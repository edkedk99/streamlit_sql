from streamlit.connections import SQLConnection

from streamlit_sql.sql_ui import ModelOpts, show_page


def show_sql_ui(conn: SQLConnection, model_opts: ModelOpts | list[ModelOpts]):
    data = show_page(conn, model_opts)
    return data
