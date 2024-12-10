from dataclasses import dataclass, field
from typing import Any

import streamlit as st
import streamlit_antd_components as sac
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql import read_model, update_model
from streamlit_sql.lib import get_pretty_name, get_row_index, set_state


@dataclass
class ModelOpts:
    """Sqlalchemy Model and configuration for the CRUD interface
    This is a dataclass with Sqlalchemy Model as the only required argument.

    The other arguments are optional configuration of this package features.
    It will be used as argument to the main show_sql_ui function

    Args:
        Model (type[DeclarativeBase]): The sqlalchemy Model to display
        rolling_total_column (str, optional): A numeric column name of the Model. A new column will be displayed with the rolling sum of these column
        filter_by (list[tuple[InstrumentedAttribute, Any]], optional): A list of tuple of the pair column and value. It will filter the rows to display before presenting to the user by adding to the select statement WHERE condition like *select(Model).where(COLUMN == VALUE)*. If the column comes from a relationship table, add that Sqlalchemy Model to joins_filter_by arg.
        joins_filter_by (list[DeclarativeAttributeIntercept], optional): List of Models that needs to join if added a relationship column in filter_by arg.
        columns (list[str], optional): Select which columns of the Model to display. Defaults to all columns
        edit_create_default_values (dict, optional): A dict with column name as keys and values to be default. When the user clicks to create a row, those columns will not show on the form and its value will be added to the Model object
        read_use_container_width (bool, optional): add use_container_width to st.dataframe args. Default to False
        available_sidebar_filter (list[str], optional): Define wich columns the user will be able to filter in the sidebar. Defaults to all

    Examples:
        ```python
        sales_manager_col = Model.__table__.columns.get("name")
        model_opts = ModelOpts(Model=Invoice,
                               rolling_total_column="amount",
                               filter_by=[(sales_manager_col, "John")]),
                               joins_filter_by=[SalesManager],
                               columns=["date", "amount", SalesManager.__tablename__],
                               edit_create_default_values=dict(department_id=52),
                               read_use_container_width=True,
                               available_sidebar_filter=["date", SalesManager.__tablename__]
        )
        ```

    """

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

        set_state("stsql_updated", 1)
        set_state("stsql_update_ok", None)
        set_state("stsql_update_message", None)
        set_state("stsql_opened", False)

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
        self.data = self.add_data()

    def add_header(self):
        col_btn, col_title = self.header_container.columns(2)

        with col_btn:
            create_btn = st.button(f"", type="primary", icon=":material/add:")
            if create_btn:
                create_row = update_model.CreateRow(
                    conn=self.conn,
                    Model=self.model_opts.Model,
                    default_values=self.model_opts.edit_create_default_values,
                )
                create_row.show_dialog()

        with col_title:
            st.subheader(self.pretty_name)

        if ss.stsql_update_ok is True:
            self.header_container.success(
                ss.stsql_update_message, icon=":material/thumb_up:"
            )
        if ss.stsql_update_ok is False:
            self.header_container.error(
                ss.stsql_update_message, icon=":material/thumb_down:"
            )

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
            return data

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
        if not ss.stsql_opened and selected_row is not None:
            row_id = int(data.iloc[selected_row]["id"])
            update_row = update_model.UpdateRow(
                conn=self.conn,
                Model=self.model_opts.Model,
                row_id=row_id,
                default_values=self.model_opts.edit_create_default_values,
            )
            update_row.show_dialog()

        ss.stsql_opened = False

        return data


def update_query_params():
    st.query_params.tablename = ss.model_opts_selected.Model.__tablename__


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
        key="model_opts_selected",
        on_change=update_query_params,
    )

    return model_opts_selected


def show_page(conn: SQLConnection, model_opts: ModelOpts | list[ModelOpts]):
    if isinstance(model_opts, ModelOpts):
        opt = model_opts
    else:
        opt = show_many(conn, model_opts)

    page = ShowPage(conn, opt)
    return page.data
