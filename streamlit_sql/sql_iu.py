import pandas as pd
import streamlit as st
from sqlalchemy import CTE, Select, select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections import SQLConnection

from streamlit_sql import lib, read_cte, update_model

OPTS_ITEMS_PAGE = [50, 100, 200, 500, 1000]


def show_sql_ui(
    conn: SQLConnection,
    read_instance,
    edit_create_model: type[DeclarativeBase],
    available_filter: list[str] = list(),
    edit_create_default_values: dict = dict(),
    rolling_total_column: str | None = None,
    read_use_container_width: bool = False,
    hide_id: bool = True,
    base_key: str = "",
):
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

    if isinstance(read_instance, Select):
        cte = read_instance.cte()
    elif isinstance(read_instance, CTE):
        cte = read_instance
    else:
        cte = select(read_instance).cte()

    lib.set_state("stsql_updated", 1)
    lib.set_state("stsql_update_ok", None)
    lib.set_state("stsql_update_message", None)
    lib.set_state("stsql_opened", False)

    header_container = st.container()
    data_container = st.container()
    pag_container = st.container()

    table_name = lib.get_pretty_name(edit_create_model.__tablename__)
    header_container.header(table_name, divider="orange")

    expander_container = header_container.expander(
        "Filter",
        icon=":material/search:",
    )
    filter_container = header_container.container()

    saldo_toggle_col, saldo_value_col = header_container.columns(2)
    btns_container = header_container.container()

    if ss.stsql_update_ok is True:
        header_container.success(ss.stsql_update_message, icon=":material/thumb_up:")
    if ss.stsql_update_ok is False:
        header_container.error(ss.stsql_update_message, icon=":material/thumb_down:")

    filter_colsname = available_filter
    if len(filter_colsname) == 0:
        filter_colsname = [col.description for col in cte.columns if col.description]

    with conn.session as s:
        existing = read_cte.get_existing_values(
            _session=s,
            cte=cte,
            updated=ss.stsql_updated,
            available_col_filter=filter_colsname,
        )

    col_filter = read_cte.ColFilter(
        expander_container,
        cte,
        existing,
        filter_colsname,
        base_key,
    )
    if str(col_filter) != "":
        filter_container.write(col_filter)

    stmt_no_pag = read_cte.get_stmt_no_pag(cte, col_filter)

    qtty_rows = read_cte.get_qtty_rows(conn, stmt_no_pag)
    with pag_container:
        items_per_page, page = read_cte.show_pagination(
            qtty_rows, OPTS_ITEMS_PAGE, base_key
        )

    stmt_pag = read_cte.get_stmt_pag(stmt_no_pag, items_per_page, page)

    with conn.session as s:
        c = s.connection()
        df = pd.read_sql(stmt_pag, c)
        if rolling_total_column is not None:
            if df.empty:
                first_row_id = None
            else:
                first_row_id = int(df.iloc[0].id)

            no_dt_filters = col_filter.no_dt_filters
            stmt_no_pag_dt = read_cte.get_stmt_no_pag_dt(cte, no_dt_filters)

            initial_balance = read_cte.initial_balance(
                _session=s,
                stmt_no_pag_dt=stmt_no_pag_dt,
                col_filter=col_filter,
                rolling_total_column=rolling_total_column,
                first_row_id=first_row_id,
            )
        else:
            initial_balance = 0

    if rolling_total_column:
        rolling_pretty_name = lib.get_pretty_name(rolling_total_column)

        saldo_toogle = saldo_toggle_col.toggle(
            "Adiciona Saldo Devedor", value=True, key=f"{base_key}_saldo_toggle_sql_ui"
        )

        if not saldo_toogle:
            initial_balance = 0

        saldo_value_col.subheader(
            f"Saldo Anterior {rolling_pretty_name}: {initial_balance:,.2f}"
        )

        rolling_col_name = f"Balance {rolling_pretty_name}"
        df[rolling_col_name] = df[rolling_total_column].cumsum() + initial_balance

    if df.empty:
        st.header(":red[Tabela Vazia]")
        return

    df.columns = df.columns.astype("str")

    column_order = None
    if hide_id:
        column_order = [colname for colname in df.columns if colname != "id"]

    selection_state = data_container.dataframe(
        df,
        use_container_width=read_use_container_width,
        height=650,
        hide_index=True,
        column_order=column_order,
        on_select="rerun",
        selection_mode="multi-row",
        key=f"{base_key}_df_sql_ui",
    )

    rows_pos = []
    if "selection" in selection_state and "rows" in selection_state["selection"]:
        rows_pos = selection_state["selection"]["rows"]

    qtty_rows = len(rows_pos)

    action = update_model.action_btns(btns_container, qtty_rows, ss.stsql_opened)

    if action == "add":
        create_row = update_model.CreateRow(
            conn=conn,
            Model=edit_create_model,
            default_values=edit_create_default_values,
        )
        create_row.show_dialog()
    elif action == "edit":
        selected_pos = rows_pos[0]
        row_id = int(df.iloc[selected_pos]["id"])
        update_row = update_model.UpdateRow(
            conn=conn,
            Model=edit_create_model,
            row_id=row_id,
            default_values=edit_create_default_values,
        )
        update_row.show_dialog()
    elif action == "delete":
        rows_id = df.iloc[rows_pos].id.astype(int).to_list()
        delete_rows = update_model.DeleteRows(
            conn=conn,
            Model=edit_create_model,
            rows_id=rows_id,
        )
        delete_rows.show_dialog()
        pass

    ss.stsql_opened = False
    return df, rows_pos
