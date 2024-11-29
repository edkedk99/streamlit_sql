from dataclasses import dataclass, field
from typing import Any

import streamlit as st
import streamlit_antd_components as sac
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql import read_model, update_model
from streamlit_sql.lib import get_pretty_name, get_row_index, set_state
from streamlit import session_state as ss


@dataclass
class ModelOpts:
    Model: type[DeclarativeBase]
    rolling_total_column: str | None = None
    order_by: str = "id"
    filter_by: list[tuple[InstrumentedAttribute, Any]] = field(default_factory=list)
    joins_filter_by: list[DeclarativeAttributeIntercept] = field(default_factory=list)
    columns: list[str] | None = None
    edit_create_default_values: dict = field(default_factory=dict)
    read_use_container_width: bool = False
    available_sidebar_filter: list[str] | None = None


class ShowPage:
    OPTS_ITEMS_PAGE = [50, 100, 200, 500, 1000]

    def __init__(self, conn: SQLConnection, model_opts: ModelOpts) -> None:
        self.conn = conn
        self.model_opts = model_opts

        self.pretty_name = get_pretty_name(model_opts.Model.__tablename__)
        self.read_stmt = read_model.ReadStmt(
            conn,
            model_opts.Model,
            model_opts.order_by,
            model_opts.filter_by,
            model_opts.joins_filter_by,
            model_opts.available_sidebar_filter,
        )

        self.header_container = st.container()
        self.data_container = st.container()
        self.pag_container = st.container()

        self.add_header()
        self.items_per_page, self.page = self.add_pagination(
            str(self.read_stmt.stmt_no_pag)
        )
        self.current_data = self.add_data()

    def add_header(self):
        col_btn, col_title = self.header_container.columns(2)

        with col_btn:
            create_btn = st.button(f"", type="primary", icon=":material/add:")
            if create_btn:
                create_row = update_model.CreateRow(
                    self.conn,
                    self.model_opts.Model,
                    self.model_opts.edit_create_default_values,
                )
                create_row.show_dialog()

        with col_title:
            st.subheader(self.pretty_name)

    def add_pagination(_self, stmt_no_pag_str: str):
        pag_col1, pag_col2 = _self.pag_container.columns([0.2, 0.8])

        count = _self.read_stmt.qtty_rows
        first_item_candidates = [item for item in _self.OPTS_ITEMS_PAGE if item > count]
        last_item = (
            first_item_candidates[0]
            if _self.OPTS_ITEMS_PAGE[-1] > count
            else _self.OPTS_ITEMS_PAGE[-1]
        )
        items_page_str = [
            str(item) for item in _self.OPTS_ITEMS_PAGE if item <= last_item
        ]

        with pag_col1:
            menu_cas = sac.cascader(
                items=items_page_str,  # pyright: ignore
                placeholder="Items per page",
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

    def add_data(self):
        read_data = read_model.ReadData(
            self.read_stmt,
            self.model_opts.rolling_total_column,
            self.items_per_page,
            self.page,
        )

        data = read_data.data
        if data.empty:
            st.header(":red[Tabela Vazia]")
            return (None, None)

        data.columns = data.columns.astype("str")
        selection_state = self.data_container.dataframe(
            data,
            use_container_width=self.model_opts.read_use_container_width,
            height=650,
            hide_index=True,
            column_order=self.model_opts.columns,
            on_select="rerun",
            selection_mode="single-row",
        )

        selected_row = get_row_index(selection_state)

        if selected_row is not None:
            row_id = int(data.iloc[selected_row]["id"])
            update_row = update_model.UpdateRow(
                self.conn,
                self.model_opts.Model,
                row_id,
                self.model_opts.edit_create_default_values,
            )
            update_row.show_dialog()


def show_many(conn: SQLConnection, model_opts: list[ModelOpts]):
    if "tablename" not in st.query_params:
        first_model = model_opts[0]
        st.query_params.tablename = first_model.Model.__tablename__

    tablename: str = st.query_params.tablename
    tables_name = [opt.Model.__tablename__ for opt in model_opts]
    if tablename in tables_name:
        model_index = tables_name.index(tablename)
    else:
        model_index = 0

    model_opts_selected = st.selectbox(
        "Table",
        options=model_opts,
        index=model_index,
        format_func=lambda model_opts: get_pretty_name(model_opts.Model.__tablename__),
    )
    st.query_params.tablename = model_opts_selected.Model.__tablename__

    ShowPage(conn, model_opts_selected)


def show_page(conn: SQLConnection, model_opts: ModelOpts | list[ModelOpts]):
    if isinstance(model_opts, ModelOpts):
        ShowPage(conn, model_opts)
    else:
        set_state("last_model_index", 0)
        model_index: int = ss.last_model_index
