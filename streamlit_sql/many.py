import pandas as pd
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.orm import RelationshipProperty, Session
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql import lib, read_cte
from streamlit_sql.create_delete_model import CreateRow, DeleteRows


class ReadManyRel:
    def __init__(
        self,
        session: Session,
        Model,
        model_id: int,
        rel: RelationshipProperty,
    ) -> None:
        self.session = session
        self.Model = Model
        self.model_id = model_id
        self.rel = rel

    @property
    def other_model(self):
        pairs = self.rel.local_remote_pairs
        assert pairs is not None
        other_col = pairs[0][1]
        other_colname: str = other_col.table.name
        mappers = self.Model.registry.mappers

        other_model = next(
            mapper.class_
            for mapper in mappers
            if mapper
            if mapper.class_.__tablename__ == other_colname
        )
        return other_model

    @property
    def base_stmt(self):
        pairs = self.rel.local_remote_pairs
        assert pairs is not None
        other_col = pairs[0][1]
        stmt = select(self.other_model.id, self.other_model)

        if self.Model != self.other_model:
            stmt = stmt.join(self.Model, self.Model.id == other_col)

        stmt = stmt.where(other_col == self.model_id)
        return stmt

    @property
    def qtty_rows(self):
        subq = self.base_stmt.subquery()
        stmt = select(func.count(subq.c.id))
        qtty = self.session.execute(stmt).scalar_one()
        return qtty

    def get_rows(self):
        stmt = select(self.other_model)
        rows = self.session.execute(stmt)
        rows_list = [str(row) for row in rows]
        return rows_list

    def get_stmt_pag(self, items_per_page: int, page: int):
        offset = (page - 1) * items_per_page
        stmt = self.base_stmt.offset(offset).limit(items_per_page)
        return stmt

    def show_pagination(self):
        OPTS_ITEMS_PAGE = [50, 100, 200, 500, 1000]
        model_name: str = self.Model.__table__.name
        pairs = self.rel.local_remote_pairs
        assert pairs is not None
        other_colname = pairs[0][1].name
        target_name = str(self.rel.target)
        items_per_page, page = read_cte.show_pagination(
            self.qtty_rows,
            OPTS_ITEMS_PAGE,
            base_key=f"stsql_read_many_rel_{model_name}_{other_colname}_{target_name}",
        )

        return items_per_page, page

    def get_data(self, items_per_page: int, page: int):
        stmt = self.get_stmt_pag(items_per_page, page)
        rows = self.session.execute(stmt)

        result: list[tuple[int, str]] = [(row[0], str(row[1])) for row in rows]
        return result


class ShowRels:
    def __init__(self, conn: SQLConnection, Model, model_id: int) -> None:
        self.Model = Model
        self.model_id = model_id
        self.conn = conn

        with conn.session as s:
            self.show_rels(s)

    def get_other_col(self, rel: RelationshipProperty):
        pairs = rel.local_remote_pairs
        assert pairs is not None
        other_col = pairs[0][1]
        return other_col

    def get_other_model(self, rel: RelationshipProperty):
        other_col = self.get_other_col(rel)
        other_colname: str = other_col.table.name
        mappers = self.Model.registry.mappers

        other_model = next(
            mapper.class_
            for mapper in mappers
            if mapper
            if mapper.class_.__tablename__ == other_colname
        )
        return other_model

    def show_create(self, rel: RelationshipProperty):
        other_model = self.get_other_model(rel)
        other_col = self.get_other_col(rel)
        other_colname = other_col.name
        default_values = {other_colname: self.model_id}
        model_name = other_model.__table__.name
        create_row = CreateRow(
            self.conn,
            other_model,
            default_values,
            f"stsql_create_many_{other_colname}_{model_name}",
        )

        pretty_name = lib.get_pretty_name(other_model.__table__.name)
        create_row.show(pretty_name)

    def show_delete(
        self, df: pd.DataFrame, rows_pos: list[int], rel: RelationshipProperty
    ):
        df_del = df.iloc[rows_pos]
        rows_id = df_del.index.to_list()
        if len(rows_id) == 0:
            st.text("Selecione antes na outra aba as linhas para apagar.")
        else:
            other_model = self.get_other_model(rel)
            other_model_name = other_model.__table__.name
            model_name = self.Model.__table__.name
            delete_rows = DeleteRows(
                self.conn,
                other_model,
                rows_id,
                f"stsql_delete_rows_{model_name}_{other_model_name}",
            )

            delete_rows.show(df.columns[0])

    @st.fragment
    def show_rel(self, session: Session, rel: RelationshipProperty):
        read_many_rel = ReadManyRel(session, self.Model, self.model_id, rel)
        qtty_rows = read_many_rel.qtty_rows

        other_colname = self.get_other_col(rel).name
        other_colname = (
            other_colname[:-3] if other_colname.endswith("_id") else other_colname
        )
        target_name = str(rel.target)
        exp_name = f"{target_name} - {other_colname}"
        pretty_name = lib.get_pretty_name(exp_name)

        with st.expander(pretty_name):
            tab_read, tab_create, tab_delete = st.tabs(["Read", "Create", "Delete"])
            data_container = tab_read.container()
            pag_container = tab_read.container()

            with pag_container:
                items_per_page, page = read_many_rel.show_pagination()

            with data_container:
                data = read_many_rel.get_data(items_per_page, page)
                df = pd.DataFrame(data, columns=["id", pretty_name]).set_index(
                    "id", drop=True
                )
                other_colname = self.get_other_col(rel).name
                target_name = str(rel.target)
                df_key = f"stsql_many_{self.Model.__table__.name}_{other_colname}_{target_name}"
                selection_state = st.dataframe(
                    df,
                    hide_index=True,
                    use_container_width=True,
                    selection_mode="multi-row",
                    on_select="rerun",
                    key=df_key,
                )

                rows_pos = []
                if (
                    "selection" in selection_state
                    and "rows" in selection_state["selection"]
                ):
                    rows_pos = selection_state["selection"]["rows"]

            with tab_create:
                self.show_create(rel)
            with tab_delete:
                self.show_delete(df, rows_pos, rel)

    def show_rels(self, session: Session):
        rels = [
            rel
            for rel in self.Model.__mapper__.relationships
            if rel.direction.value == 1
        ]

        for rel in rels:
            self.show_rel(session, rel)
