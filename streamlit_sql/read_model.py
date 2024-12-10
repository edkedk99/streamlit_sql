from datetime import date, datetime
from functools import cached_property
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import Row, func, select
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute, selectinload
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql import filters


class ReadStmt:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        order_by: str = "id",
        filter_by: list[tuple[InstrumentedAttribute, Any]] = list(),
        joins_filter_by: list[DeclarativeAttributeIntercept] = list(),
        available_sidebar_filter: list[str] | None = None,
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.order_by = order_by
        self.filter_by = filter_by
        self.joins_filter_by = joins_filter_by
        self.available_sidebar_filter = available_sidebar_filter
        self.stmt_no_pag = select(Model)
        self._add_joins()
        self._add_filters()
        self._add_sidebar_filters()
        self._add_order_by()
        self._add_load_relationships()

        columns = self.Model.__table__.columns.values()
        self.rels_list = list(self.Model.__mapper__.relationships)

        self.qtty_rows = self.get_qtty_rows()

    def _add_joins(self):
        for join_model in self.joins_filter_by:
            self.stmt_no_pag = self.stmt_no_pag.join(join_model)

    def _add_filters(self):
        for col, value in self.filter_by:
            self.stmt_no_pag = self.stmt_no_pag.where(col == value)

    def _add_order_by(self):
        col = self.Model.__table__.columns.get(self.order_by)
        self.stmt_no_pag = self.stmt_no_pag.order_by(col)

    def _add_sidebar_filters(self):
        with self.conn.session as s:
            table_name = self.Model.__tablename__
            existing = filters.ExistingData(
                session=s,
                Model=self.Model,
            )

        sidebar_filters = filters.SidebarFilter(
            self.Model,
            existing,
            self.filter_by,
            self.available_sidebar_filter,
        )

        filters_dict = sidebar_filters.filters

        for col_name, value in filters_dict.items():
            col = self.Model.__table__.columns.get(col_name)
            assert col is not None

            col_type = col.type.python_type
            is_datetime = col_type is date or col_type is datetime
            is_value_tuple = isinstance(value, tuple)

            if is_datetime and is_value_tuple:
                self.stmt_no_pag.where(col >= value[0], col <= value[1])
            elif isinstance(value, filters.FkOpt):
                self.stmt_no_pag = self.stmt_no_pag.where(col == value.idx)
            else:
                self.stmt_no_pag = self.stmt_no_pag.where(col == value)

    def _add_load_relationships(self):
        rels_list = list(self.Model.__mapper__.relationships)

        self.stmt_no_pag = self.stmt_no_pag.options(
            selectinload(*rels_list)  # pyright: ignore
        )

    def get_qtty_rows(self):
        stmt_no_pag = select(func.count()).select_from(self.stmt_no_pag.subquery())
        with self.conn.session as s:
            qtty = s.execute(stmt_no_pag).scalar_one()

        return qtty


class ReadData:
    def __init__(
        _self,
        _read_stmt: ReadStmt,
        _rolling_total_column: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> None:
        _self.read_stmt = _read_stmt
        _self.rolling_total_column = _rolling_total_column
        _self.limit = limit
        _self.page = page

        _self._cols_name = [
            col.description
            for col in _read_stmt.Model.__table__.columns
            if col.description
        ]

        _self.stmt_pag = _self.get_stmt_pag()
        stmt_params = dict(_self.stmt_pag.compile().params)
        _self.data = _self.get_data(str(_self.stmt_pag), stmt_params, ss.stsql_updated)

    def get_stmt_pag(
        _self,
    ):
        offset = (_self.page - 1) * _self.limit
        result = _self.read_stmt.stmt_no_pag.offset(offset).limit(_self.limit)
        return result

    @property
    def _initial_balance(self):
        if not self.rolling_total_column or self.page == 1:
            return 0

        rolling_column = self.read_stmt.Model.__table__.columns[
            self.rolling_total_column
        ]

        initial_limit = (self.page - 1) * self.limit
        subquery_no_pag = (
            select(rolling_column.label("rolling_column"))
            .limit(initial_limit)
            .subquery()
        )
        stmt_no_pag = select(func.sum(subquery_no_pag.c.rolling_column))

        with self.read_stmt.conn.session as s:
            total = s.execute(stmt_no_pag).scalar() or 0

        total = float(total)
        return total

    @cached_property
    def rels(self):
        fks = [
            list(col.foreign_keys)[0]
            for col in self.read_stmt.Model.__table__.columns
            if len(col.foreign_keys) > 0
        ]

        result = [
            rel
            for rel in self.read_stmt.rels_list
            for fk in fks
            if fk.get_referent(rel.target) is not None
        ]
        return result

    def _get_row(self, row: Row[tuple[DeclarativeBase]]):
        col_data = {col: getattr(row[0], col) for col in self._cols_name}
        rel_obj = {rel.key: getattr(row[0], rel.key) for rel in self.rels}

        rel_data = {name: str(rel) for name, rel in rel_obj.items()}

        row_data = {**col_data, **rel_data}
        return row_data

    @st.cache_data
    def get_data(_self, stmt_pag_str: str, stmt_params: dict, updated: int):
        with _self.read_stmt.conn.session as s:
            rows = s.execute(_self.stmt_pag)
            rows_dict = [_self._get_row(row) for row in rows]

        df = pd.DataFrame(rows_dict)
        if df.empty:
            return df

        if _self.rolling_total_column:
            label = f"sum_{_self.rolling_total_column}"
            df[label] = df[_self.rolling_total_column].cumsum() + _self._initial_balance

        return df
