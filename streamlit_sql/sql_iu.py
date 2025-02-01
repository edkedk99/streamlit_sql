from collections.abc import Callable

import pandas as pd
import streamlit as st
from sqlalchemy import CTE, Select, select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections import SQLConnection
from streamlit.elements.arrow import DataframeState

from streamlit_sql import create_delete_model, lib, read_cte, update_model

OPTS_ITEMS_PAGE = (50, 100, 200, 500, 1000)


class SqlUi:
    """Show A CRUD interface in a Streamlit Page

    See in __init__ method detailed descriptions of arguments and properties

    It also offers the following properties:


    """

    def __init__(
        self,
        conn: SQLConnection,
        read_instance,
        edit_create_model: type[DeclarativeBase],
        available_filter: list[str] | None = None,
        edit_create_default_values: dict | None = None,
        rolling_total_column: str | None = None,
        read_use_container_width: bool = False,
        hide_id: bool = True,
        base_key: str = "",
        style_fn: Callable[[pd.Series], list[str]] | None = None,
        update_show_many: bool = False,
    ):
        """Init method

        Arguments:
            conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
            read_instance (Select | CTE | Model): The sqlalchemy select statement to display or a CTE. Choose columns to display , join, query or order.If selecting columns, you need to add the id column. If a Model, it will select all columns.
            edit_create_default_values (dict, optional): A dict with column name as keys and values to be default. When the user clicks to create a row, those columns will not show on the form and its value will be added to the Model object
            available_filter (list[str], optional): Define wich columns the user will be able to filter in the sidebar. Defaults to all
            rolling_total_column (str, optional): A numeric column name of the Model. A new column will be displayed with the rolling sum of these column
            read_use_container_width (bool, optional): add use_container_width to st.dataframe args. Default to False
            hide_id (bool, optional): The id column will not be displayed if set to True. Defaults to True
            base_key (str, optional): A prefix to add to widget's key argument.
            style_fn (Callable[[pd.Series], list[str]], optional): A function that style the DataFrame that receives the a Series representing a DataFrame row as argument and should return a list of string with the css property of the size of the number of columns of the DataFrame

        Attributes:
            df (pd.Dataframe): The Dataframe displayed in the screen
            selected_rows (list[int]): The position of selected rows. This is not the row id.
            qtty_rows (int): The quantity of all rows after filtering
        """
        self.conn = conn
        self.read_instance = read_instance
        self.edit_create_model = edit_create_model
        self.available_filter = available_filter or []
        self.edit_create_default_values = edit_create_default_values or {}
        self.rolling_total_column = rolling_total_column
        self.read_use_container_width = read_use_container_width
        self.hide_id = hide_id
        self.base_key = base_key
        self.style_fn = style_fn
        self.update_show_many = update_show_many

        self.cte = self.get_cte()
        self.rolling_pretty_name = lib.get_pretty_name(self.rolling_total_column or "")

        # Bootstrap
        self.set_initial_state()
        self.set_structure()
        self.notification()

        # Create UI
        col_filter = self.filter()
        stmt_no_pag = read_cte.get_stmt_no_pag(self.cte, col_filter)
        qtty_rows = read_cte.get_qtty_rows(self.conn, stmt_no_pag)
        items_per_page, page = self.pagination(qtty_rows)
        stmt_pag = read_cte.get_stmt_pag(stmt_no_pag, items_per_page, page)
        initial_balance = self.get_initial_balance(col_filter)
        df = self.get_df(stmt_pag, initial_balance)
        selection_state = self.show_df(df)
        rows_selected = self.get_rows_selected(selection_state)

        # CRUD
        self.crud(df, rows_selected)
        ss.stsql_opened = False

        # Returns
        self.df = df
        self.rows_selected = rows_selected
        self.qtty_rows = qtty_rows

    def set_initial_state(self):
        lib.set_state("stsql_updated", 1)
        lib.set_state("stsql_update_ok", None)
        lib.set_state("stsql_update_message", None)
        lib.set_state("stsql_opened", False)

    def set_structure(self):
        self.header_container = st.container()
        self.data_container = st.container()
        self.pag_container = st.container()

        table_name = lib.get_pretty_name(self.edit_create_model.__tablename__)
        self.header_container.header(table_name, divider="orange")

        self.expander_container = self.header_container.expander(
            "Filter",
            icon=":material/search:",
        )

        self.filter_container = self.header_container.container()

        if self.rolling_total_column:
            self.saldo_toggle_col, self.saldo_value_col = self.header_container.columns(
                2
            )

        self.btns_container = self.header_container.container()

    def notification(self):
        if ss.stsql_update_ok is True:
            self.header_container.success(
                ss.stsql_update_message, icon=":material/thumb_up:"
            )
        if ss.stsql_update_ok is False:
            self.header_container.error(
                ss.stsql_update_message, icon=":material/thumb_down:"
            )

    def get_cte(self):
        if isinstance(self.read_instance, Select):
            cte = self.read_instance.cte()
        elif isinstance(self.read_instance, CTE):
            cte = self.read_instance
        else:
            cte = select(self.read_instance).cte()

        return cte

    def filter(self):
        filter_colsname = self.available_filter
        if len(filter_colsname) == 0:
            filter_colsname = [
                col.description for col in self.cte.columns if col.description
            ]

        with self.conn.session as s:
            existing = read_cte.get_existing_values(
                _session=s,
                cte=self.cte,
                updated=ss.stsql_updated,
                available_col_filter=filter_colsname,
            )

        col_filter = read_cte.ColFilter(
            self.expander_container,
            self.cte,
            existing,
            filter_colsname,
            self.base_key,
        )
        if str(col_filter) != "":
            self.filter_container.write(col_filter)

        return col_filter

    def pagination(self, qtty_rows: int):
        with self.pag_container:
            items_per_page, page = read_cte.show_pagination(
                qtty_rows,
                OPTS_ITEMS_PAGE,
                self.base_key,
            )

        return items_per_page, page

    def get_initial_balance(self, col_filter: read_cte.ColFilter):
        if self.rolling_total_column is None:
            return 0

        saldo_toogle = self.saldo_toggle_col.toggle(
            f"Adiciona Saldo Devedor em {self.rolling_pretty_name}",
            value=True,
            key=f"{self.base_key}_saldo_toggle_sql_ui",
        )

        if not saldo_toogle:
            return 0

        first_row_id: int | None = None
        if not self.df.empty:
            first_row_id = int(self.df.iloc[0].id)

        no_dt_filters = col_filter.no_dt_filters
        stmt_no_pag_dt = read_cte.get_stmt_no_pag_dt(self.cte, no_dt_filters)

        with self.conn.session as s:
            initial_balance = read_cte.initial_balance(
                _session=s,
                stmt_no_pag_dt=stmt_no_pag_dt,
                col_filter=col_filter,
                rolling_total_column=self.rolling_total_column,
                first_row_id=first_row_id,
            )

        self.saldo_value_col.subheader(
            f"Saldo Anterior {self.rolling_pretty_name}: {initial_balance:,.2f}"
        )

        return initial_balance

    def get_df(
        self,
        stmt_pag: Select,
        initial_balance: float,
    ):
        with self.conn.connect() as c:
            df = pd.read_sql(stmt_pag, c)

        if self.rolling_total_column is None:
            return df

        rolling_col_name = f"Balance {self.rolling_pretty_name}"
        df[rolling_col_name] = df[self.rolling_total_column].cumsum() + initial_balance

        return df

    def show_df(self, df: pd.DataFrame):
        if df.empty:
            st.header(":red[Tabela Vazia]")
            return None

        column_order = None
        if self.hide_id:
            column_order = [colname for colname in df.columns if colname != "id"]

        df_style = df
        if self.style_fn is not None:
            df_style = df.style.apply(self.style_fn, axis=1)

        selection_state = self.data_container.dataframe(
            df_style,
            use_container_width=self.read_use_container_width,
            height=650,
            hide_index=True,
            column_order=column_order,
            on_select="rerun",
            selection_mode="multi-row",
            key=f"{self.base_key}_df_sql_ui",
        )
        return selection_state

    def get_rows_selected(self, selection_state: DataframeState | None):
        rows_pos = []
        if (
            selection_state
            and "selection" in selection_state
            and "rows" in selection_state["selection"]
        ):
            rows_pos = selection_state["selection"]["rows"]

        return rows_pos

    def crud(self, df: pd.DataFrame, rows_selected: list[int]):
        qtty_rows = len(rows_selected)
        action = update_model.action_btns(
            self.btns_container,
            qtty_rows,
            ss.stsql_opened,
        )

        if action == "add":
            create_row = create_delete_model.CreateRow(
                conn=self.conn,
                Model=self.edit_create_model,
                default_values=self.edit_create_default_values,
            )
            create_row.show_dialog()
        elif action == "edit":
            selected_pos = rows_selected[0]
            row_id = int(self.df.iloc[selected_pos]["id"])
            update_row = update_model.UpdateRow(
                conn=self.conn,
                Model=self.edit_create_model,
                row_id=row_id,
                default_values=self.edit_create_default_values,
                update_show_many=self.update_show_many,
            )
            update_row.show_dialog()
        elif action == "delete":
            rows_id = df.iloc[rows_selected].id.astype(int).to_list()
            delete_rows = create_delete_model.DeleteRows(
                conn=self.conn,
                Model=self.edit_create_model,
                rows_id=rows_id,
            )
            delete_rows.show_dialog()


def show_sql_ui(
    conn: SQLConnection,
    read_instance,
    edit_create_model: type[DeclarativeBase],
    available_filter: list[str] | None = None,
    edit_create_default_values: dict | None = None,
    rolling_total_column: str | None = None,
    read_use_container_width: bool = False,
    hide_id: bool = True,
    base_key: str = "",
    style_fn: Callable[[pd.Series], list[str]] | None = None,
    update_show_many: bool = False,
) -> tuple[pd.DataFrame, list[int]] | None:
    """Show A CRUD interface in a Streamlit Page

    Args:
        conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
        read_instance (Select | CTE | Model): The sqlalchemy select statement to display or a CTE. Choose columns to display , join, query or order.If selecting columns, you need to add the id column. If a Model, it will select all columns.
        edit_create_default_values (dict, optional): A dict with column name as keys and values to be default. When the user clicks to create a row, those columns will not show on the form and its value will be added to the Model object
        available_filter (list[str], optional): Define wich columns the user will be able to filter in the sidebar. Defaults to all
        rolling_total_column (str, optional): A numeric column name of the Model. A new column will be displayed with the rolling sum of these column
        read_use_container_width (bool, optional): add use_container_width to st.dataframe args. Default to False
        hide_id (bool, optional): The id column will not be displayed if set to True. Defaults to True
        base_key (str, optional): A prefix to add to widget's key argument.
        style_fn (Callable[[pd.Series], list[str]], optional): A function that style the DataFrame that receives the a Series representing a DataFrame row as argument and should return a list of string with the css property of the size of the number of columns of the DataFrame

    Returns:
        tuple[pd.DataFrame, list[int]]: A Tuple with the DataFrame displayed as first item and a list of rows numbers selected as second item.

    Examples:
        ```python
        conn = st.connection("sql", db_url)

        stmt = (
            select(
                db.Invoice.id,
                db.Invoice.Date,
                db.Invoice.amount,
                db.Client.name,
            )
            .join(db.Client)
            .where(db.Invoice.amount > 1000)
    .       .order_by(db.Invoice.date)
        )

        show_sql_ui(conn=conn,
                    read_instance=stmt,
                    edit_create_model=db.Invoice,
                    available_filter=["name"],
                    rolling_total_column="amount",
        )

        ```


    """
    ui = SqlUi(
        conn=conn,
        read_instance=read_instance,
        edit_create_model=edit_create_model,
        available_filter=available_filter,
        edit_create_default_values=edit_create_default_values,
        rolling_total_column=rolling_total_column,
        read_use_container_width=read_use_container_width,
        hide_id=hide_id,
        base_key=base_key,
        style_fn=style_fn,
        update_show_many=update_show_many,
    )

    return ui.df, ui.rows_selected
