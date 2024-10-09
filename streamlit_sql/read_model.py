from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.selectable import Select
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql import filters


def get_model_by_name(base_model, name: str):
    registry = base_model.registry._class_registry
    models_reg = [
        model for model in registry.values() if hasattr(model, "__tablename__")
    ]
    model_reg = next(model for model in models_reg if model.__tablename__ == name)
    return model_reg


def get_base_select(
    Model,
    filter_by: list[tuple[InstrumentedAttribute, Any]],
    joins_filter_by: list[DeclarativeAttributeIntercept],
):
    stmt = select(Model)
    if len(filter_by) == 0:
        return stmt

    for join_model in joins_filter_by:
        stmt = stmt.join(join_model)

    for col, value in filter_by:
        stmt = stmt.where(col == value)

    return stmt


def get_initial_balance(
    conn: SQLConnection, base_query: Select, page: int, limit: int, rolling_colname: str
):
    if page == 1:
        offset = 0
    else:
        offset = (page - 1) * limit

    stmt_get_data = base_query.limit(offset).subquery()

    rolling_column: Column = getattr(stmt_get_data.c, rolling_colname)
    stmt = select(func.sum(rolling_column))

    with conn.session as s:
        total = s.execute(stmt).scalar() or 0

    total_int = int(total)
    return total_int


def get_rolling_df(rolling_total_column: str, df: pd.DataFrame, prev_bal: float):
    label = f"sum_{rolling_total_column}"
    df[label] = df[rolling_total_column].cumsum() + prev_bal
    return df


class ReadSQL:
    def __init__(
        self,
        _conn: SQLConnection,
        Model,
        sum_columns: list[str] | None = None,
        rolling_total_column: str | None = None,
        order_by: str = "id",
        filter_by: list[tuple[InstrumentedAttribute, Any]] = list(),
        joins_filter_by: list[DeclarativeAttributeIntercept] = list(),
    ) -> None:
        self.conn = _conn
        self.Model = Model
        self.sum_columns = sum_columns
        self.rolling_total_column = rolling_total_column
        self.order_by = order_by
        self.filter_by = filter_by
        self.joins_filter_by = joins_filter_by

        columns: list[Column] = self.Model.__table__.columns.values()
        self.pk_col: Column = next(col for col in columns if col.primary_key)

        self.filter_opts = filters.get_filter_opts(_conn, Model)
        self.base_query = self.get_base_query()

    def get_base_query(self):
        stmt = get_base_select(self.Model, self.filter_by, self.joins_filter_by)

        model_name: str = self.Model.__tablename__

        cols_name = [
            item[0].name for item in self.filter_by if item[0].table.name == model_name
        ]
        stmt = filters.get_filters(self.Model, stmt, cols_name, self.filter_opts)

        order_column = getattr(self.Model, self.order_by)
        stmt = stmt.order_by(order_column, self.pk_col)
        return stmt

    def get_rel_fk(self, rels_list, fk: ForeignKey):
        fk_table_name = fk.column.table.description
        rel = next(
            relation for relation in rels_list if relation.target.name == fk_table_name
        )
        return rel

    def query_data(self, limit: int, page: int):
        fks: set[ForeignKey] = self.Model.__table__.foreign_keys

        rels_list = list(self.Model.__mapper__.relationships)
        rels_fk = [self.get_rel_fk(rels_list, fk) for fk in fks]

        offset = (page - 1) * limit
        stmt = self.base_query.offset(offset).limit(limit)
        if len(rels_fk) > 0:
            stmt = stmt.options(selectinload(*rels_fk))

        cols = self.Model.__table__.columns.keys()
        rows_data: list[dict] = list()
        with self.conn.session as s:
            rows = s.execute(stmt)
            for row in rows:
                col_data = {col: getattr(row[0], col) for col in cols}
                rel_data = {rel: str(getattr(row[0], rel.key)) for rel in rels_fk}

                row_data = {**col_data, **rel_data}
                rows_data.append(row_data)

        df = pd.DataFrame(rows_data)
        return df

    def get_data(self, limit: int, page: int):
        df = self.query_data(limit, page)
        if df.empty:
            return df

        if self.rolling_total_column:
            prev_total = get_initial_balance(
                self.conn, self.base_query, page, limit, self.rolling_total_column
            )
            df = get_rolling_df(self.rolling_total_column, df, prev_total)
        return df
