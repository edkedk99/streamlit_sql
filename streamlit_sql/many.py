from functools import cached_property

import pandas as pd
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.orm import RelationshipProperty, Session
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql import lib, read_cte
from streamlit_sql.create_delete_model import CreateRow, DeleteRows


class ReadManyRel:
    OPTS_ITEMS_PAGE = (50, 100, 200, 500, 1000)

    def __init__(
        self,
        Model,
        model_id: int,
        rel: RelationshipProperty,
    ) -> None:
        self.Model = Model
        self.model_id = model_id
        self.rel = rel

    @cached_property
    def other_col(self):
        pairs = self.rel.local_remote_pairs
        assert pairs is not None
        col = pairs[0][1]
        return col

    @cached_property
    def other_colname_noid(self):
        if self.other_col.name.endswith("_id"):
            name = self.other_col.name[:-3]
        else:
            name = self.other_col.name

        return name

    @cached_property
    def other_model(self):
        other_col = self.other_col
        other_colname: str = other_col.table.name
        mappers = self.Model.registry.mappers

        other_model = next(
            mapper.class_
            for mapper in mappers
            if mapper
            if mapper.class_.__tablename__ == other_colname
        )
        return other_model

    @cached_property
    def suffix_key(self):
        model_name: str = self.Model.__table__.name
        key = f"{model_name}_{self.other_col.name}_{self.rel.target}"
        return key

    @property
    def base_stmt(self):
        stmt = select(self.other_model.id, self.other_model)

        if self.Model != self.other_model:
            stmt = stmt.join(self.Model, self.Model.id == self.other_col)

        stmt = stmt.where(self.other_col == self.model_id)
        return stmt

    def get_qtty_rows(self, session: Session):
        subq = self.base_stmt.subquery()
        stmt = select(func.count(subq.c.id))
        qtty = session.execute(stmt).scalar_one()
        return qtty

    def get_stmt_pag(self, items_per_page: int, page: int):
        offset = (page - 1) * items_per_page
        stmt = self.base_stmt.offset(offset).limit(items_per_page)
        return stmt

    def get_data(self, session: Session, items_per_page: int, page: int):
        stmt = self.get_stmt_pag(items_per_page, page)
        rows = session.execute(stmt)

        result: list[tuple[int, str]] = [(row[0], str(row[1])) for row in rows]
        return result


@st.fragment
def show_rel(conn: SQLConnection, Model, model_id: int, rel: RelationshipProperty):
    read_many_rel = ReadManyRel(Model, model_id, rel)

    exp_name = f"{rel.target} - {read_many_rel.other_col.name}"
    pretty_name = lib.get_pretty_name(exp_name)

    with st.expander(pretty_name):
        tab_read, tab_create, tab_delete = st.tabs(["Read", "Create", "Delete"])
        data_container = tab_read.container()
        pag_container = tab_read.container()

    with pag_container, conn.session as s:
        qtty_rows = read_many_rel.get_qtty_rows(s)
        items_per_page, page = read_cte.show_pagination(
            qtty_rows,
            read_many_rel.OPTS_ITEMS_PAGE,
            base_key=f"stsql_read_many_pag_{read_many_rel.suffix_key}",
        )

        data = read_many_rel.get_data(s, items_per_page, page)

    with data_container:
        df = pd.DataFrame(data, columns=["id", pretty_name]).set_index("id", drop=True)
        selection_state = st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            selection_mode="multi-row",
            on_select="rerun",
            key=f"stsql_many_df_{read_many_rel.suffix_key}",
        )

        rows_pos = []
        if "selection" in selection_state and "rows" in selection_state["selection"]:
            rows_pos = selection_state["selection"]["rows"]

        with tab_create:
            default_values = {read_many_rel.other_col.name: model_id}
            create_row = CreateRow(
                conn,
                read_many_rel.other_model,
                default_values,
                f"stsql_create_many_{read_many_rel.suffix_key}",
            )
            create_row.show(pretty_name)

        with tab_delete:
            rows_id = df.iloc[rows_pos].index.to_list()
            if len(rows_id) == 0:
                st.text("Selecione antes na outra aba as linhas para apagar.")
            else:
                delete_rows = DeleteRows(
                    conn,
                    read_many_rel.other_model,
                    rows_id,
                    f"st_sql_many_delete_{read_many_rel.suffix_key}",
                )
                delete_rows.show(pretty_name)


def show_rels(conn: SQLConnection, Model, model_id: int):
    rels = [rel for rel in Model.__mapper__.relationships if rel.direction.value == 1]

    for rel in rels:
        show_rel(conn, Model, model_id, rel)
