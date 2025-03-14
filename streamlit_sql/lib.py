import sys
from typing import Literal

import streamlit as st
from loguru import logger
from streamlit import session_state as ss


def log(
    action: Literal["CREATE", "UPDATE", "DELETE"],
    table: str,
    row,
    success: bool = True,
):
    message = "| Action={} | Table={} | Row={}"
    if success:
        logger.info(message, action, table, str(row))
    else:
        logger.error(message, action, table, str(row))


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


if __name__ == "__main__":
    set_logging(False)
    log(action="CREATE", table="tableA", row="rowabc")
    log(action="UPDATE", table="tableB", row="xyzw", success=False)
