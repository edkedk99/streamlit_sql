from sqlalchemy.orm import DeclarativeBase
from streamlit.connections import SQLConnection

from streamlit_sql.create_delete_model import CreateRow
from streamlit_sql.lib import get_pretty_name
from streamlit_sql.sql_iu import SqlUi, show_sql_ui
from streamlit_sql.update_model import UpdateRow

__all__ = ["SqlUi", "show_create", "show_sql_ui"]


def show_create(
    conn: SQLConnection,
    Model: type[DeclarativeBase],
    default_values: dict | None = None,
):
    """Show a form to add a new row to the database table of the choosen sqlalchemy Model

    This function should be used to just show a form and a button to add a row to the table without the other features of this package

    Args:
        conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
        Model (type[DeclarativeBase]): The sqlalchemy Model of the table
        default_values (dict, optional): A dict with column name as keys and values to be default. The form will not display those columns and its value will be added to the Model object

    """
    if default_values is None:
        default_values = {}

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
    default_values: dict | None = None,
):
    """Show a form to update or delete a row to the database table of the choosen sqlalchemy Model

    This function should be used to just show a form and buttons to update or delete a row to the table without the other features of this package

    Args:
        conn (SQLConnection): A sqlalchemy connection created with st.connection(\"sql\", url=\"<sqlalchemy url>\")
        Model (type[DeclarativeBase]): The sqlalchemy Model of the table
        default_values (dict, optional): A dict with column name as keys and values to be default. The form will not display those columns and its value will be added to the Model object

    """
    if default_values is None:
        default_values = {}

    update_row = UpdateRow(
        conn=conn,
        Model=Model,
        row_id=row_id,
        default_values=default_values,
    )
    update_row.show()
