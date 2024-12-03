from streamlit.connections import SQLConnection

from streamlit_sql.sql_ui import ModelOpts, show_page


def show_sql_ui(conn: SQLConnection, model_opts: ModelOpts | list[ModelOpts]):
    """Show A CRUD interface in a Streamlit Page

    Args:
        conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
        model_opts (ModelOpts | list[ModelOpts]): ModelOpts is a dataclass with the sqlalchemy Model and optional configuration on how to display the CRUD interface. If a single ModelOpts, show the crud interface for this Model. If a list, show a st.selectbox to choose the Model

    """
    data = show_page(conn, model_opts)
    return data
