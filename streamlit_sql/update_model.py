from datetime import date

import streamlit as st
from sqlalchemy import distinct, select
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.schema import Column, Table
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator
from streamlit_datalist import stDatalist

from streamlit_sql import read_model


def show_status(update_ok: bool, message: str, container: DeltaGenerator):
    if update_ok:
        container.info(message)
    else:
        container.error(message)


def get_pretty_name(name: str):
    pretty_name = " ".join(name.split("_")).title()
    return pretty_name


def get_str_opts(_column: Column, _session: Session):
    stmt = select(distinct(_column)).limit(10000)
    rows = _session.execute(stmt).all()
    opts: list[str] = [row[0] for row in rows]
    return opts


def get_fk_opts(_column: Column, _Model, _session: Session):
    fk_iter = iter(_column.foreign_keys)
    fk = next(fk_iter)
    fk_col_name = fk.column.table.name
    fk_model = read_model.get_model_by_name(_Model, fk_col_name)
    fk_table: Table = fk_model.__table__
    fk_pk_col_name = fk_table.primary_key.columns.values()[0].name
    stmt = select(fk_model)
    rows = _session.execute(stmt).all()

    opts: list[tuple[int, str]] = [
        (getattr(row[0], fk_pk_col_name), str(row[0])) for row in rows
    ]
    return opts


def get_opts(_conn: SQLConnection, _Model, table_name: str):
    table_name
    table: Table = _Model.__table__
    cols = table.columns
    opts: dict[str, list] = dict()

    with _conn.session as s:
        for col in cols:
            if len(col.foreign_keys) > 0:
                opts[col.description] = get_fk_opts(col, _Model, s)
            elif col.type.python_type is str:
                opts[col.description] = get_str_opts(col, s)

    return opts


def input_fk(col_name: str, value: int | None, opts: list[tuple[int, str]], key: str):
    index = next((i for i, opt in enumerate(opts) if opt[0] == value), None)
    input_value = st.selectbox(
        col_name,
        options=opts,
        format_func=lambda opt: opt[1],
        index=index,
        key=key,
    )
    if not input_value:
        return
    return input_value[0]


def input_str(col_name, opts: list[str], key: str, value=None):
    if value:
        val_index = opts.index(value)
        input_value = stDatalist(col_name, opts, index=val_index, key=key)
    else:
        input_value = stDatalist(col_name, opts, key=key)

    result = str(input_value)
    return result


def input_number(col_name, step: int | float, key: str, value=None):
    input_value = st.number_input(col_name, value=value, step=step, key=key)
    return input_value


def get_input_value(
    col: Column, col_value, columns_opts: dict[str, list], key_prefix: str
):
    col_name = col.description
    pretty_name = get_pretty_name(col_name)
    key = f"{key_prefix}_{col_name}"

    if col.primary_key:
        input_value = col_value
    elif len(col.foreign_keys) > 0:
        opts = columns_opts[col_name]
        input_value = input_fk(pretty_name, col_value, opts, key)
    elif col.type.python_type is str:
        opts = columns_opts[col_name]
        input_value = input_str(col_name, opts, key, col_value)
    elif col.type.python_type is int:
        input_value = st.number_input(pretty_name, value=col_value, step=1, key=key)
    elif col.type.python_type is float:
        input_value = st.number_input(pretty_name, value=col_value, step=0.1, key=key)
    elif col.type.python_type is date:
        input_value = st.date_input(pretty_name, value=col_value, key=key)
    elif col.type.python_type is bool:
        input_value = st.checkbox(pretty_name, value=col_value, key=key)
    else:
        input_value = None

    return input_value


def save_update(conn: SQLConnection, row):
    with conn.session as s:
        try:
            s.add(row)
            s.commit()
            return (True, "Atualizado com sucesso")
        except Exception as e:
            return (False, str(e))


def delete_update(conn: SQLConnection, Model, idx: int):
    with conn.session as s:
        row = s.get_one(Model, idx)
        try:
            s.delete(row)
            s.commit()
            return (True, "Removido com Sucesso")
        except Exception as e:
            s.rollback()
            return (False, str(e))


def show_update(
    conn: SQLConnection,
    row_id: int,
    Model,
    default_values: dict = dict(),
):
    with conn.session as s:
        row = s.get_one(Model, row_id)

    with st.form("update_model_form", border=False):
        columns_opts = get_opts(conn, Model, Model.__tablename__)
        columns: list[Column] = Model.__table__.columns

        for col in columns:
            col_name = col.description
            col_value = getattr(row, col_name)
            default_value = default_values.get(col_name)

            if default_value:
                input_value = default_value
            else:
                input_value = get_input_value(
                    col,
                    col_value,
                    columns_opts,
                    "update_model_key",
                )
            setattr(row, col_name, input_value)

        msg_container = st.empty()
        update_btn = st.form_submit_button("Save")

    del_btn = st.button("Delete", key="delete_btn", type="primary")

    if update_btn:
        update_ok, message = save_update(conn, row)
        show_status(update_ok, message, msg_container)

    if del_btn:
        update_ok, message = delete_update(conn, Model, row.id)
        show_status(update_ok, message, msg_container)


def show_create(
    conn: SQLConnection,
    Model,
    default_values: dict = dict(),
):
    table_name = Model.__tablename__
    pretty_name = " ".join(table_name.split("_")).title()
    st.write(f"## Add {pretty_name}")

    row_data = dict()
    with st.form("create_model_form", border=False):
        columns_opts = get_opts(conn, Model, Model.__tablename__)
        columns: list[Column] = Model.__table__.columns

        for col in columns:
            col_name = col.description
            if not col.primary_key:
                col_value = default_values.get(col_name)
                input_value = get_input_value(
                    col, col_value, columns_opts, "create_model_key"
                )
                row_data[col_name] = input_value

        create_btn = st.form_submit_button("Save", type="primary")

    if create_btn:
        row = Model(**row_data)
        with conn.session as s:
            s.add(row)
            s.commit()
            st.balloons()
