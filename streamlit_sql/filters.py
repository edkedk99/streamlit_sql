from copy import copy
from dataclasses import dataclass
from datetime import date
from operator import and_
from typing import Any

import streamlit as st
from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, func, or_
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.selectable import Select
from streamlit.connections.sql_connection import SQLConnection


@dataclass
class FkOpts:
    idx: int
    name: str


@dataclass
class FilterOpts:
    text: dict[str, list[str]]
    dt: dict[str, tuple[date, date]]
    fk: dict[str, list[FkOpts]]


def get_dt_column(s: Session, column: Column):
    min_default = date.today() - relativedelta(days=30)
    min_dt: date = s.query(func.min(column)).scalar() or min_default
    max_dt: date = s.query(func.max(column)).scalar() or date.today()

    return (min_dt, max_dt)


def get_dt_opts(_session: Session, Model):
    columns: list[Column] = Model.__table__.columns
    dts: dict[str, tuple[date, date]] = {
        column.description: get_dt_column(_session, column)
        for column in columns
        if column.type.python_type == date
    }

    return dts


def get_foreign_opt(session: Session, Model, foreign_key: ForeignKey):
    reg_values = Model.registry._class_registry.values()
    has_table = [reg for reg in reg_values if hasattr(reg, "__tablename__")]

    foreign_table_name = foreign_key.column.table.name
    model = next(reg for reg in has_table if reg.__tablename__ == foreign_table_name)
    fk_pk_name = foreign_key.column.description

    rows = session.query(model).limit(10000)
    opts: list[FkOpts] = [FkOpts(0, "ALL")]
    for row in rows:
        idx = getattr(row, fk_pk_name)
        format_str = str(row)
        fk_opt = FkOpts(idx, format_str)
        opts.append(fk_opt)

    return opts


def get_foreign_opts(session: Session, Model):
    cols: list[Column] = list(Model.__table__.columns)
    fk_cols = [col for col in cols if len(list(col.foreign_keys))]
    relation = [(col.description, list(col.foreign_keys)[0]) for col in fk_cols]

    opts = {rel[0]: get_foreign_opt(session, Model, rel[1]) for rel in relation}
    return opts


def get_options_column(s: Session, column: Column):
    rows = s.query(column).distinct().limit(10000).all()
    values = [row[0] for row in rows]
    values = ["ALL", *values]
    return values


def get_str_opts(_session: Session, Model):
    columns: list[Column] = Model.__table__.columns
    options: dict[str, list] = {
        column.description: get_options_column(_session, column)
        for column in columns
        if column.type.python_type is str
    }

    return options


def get_filter_opts(conn: SQLConnection, Model):
    with conn.session as s:
        str_opts = get_str_opts(s, Model)
        dt_opts = get_dt_opts(s, Model)
        fk_opts = get_foreign_opts(s, Model)

    opts = FilterOpts(str_opts, dt_opts, fk_opts)
    return opts


def date_filter(label: str, min_value: date, max_value: date):
    container = st.sidebar.container(border=True)
    container.write(label)
    inicio_c, final_c = container.columns(2)
    inicio = inicio_c.date_input(
        "Inicio",
        key=f"date_filter_inicio_{label}",
        value=min_value,
        min_value=min_value,
        max_value=max_value,
    )
    final = final_c.date_input(
        "Final",
        key=f"date_filter_final_{label}",
        value=max_value,
        min_value=min_value,
        max_value=max_value,
    )
    return (inicio, final)


def add_not_all(stmt: Select, column: Column, value: Any | None):
    new_stmt = copy(stmt)
    if not value:
        return new_stmt
    if value == "ALL":
        return new_stmt

    new_stmt = new_stmt.where(column == value)
    return new_stmt


def get_filters(
    Model,
    stmt: Select,
    cols_name: list[str],
    filter_opts: FilterOpts,
):
    new_stmt: Select = copy(stmt)

    cols: list[Column] = Model.__table__.columns
    for col in cols:
        is_pk = col.primary_key
        is_filter_by = col.description in cols_name
        is_fk = len(col.foreign_keys) > 0
        col_name = col.description
        if is_pk or is_filter_by:
            pass
        elif is_fk:
            opts = filter_opts.fk[col_name]
            value = st.sidebar.selectbox(
                col_name, options=opts, format_func=lambda opt: opt.name
            )
            value_filter = value.idx if value else None

            new_stmt = add_not_all(new_stmt, col, value_filter)
        elif col.type.python_type is str:
            opts = filter_opts.text[col_name]
            value = st.sidebar.selectbox(col_name, options=opts)
            new_stmt = add_not_all(new_stmt, col, value)
        elif col.type.python_type is int:
            value = st.sidebar.number_input(col_name, step=1, value=None)
            new_stmt = add_not_all(new_stmt, col, value)
        elif col.type.python_type is float:
            value = st.sidebar.number_input(col_name, step=0.1, value=None)
            new_stmt = add_not_all(new_stmt, col, value)
        elif col.type.python_type == date:
            min_value, max_value = filter_opts.dt[col_name]
            value = date_filter(col_name, min_value, max_value)
            new_stmt = new_stmt.where(
                or_(and_(col >= value[0], col <= value[1]), col.is_(None))
            )

    return new_stmt
