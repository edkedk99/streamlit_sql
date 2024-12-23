from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
import streamlit_antd_components as sac
from sqlalchemy import CTE, Select, desc, distinct, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import KeyedColumnElement
from sqlalchemy.sql.expression import literal_column
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator

from streamlit_sql.lib import get_pretty_name

hash_funcs: dict[Any, Callable[[Any], Any]] = {
    pd.Series: lambda serie: serie.to_dict(),
    CTE: lambda sel: (str(sel), sel.compile().params),
    Select: lambda sel: (str(sel), sel.compile().params),
    "streamlit_sql.read_cte.ColFilter": lambda cl: (cl.dt_filters, cl.no_dt_filters),
}


def get_existing_cond(col: KeyedColumnElement):
    is_str = col.type.python_type is str
    is_bool = col.type.python_type is bool
    is_not_pk = not col.primary_key

    fks = list(col.foreign_keys)
    has_fk = len(fks) > 0
    int_not_fk_cond = col.type.python_type is int and not has_fk

    cond = is_not_pk and (is_str or is_bool or int_not_fk_cond)
    return cond


@st.cache_data(hash_funcs=hash_funcs)
def get_existing_values(
    _session: Session,
    cte: CTE,
    updated: int,
    available_col_filter: list[str] | None = None,
):
    if not available_col_filter:
        available_col_filter = []

    cols = list(cte.columns)

    if len(available_col_filter) > 0:
        cols = [col for col in cte.columns if get_existing_cond(col)]

    result: dict[str, Any] = {}
    for col in cols:
        stmt = select(distinct(col)).order_by(col)
        values = _session.execute(stmt).scalars().all()
        colname = col.description
        assert colname is not None
        result[colname] = values

    return result


class ColFilter:
    def __init__(
        self,
        container: DeltaGenerator,
        cte: CTE,
        existing_values: dict[str, Any],
        available_col_filter: list[str] | None = None,
        base_key: str = "",
    ) -> None:
        self.container = container
        self.cte = cte
        self.existing_values = existing_values
        self.available_col_filter = available_col_filter or []
        self.base_key = base_key

        self.dt_filters = self.get_dt_filters()
        self.no_dt_filters = self.get_no_dt_filters()

    def __str__(self):
        dt_str = ", ".join(
            f"{k}: {dt.strftime('%d/%m/%Y')}"
            for k, v in self.dt_filters.items()
            for dt in v
            if v
            if dt
        )
        no_dt_str = ", ".join(f"{k}: {v}" for k, v in self.no_dt_filters.items() if v)

        filter_str = ""
        if dt_str != "":
            filter_str += f"{dt_str}, "
        if no_dt_str != "":
            filter_str += f"{no_dt_str}"

        return filter_str

    def get_dt_filters(self):
        cols = [
            col
            for col in self.cte.columns
            if col.description in self.available_col_filter
            and col.type.python_type is date
        ]

        result: dict[str, tuple[date | None, date | None]] = {}
        for col in cols:
            colname = col.description
            assert colname is not None
            label = get_pretty_name(colname)
            self.container.write(label)
            inicio_c, final_c = self.container.columns(2)
            inicio = inicio_c.date_input(
                "Inicio",
                value=None,
                key=f"{self.base_key}_date_filter_inicio_{label}",
            )
            final = final_c.date_input(
                "Final",
                value=None,
                key=f"{self.base_key}_date_filter_final_{label}",
            )

            assert inicio is None or isinstance(inicio, date)
            if inicio is None:
                inicio_date = None
            else:
                inicio_date = date(inicio.year, inicio.month, inicio.day)

            assert final is None or isinstance(final, date)
            if final is None:
                final_date = None
            else:
                final_date = date(final.year, final.month, final.day)
            result[colname] = inicio_date, final_date
        return result

    def get_no_dt_filters(self):
        cols = [
            col
            for col in self.cte.columns
            if col.description in self.available_col_filter
            and col.type.python_type is not date
        ]

        result: dict[str, str | None] = {}
        for col in cols:
            colname = col.description
            assert colname is not None

            existing_value = self.existing_values.get(colname)

            if existing_value is not None:
                label = get_pretty_name(colname)
                value = self.container.selectbox(
                    label,
                    options=self.existing_values[colname],
                    index=None,
                    key=f"{self.base_key}_no_dt_filter_{label}",
                )
                result[colname] = value

        return result


def get_stmt_no_pag_dt(cte: CTE, no_dt_filters: dict[str, str | None]):
    stmt = select(cte)
    for colname, value in no_dt_filters.items():
        if value:
            col = cte.columns.get(colname)
            assert col is not None
            stmt = stmt.where(col == value)

    return stmt


def get_stmt_no_pag(cte: CTE, col_filter: ColFilter):
    no_dt_filters = col_filter.no_dt_filters
    stmt = get_stmt_no_pag_dt(cte, no_dt_filters)

    dt_filters = col_filter.dt_filters
    for colname, filters in dt_filters.items():
        col = cte.columns.get(colname)
        assert col is not None
        inicio, final = filters
        if inicio:
            stmt = stmt.where(col >= inicio)
        if final:
            stmt = stmt.where(col <= final)

    return stmt


@st.cache_data(hash_funcs=hash_funcs)
def get_qtty_rows(_conn: SQLConnection, stmt_no_pag: Select):
    stmt = select(func.count()).select_from(stmt_no_pag.subquery())
    with _conn.session as s:
        qtty = s.execute(stmt).scalar_one()

    return qtty


def show_pagination(count: int, opts_items_page: tuple[int, ...], base_key: str = ""):
    pag_col1, pag_col2 = st.columns([0.2, 0.8])

    first_item_candidates = [item for item in opts_items_page if item > count]
    last_item = (
        first_item_candidates[0] if opts_items_page[-1] > count else opts_items_page[-1]
    )
    items_page_str = [str(item) for item in opts_items_page if item <= last_item]

    with pag_col1:
        menu_cas = sac.cascader(
            items=items_page_str,  # pyright: ignore
            placeholder="Items per page",
            key=f"{base_key}_menu_cascader",
        )

    items_per_page = menu_cas[0] if menu_cas else items_page_str[0]

    with pag_col2:
        page = sac.pagination(
            total=count,
            page_size=int(items_per_page),
            show_total=True,
            jump=True,
            key=f"{base_key}_pagination",
        )

    return (int(items_per_page), int(page))


def get_stmt_pag(stmt_no_pag: Select, limit: int, page: int):
    offset = (page - 1) * limit
    stmt = stmt_no_pag.offset(offset).limit(limit)
    return stmt


# @st.cache_data(hash_funcs=hash_funcs)
def initial_balance(
    _session: Session,
    stmt_no_pag_dt: Select,
    col_filter: ColFilter,
    rolling_total_column: str | None,
    first_row_id: int | None,
):
    if not rolling_total_column:
        return 0

    col = stmt_no_pag_dt.columns.get(rolling_total_column)
    assert col is not None

    row_number_col = func.row_number().over(order_by=literal_column("NULL"))
    id_col = stmt_no_pag_dt.c.id

    subq = select(
        id_col.label("id"),
        row_number_col.label("position"),
        col.label("Valor"),
    ).subquery()

    stmt_last = select(subq.c.position)
    if first_row_id:
        stmt_last = stmt_last.where(subq.c.id == first_row_id)
    stmt_last = stmt_last.order_by(desc(subq.c.position))

    last_pos_list = _session.execute(stmt_last).scalars().all()
    if not last_pos_list:
        return 0

    last_pos = min(last_pos_list)

    rolling_sum = func.sum(subq.c.Valor).over(order_by=subq.c.position)
    stmt_sum = (
        select(rolling_sum)
        .where(subq.c.position < last_pos)
        .order_by(desc(subq.c.position))
    )

    total: float | None = _session.execute(stmt_sum).scalars().first()
    return total or 0
