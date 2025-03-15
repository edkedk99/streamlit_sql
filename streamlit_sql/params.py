from datetime import date

import streamlit as st
from sqlalchemy.sql.elements import KeyedColumnElement
from streamlit import session_state as ss

from streamlit_sql.filters import FkOpt


def get_dt_param(colname: str):
    inicio_param = st.query_params.get(f"{colname}_inicio", None)
    if inicio_param == "":
        inicio = None
    else:
        inicio = inicio_param

    final_param = st.query_params.get(f"{colname}_final", None)
    if final_param == "":
        final = None
    else:
        final = final_param

    return inicio, final


def get_no_dt_param(col: KeyedColumnElement, existing: list):
    colname = col.description
    if not colname:
        return None

    param = st.query_params.get(colname, None)
    if not param:
        return None

    if col.type.python_type is str:
        return existing.index(param)

    if col.type.python_type is not int:
        return None

    try:
        idx = int(param)
    except ValueError:
        return None

    index = next((i for i, fk in enumerate(existing) if fk.idx == idx), None)
    return index


def set_dt_param(colname: str, key: str, suffix: str):
    query_key = f"{colname}_{suffix}"
    value = ss[key]
    assert isinstance(value, date)
    value_str = value.strftime("%Y-%m-%d")
    st.query_params[query_key] = value_str


def set_no_dt_param(colname: str, key: str):
    value = ss[key]
    if isinstance(value, str):
        st.query_params[colname] = value
    elif isinstance(value, FkOpt):
        value_str = str(value.idx)
        st.query_params[colname] = value_str
