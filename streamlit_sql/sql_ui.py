from typing import Any

import streamlit as st
import streamlit_antd_components as sac
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept
from sqlalchemy.sql.selectable import Select
from streamlit.connections.sql_connection import SQLConnection
from streamlit.elements.arrow import DataframeState

from streamlit_sql import update_model
from streamlit_sql.read_model import ReadSQL

ITEMS_PAGE = [50, 100, 200, 500, 1000]


def get_count(conn: SQLConnection, base_query: Select):
    stmt_count = list(base_query.subquery().primary_key)[0]
    stmt = select(func.count(stmt_count))

    with conn.session as s:
        count = s.execute(stmt).scalar() or 0

    count_float = int(count)
    return count_float


def show_pagination(items_page: list[int], count: int):
    pag_col1, pag_col2 = st.columns([0.2, 0.8])

    first_item_candidates = [item for item in items_page if item > count]
    last_item = first_item_candidates[0] if items_page[-1] > count else items_page[-1]
    items_page_str = [str(item) for item in items_page if item <= last_item]

    with pag_col1:
        menu_cas = sac.cascader(
            items=items_page_str, placeholder="Items per page"  # pyright: ignore
        )

    items_per_page = menu_cas[0] if menu_cas else items_page_str[0]

    with pag_col2:
        page = sac.pagination(
            total=count,
            page_size=int(items_per_page),
            show_total=True,
            jump=True,
        )

    return (int(items_per_page), int(page))


def get_row_index(state: DataframeState | None):
    if not state:
        return

    selection = state.get("selection")
    if not selection:
        return

    rows = selection.get("rows")
    if rows:
        result = rows[0]
        return result


def show_update(
    table_name: str,
    conn: SQLConnection,
    row_id: int,
    Model,
    default_values: dict = dict(),
):
    @st.dialog(f"Edit {table_name}", width="large")  # pyright: ignore
    def wrap_show_update(
        conn: SQLConnection,
        row_id: int,
        Model,
        default_values: dict = dict(),
    ):
        update_model.show_update(conn, row_id, Model, default_values)

    wrap_show_update(conn, row_id, Model, default_values)


def show_create(
    table_name: str,
    conn: SQLConnection,
    Model,
    default_values: dict = dict(),
):
    @st.dialog(f"Create {table_name}", width="large")
    def wrap_create_form(
        conn: SQLConnection,
        Model,
        default_values: dict = dict(),
    ):
        update_model.show_create(conn, Model, default_values)

    wrap_create_form(conn, Model, default_values)


def show_page(
    conn: SQLConnection,
    Model,
    read_sum_columns: list[str] | None = None,
    read_rolling_total_column: str | None = None,
    read_order_by: str = "id",
    read_filter_by: list[tuple[InstrumentedAttribute, Any]] = list(),
    read_joins_filter_by: list[DeclarativeAttributeIntercept] = list(),
    read_use_container_width: bool = False,
    edit_create_default_values: dict = dict(),
):
    read_sql = ReadSQL(
        conn,
        Model,
        read_sum_columns,
        read_rolling_total_column,
        read_order_by,
        read_filter_by,
        read_joins_filter_by,
    )

    data_container = st.container()
    pagination_container = st.container()

    table_name: str = Model.__tablename__

    create_btn = data_container.button(f"Novo {table_name}")
    if create_btn:
        show_create(table_name, conn, Model, edit_create_default_values)
    # with data_container.popover(f"Novo {table_name}", use_container_width=False):
    #     update_model.show_create(conn, Model, edit_create_default_values)

    count = get_count(conn, read_sql.base_query)
    with pagination_container:
        items_per_page, page = show_pagination(ITEMS_PAGE, count)

    data = read_sql.get_data(items_per_page, page)
    selection_state = None
    if data.empty:
        st.header(":red[Tabela Vazia]")
    else:
        data.columns = data.columns.astype("str")
        selection_state = data_container.dataframe(
            data,
            use_container_width=read_use_container_width,
            height=650,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

    row_i = get_row_index(selection_state)

    if row_i is not None:
        row_id = int(data.iloc[row_i]["id"])
        show_update(table_name, conn, row_id, Model, edit_create_default_values)
    return data
