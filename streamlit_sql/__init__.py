import streamlit as st
from streamlit import session_state as ss
from streamlit.connections import SQLConnection

from streamlit_sql.lib import get_pretty_name, set_state
from streamlit_sql.sql_ui import ModelOpts, ShowPage


def show_page(conn: SQLConnection, model_opts: ModelOpts | list[ModelOpts]):
    if isinstance(model_opts, ModelOpts):
        ShowPage(conn, model_opts)
    else:
        set_state("last_model_index", 0)
        model_index: int = ss.last_model_index

        model_opts_selected = st.selectbox(
            "Table",
            options=model_opts,
            index=model_index,
            format_func=lambda model_opts: get_pretty_name(
                model_opts.Model.__tablename__
            ),
        )

        ShowPage(conn, model_opts_selected)
