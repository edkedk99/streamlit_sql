from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import streamlit as st
from dateutil.relativedelta import relativedelta
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.schema import ForeignKey
from streamlit import session_state as ss


@dataclass
class FkOpt:
    idx: int
    name: str


class ExistingData:
    def __init__(
        self,
        session: Session,
        Model: type[DeclarativeBase],
        default_values: dict,
        row: DeclarativeBase | None = None,
    ) -> None:
        self.session = session
        self.Model = Model
        self.default_values = default_values
        self.row = row

        self.cols = Model.__table__.columns
        reg_values: Any = Model.registry._class_registry.values()
        self._models = [reg for reg in reg_values if hasattr(reg, "__tablename__")]

        table_name = Model.__tablename__
        self.text = self.get_text(table_name, ss.stsql_updated)
        self.dt = self.get_dt(table_name, ss.stsql_updated)
        self.fk = self.get_fk(table_name, ss.stsql_updated)

    def add_default_where(self, stmt, model: type[DeclarativeBase]):
        cols = model.__table__.columns
        default_values = {
            colname: value
            for colname, value in self.default_values.items()
            if colname in cols
        }

        for colname, value in default_values.items():
            default_col = cols.get(colname)
            stmt = stmt.where(default_col == value)

        return stmt

    def _get_str_opts(self, column) -> Sequence[str]:
        col_name = column.name
        stmt = select(distinct(column)).select_from(self.Model).limit(10000)
        stmt = self.add_default_where(stmt, self.Model)

        opts = list(self.session.execute(stmt).scalars().all())
        row_value = None
        if self.row:
            row_value: str | None = getattr(self.row, col_name)
        if row_value is not None and row_value not in opts:
            opts.append(row_value)

        return opts

    @st.cache_data
    def get_text(_self, table_name: str, updated: int) -> dict[str, Sequence[str]]:
        opts = {
            col.name: _self._get_str_opts(col)
            for col in _self.cols
            if col.type.python_type is str
        }
        return opts

    def _get_dt_col(self, column):
        min_default = date.today() - relativedelta(days=30)
        min_dt: date = self.session.query(func.min(column)).scalar() or min_default
        max_dt: date = self.session.query(func.max(column)).scalar() or date.today()
        return min_dt, max_dt

    @st.cache_data
    def get_dt(_self, table_name: str, updated: int) -> dict[str, tuple[date, date]]:
        opts = {
            col.name: _self._get_dt_col(col)
            for col in _self.cols
            if col.type.python_type is date
        }
        return opts

    def get_foreign_opt(self, row, fk_pk_name: str):
        idx = getattr(row, fk_pk_name)
        fk_opt = FkOpt(idx, str(row))
        return fk_opt

    def get_foreign_opts(self, col, foreign_key: ForeignKey):
        foreign_table_name = foreign_key.column.table.name
        model = next(
            reg for reg in self._models if reg.__tablename__ == foreign_table_name
        )
        fk_pk_name = foreign_key.column.description
        stmt = select(model).distinct()

        if col.table.name != foreign_key.column.table.name:
            stmt = stmt.outerjoin(self.Model, col == foreign_key.column)

        stmt = self.add_default_where(stmt, model)

        rows = self.session.execute(stmt).scalars()

        opts = [self.get_foreign_opt(row, fk_pk_name) for row in rows]

        opt_row = None
        if self.row is not None:
            opt_row = self.get_foreign_opt(self.row, fk_pk_name)
        if opt_row and opt_row not in opts:
            opts.append(opt_row)

        return opts

    @st.cache_data
    def get_fk(_self, table_name: str, _updated: int):
        fk_cols = [col for col in _self.cols if len(list(col.foreign_keys)) > 0]
        opts = {
            col.description: _self.get_foreign_opts(col, next(iter(col.foreign_keys)))
            for col in fk_cols
            if col.description
        }
        return opts
