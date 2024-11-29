import streamlit as st
from streamlit import session_state as ss
from streamlit.elements.arrow import DataframeState


def set_state(key: str, value):
    if key not in ss:
        ss[key] = value


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


@st.cache_data
def get_pretty_name(name: str):
    pretty_name = " ".join(name.split("_")).title()
    return pretty_name
