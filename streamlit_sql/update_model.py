from datetime import date

import streamlit as st
from sqlalchemy import select, update
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.elements import KeyedColumnElement
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from streamlit_datalist import stDatalist

from streamlit_sql.filters import ExistingData
from streamlit_sql.lib import get_pretty_name


def update_state(status: bool, msg: str):
    ss.stsql_update_ok = status
    ss.stsql_update_message = msg
    ss.stsql_opened = True
    ss.stsql_updated += 1
    st.rerun()


class InputFields:
    def __init__(
        self,
        session: Session,
        Model: type[DeclarativeBase],
        key_prefix: str,
    ) -> None:
        self.session = session
        self.Model = Model
        self.key_prefix = key_prefix

        table_name = self.Model.__tablename__
        self.existing_data = ExistingData(
            session=session,
            Model=Model,
        )

    def input_fk(self, col_name: str, value: int | None):
        key = f"{self.key_prefix}_{col_name}"
        opts = self.existing_data.fk[col_name]

        index = next((i for i, opt in enumerate(opts) if opt.idx == value), None)
        input_value = st.selectbox(
            col_name,
            options=opts,
            format_func=lambda opt: opt.name,
            index=index,
            key=key,
        )
        if not input_value:
            return
        return input_value.idx

    def input_str(self, col_name: str, value=None):
        key = f"{self.key_prefix}_{col_name}"
        opts = self.existing_data.text[col_name]

        if value:
            val_index = opts.index(value)
            input_value = stDatalist(col_name, list(opts), index=val_index, key=key)
        else:
            input_value = stDatalist(col_name, list(opts), key=key)

        result = str(input_value)
        return result

    def get_input_value(self, col: KeyedColumnElement, col_value):
        col_name = col.description
        assert col_name is not None
        pretty_name = get_pretty_name(col_name)

        if col.primary_key:
            input_value = col_value
        elif len(col.foreign_keys) > 0:
            input_value = self.input_fk(col_name, col_value)
        elif col.type.python_type is str:
            input_value = self.input_str(col_name, col_value)
        elif col.type.python_type is int:
            input_value = st.number_input(pretty_name, value=col_value, step=1)
        elif col.type.python_type is float:
            input_value = st.number_input(pretty_name, value=col_value, step=0.1)
        elif col.type.python_type is date:
            input_value = st.date_input(pretty_name, value=col_value)
        elif col.type.python_type is bool:
            input_value = st.checkbox(pretty_name, value=col_value)
        else:
            input_value = None

        return input_value


class UpdateRow:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        row_id: int,
        default_values: dict = dict(),
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.row_id = row_id
        self.default_values = default_values

        with conn.session as s:
            self.row = s.get_one(Model, row_id)
            self.input_fields = InputFields(
                s,
                Model,
                "update",
            )

    def get_updates(self):
        cols = self.Model.__table__.columns
        updated = dict()
        for col in cols:
            col_name = col.description
            assert col_name is not None
            col_value = getattr(self.row, col_name)
            default_value = self.default_values.get(col_name)

            if default_value:
                input_value = default_value
            else:
                input_value = self.input_fields.get_input_value(col, col_value)

            updated[col_name] = input_value

        return updated

    def save(self, updated: dict):
        with self.conn.session as s:
            try:
                stmt = (
                    update(self.Model)
                    .where(self.Model.__table__.columns.id == updated["id"])
                    .values(**updated)
                )
                s.execute(stmt)
                s.commit()
                new_row_stmt = select(self.Model).where(
                    self.Model.id == updated["id"]  # pyright: ignore
                )  # pyright: ignore
                new_row = s.execute(new_row_stmt).scalar_one()
                update_state(True, f"Atualizado com sucesso {new_row}")
            except Exception as e:
                update_state(False, str(e))

    def delete(self, idx: int):
        with self.conn.session as s:
            stmt = select(self.Model).where(self.Model.id == idx)  # pyright: ignore
            row = s.execute(stmt).scalar_one()
            row_str = str(row)
            try:
                s.delete(row)
                s.commit()
                update_state(True, f"Deletado com sucesso {row_str}")
            except Exception as e:
                update_state(False, str(e))

    def show(self):
        msg_container = st.empty()

        pretty_name = get_pretty_name(self.Model.__tablename__)
        st.subheader(pretty_name)
        with st.form(f"update_model_form_{pretty_name}", border=False):
            updated = self.get_updates()
            update_btn = st.form_submit_button("Save")

        del_btn = st.button("Delete", key="delete_btn", type="primary")

        if update_btn:
            self.save(updated)

        if del_btn:
            self.delete(self.row_id)

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Edit {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            self.show()

        wrap_show_update()


class CreateRow:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        default_values: dict = dict(),
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.default_values = default_values

        with conn.session as s:
            self.input_fields = InputFields(s, Model, "create")

    def get_fields(self):
        cols = self.Model.__table__.columns
        created = dict()
        for col in cols:
            col_name = col.description
            assert col_name is not None
            default_value = self.default_values.get(col_name)

            if default_value:
                input_value = default_value
            else:
                input_value = self.input_fields.get_input_value(col, None)

            created[col_name] = input_value

        return created

    def show(self, pretty_name: str):
        st.subheader(pretty_name)

        with st.form(f"create_model_form_{pretty_name}", border=False):
            created = self.get_fields()
            create_btn = st.form_submit_button("Save", type="primary")

        if create_btn:
            row = self.Model(**created)
            with self.conn.session as s:
                try:
                    s.add(row)
                    s.commit()
                    update_state(True, f"Criado com sucesso {row}")
                    ss.update = ss.stsql_updated * -1
                except Exception as e:
                    update_state(False, str(e))

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Edit {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            self.show(pretty_name)

        wrap_show_update()
