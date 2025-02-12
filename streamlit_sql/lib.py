import sys

import streamlit as st
from loguru import logger
from streamlit import session_state as ss

log = logger.bind(name="streamlit_sql")


def set_logging(disable_log: bool):
    if disable_log:
        logger.disable("streamlit_sql")
        return

    logger.enable("streamlit_sql")

    if not logger._core.handlers:  # pyright: ignore
        logger.add(sys.stderr, level="INFO")


def set_state(key: str, value):
    if key not in ss:
        ss[key] = value


@st.cache_data
def get_pretty_name(name: str):
    pretty_name = " ".join(name.split("_")).title()
    return pretty_name
