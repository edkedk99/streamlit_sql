from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence, Type

import streamlit as st
from dateutil.relativedelta import relativedelta
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.sql.schema import ForeignKey
from streamlit import session_state as ss

from streamlit_sql.lib import get_pretty_name


@dataclass
class FkOpt:
    idx: int
    name: str


class ExistingData:
    def __init__(
        self,
        session: Session,
        Model: Type[DeclarativeBase],
    ) -> None:
        self.session = session
        self.Model = Model

        self.cols = Model.__table__.columns
        reg_values: Any = Model.registry._class_registry.values()
        self._models = [reg for reg in reg_values if hasattr(reg, "__tablename__")]

        table_name = Model.__tablename__

        self.text = self.get_text(table_name, ss.stsql_updated)
        self.dt = self.get_dt(table_name, ss.stsql_updated)
        self.fk = self.get_fk(table_name, ss.stsql_updated)

    def _get_str_opts(self, column) -> Sequence[str]:
        col_name = column.name
        stmt = select(distinct(column)).select_from(self.Model).limit(10000)
        opts = self.session.execute(stmt).scalars().all()
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

    def get_foreign_opts(self, foreign_key: ForeignKey):
        foreign_table_name = foreign_key.column.table.name
        model = next(
            reg for reg in self._models if reg.__tablename__ == foreign_table_name
        )
        fk_pk_name = foreign_key.column.description

        stmt = select(model)
        rows = self.session.execute(stmt).scalars()
        opts = [self.get_foreign_opt(row, fk_pk_name) for row in rows]
        return opts

    @st.cache_data
    def get_fk(_self, table_name: str, updated: int):
        fk_cols = [col for col in _self.cols if len(list(col.foreign_keys)) > 0]
        opts = {
            col.description: _self.get_foreign_opts(list(col.foreign_keys)[0])
            for col in fk_cols
            if col.description
        }
        return opts


class SidebarFilter:
    def __init__(
        self,
        Model: type[DeclarativeBase],
        existing_data: ExistingData,
        filter_by: list[tuple[InstrumentedAttribute, Any]] = [],
        available_sidebar_filter: list[str] | None = None,
    ) -> None:
        self.Model = Model
        self.opts = existing_data
        self.filter_by = filter_by
        self.available_sidebar_filter = available_sidebar_filter

        self.table_name = Model.__tablename__
        self.rels_list = list(self.Model.__mapper__.relationships)

    @property
    def cols(self):
        filter_cols: list[str] = [
            col.name for col, _ in self.filter_by if col.table.name == self.table_name
        ]

        all_cols = self.Model.__table__.columns
        result = [
            col
            for col in all_cols
            if col.name not in filter_cols and not col.primary_key
        ]

        if self.available_sidebar_filter:
            result = [
                col for col in result if col.name in self.available_sidebar_filter
            ]

        return result

    def _date_filter(self, label: str, min_value: date, max_value: date):
        container = st.sidebar.container(border=True)
        container.write(label)
        inicio_c, final_c = container.columns(2)
        inicio = inicio_c.date_input(
            "Inicio",
            key=f"date_filter_inicio_{label}",
            value=min_value,
            min_value=min_value,
            max_value=max_value,
        )
        final = final_c.date_input(
            "Final",
            key=f"date_filter_final_{label}",
            value=max_value,
            min_value=min_value,
            max_value=max_value,
        )
        return (inicio, final)

    def filter_col(self, col: KeyedColumnElement):
        col_name = col.description
        assert col_name is not None
        col_label = get_pretty_name(col_name)
        is_fk = len(col.foreign_keys) > 0
        col_type = col.type.python_type
        if is_fk:
            opts = self.opts.fk[col_name]
            rel_name = col_label.removesuffix(" Id")
            value = st.sidebar.selectbox(
                rel_name,
                options=opts,
                format_func=lambda opt: opt.name,
                index=None,
            )
        elif col_type is str:
            opts = self.opts.text[col_name]
            value = st.sidebar.selectbox(col_label, options=opts, index=None)
        elif col_type is int:
            value = st.sidebar.number_input(col_label, step=1, value=None)
        elif col_type is float:
            value = st.sidebar.number_input(col_label, step=0.1, value=None)
        elif col_type is date:
            min_value, max_value = self.opts.dt[col_name]
            value = self._date_filter(col_label, min_value, max_value)
        else:
            value = None

        return value

    @property
    def filters(self):
        conds = {
            col.description: self.filter_col(col)
            for col in self.cols
            if col.description
        }
        conds = {k: v for k, v in conds.items() if v}
        return conds
