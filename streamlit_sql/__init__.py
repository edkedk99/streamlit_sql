from sqlalchemy.orm import DeclarativeBase
from streamlit.connections import SQLConnection

from streamlit_sql.lib import get_pretty_name
from streamlit_sql.sql_ui import ModelOpts, show_page
from streamlit_sql.update_model import CreateRow, UpdateRow

__all__ = ["show_sql_ui", "ModelOpts", "show_create", "show_update"]


def show_sql_ui(conn: SQLConnection, model_opts: ModelOpts | list[ModelOpts]):
    """Show A CRUD interface in a Streamlit Page

    Args:
        conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
        model_opts (ModelOpts | list[ModelOpts]): ModelOpts is a dataclass with the sqlalchemy Model and optional configuration on how to display the CRUD interface. If a single ModelOpts, show the crud interface for this Model. If a list, show a st.selectbox to choose the Model

    """
    data = show_page(conn, model_opts)
    return data


def show_create(
    conn: SQLConnection,
    Model: type[DeclarativeBase],
    default_values: dict = dict(),
):
    """Show a form to add a new row to the database table of the choosen sqlalchemy Model

    This function should be used to just show a form and a button to add a row to the table without the other features of this package

    Args:
        conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
        Model (type[DeclarativeBase]): The sqlalchemy Model of the table
        default_values (dict, optional): A dict with column name as keys and values to be default. The form will not display those columns and its value will be added to the Model object

    """
    create_row = CreateRow(
        conn=conn,
        Model=Model,
        default_values=default_values,
    )
    pretty_name = get_pretty_name(Model.__tablename__)
    create_row.show(pretty_name)


def show_update(
    conn: SQLConnection,
    Model: type[DeclarativeBase],
    row_id: int,
    default_values: dict = dict(),
):
    """Show a form to update or delete a row to the database table of the choosen sqlalchemy Model

    This function should be used to just show a form and buttons to update or delete a row to the table without the other features of this package

    Args:
        conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
        Model (type[DeclarativeBase]): The sqlalchemy Model of the table
        default_values (dict, optional): A dict with column name as keys and values to be default. The form will not display those columns and its value will be added to the Model object

    """
    update_row = UpdateRow(
        conn=conn,
        Model=Model,
        row_id=row_id,
        default_values=default_values,
    )
    update_row.show()
