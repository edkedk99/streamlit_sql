from datetime import date

import streamlit as st
from sqlalchemy import delete, select, update
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.elements import KeyedColumnElement
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection
from streamlit.delta_generator import DeltaGenerator
from streamlit_datalist import stDatalist

from streamlit_sql.filters import ExistingData
from streamlit_sql.lib import get_pretty_name, set_state


def update_state(status: bool, msg: str):
    ss.stsql_update_ok = status
    ss.stsql_update_message = msg
    ss.stsql_opened = True
    ss.stsql_updated += 1
    st.rerun()


class InputFields:
    def __init__(
        self,
        Model: type[DeclarativeBase],
        key_prefix: str,
        default_values: dict,
        existing_data: ExistingData,
    ) -> None:
        self.Model = Model
        self.key_prefix = key_prefix
        self.default_values = default_values
        self.existing_data = existing_data

        table_name = self.Model.__tablename__

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

    def get_col_str_opts(self, col_name: str, value: str | None):
        opts = list(self.existing_data.text[col_name])
        if value is None:
            return None, opts

        try:
            val_index = opts.index(value)
            return val_index, opts
        except ValueError:
            opts.append(value)
            val_index = len(opts) - 1
            return val_index, opts

    def input_str(self, col_name: str, value=None):
        key = f"{self.key_prefix}_{col_name}"
        val_index, opts = self.get_col_str_opts(col_name, value)
        input_value = stDatalist(
            col_name,
            list(opts),
            index=val_index,  # pyright: ignore
            key=key,
        )
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

        set_state("stsql_updated", 0)

        with conn.session as s:
            self.row = s.get_one(Model, row_id)
            self.existing_data = ExistingData(s, Model, default_values, self.row)

        self.input_fields = InputFields(
            Model, "update", default_values, self.existing_data
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
                input_value = col_value
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
                return True, f"Atualizado com sucesso {new_row}"
            except Exception as e:
                return False, str(e)

    def show(self):
        msg_container = st.empty()

        pretty_name = get_pretty_name(self.Model.__tablename__)
        st.subheader(pretty_name)
        with st.form(f"update_model_form_{pretty_name}", border=False):
            updated = self.get_updates()
            update_btn = st.form_submit_button("Save")

        if update_btn:
            ss.stsql_updated += 1
            return self.save(updated)
        else:
            return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Edit {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show()

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

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

        set_state("stsql_updated", 0)

        with conn.session as s:
            self.existing_data = ExistingData(s, Model, default_values)
            self.input_fields = InputFields(
                Model, "create", default_values, self.existing_data
            )

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
                    ss.stsql_updated += 1
                    return True, f"Criado com sucesso {row}"
                except Exception as e:
                    ss.stsql_updated += 1
                    return False, str(e)
        else:
            return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Create {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()


class DeleteRows:
    def __init__(
        self, conn: SQLConnection, Model: type[DeclarativeBase], rows_id: list[int]
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.rows_id = rows_id

    @st.cache_data
    def get_rows_str(_self, rows_id: list[int]):
        id_col = _self.Model.__table__.columns.get("id")
        assert id_col is not None
        stmt = select(_self.Model).where(id_col.in_(rows_id))

        with _self.conn.session as s:
            rows = s.execute(stmt).scalars()
            rows_str = [str(row) for row in rows]

        return rows_str

    def show(self, pretty_name):
        st.subheader("Apagar items abaixo?")

        rows_str = self.get_rows_str(self.rows_id)
        items = "\n\n".join(rows_str)
        st.dataframe({pretty_name: rows_str}, hide_index=True)

        btn = st.button("Delete")
        if btn:
            id_col = self.Model.__table__.columns.get("id")
            assert id_col is not None
            stmt_del = delete(self.Model).where(id_col.in_(self.rows_id))
            with self.conn.session as s:
                try:
                    s.execute(stmt_del)
                    s.commit()
                    ss.stsql_updated += 1
                    qtty = len(self.rows_id)
                    return True, f"Deletado com sucesso {qtty} registros"
                except Exception as e:
                    ss.stsql_updated += 1
                    return False, str(e)
        else:
            return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Delete {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()


def action_btns(container: DeltaGenerator, qtty_selected: int, opened: bool):
    set_state("stsql_action", "")
    disabled_add = qtty_selected > 0
    disabled_edit = qtty_selected != 1
    disabled_delete = qtty_selected == 0

    with container:
        add_col, edit_col, del_col, empty_col = st.columns([1, 1, 1, 6])

        add_btn = add_col.button(
            "",
            help="Add",
            icon=":material/add:",
            type="secondary",
            disabled=disabled_add,
            use_container_width=True,
        )

        edit_btn = edit_col.button(
            "",
            help="Edit",
            icon=":material/edit:",
            type="secondary",
            disabled=disabled_edit,
            use_container_width=True,
        )

        del_btn = del_col.button(
            "",
            help="Delete",
            icon=":material/delete:",
            type="primary",
            disabled=disabled_delete,
            use_container_width=True,
        )

        if opened:
            return None
        elif add_btn:
            return "add"
        elif edit_btn:
            return "edit"
        elif del_btn:
            return "delete"
