# streamlit_sql

## Introduction

This package offers a CRUD frontend to a databse using sqlalchemy. With few lines of code, show the data as table and allow the user to **filter, update and create rows** with many useful features:

### READ

- Add pagination, displaying only a set of rows each time
- Display the string representation of a ForeignKey column (Using __str__ method)
- Select the columns to display to the user
- Add a column to show the rolling sum of a numeric column

### FILTER

- Filter the data by some columns before presenting the table. It can use columns from relationship tables too.
- Let users filter the columns by selecting conditions in the sidebar
- Give possible candidates when filtering using existing values for the columns
- Let users select ForeignKey's values using the string representation of the foreign table

### CREATE / UPDATE / DELETE

- Users create new rows with a dialog opened by clicking the create button
- Users update rows with a dialog opened by clicking on desired row
- Text columns offers previous values in a fizzy search
- ForeignKey columns are added by the string representation and not id number
- Hide columns to fill by offering default values
- Delete button in the UPDATE field

## Requirements

1. streamlit and sqlalchemy
2. Sqlalchemy models needs a __str__ method
2. Id column should be called as "id"
3. Relationships should be added for all ForeignKey columns 


## Basic Usage

Install the package using pip:

```bash
pip install streamlit_sql
```

Define a ModelOpts and add it to the argument of *show_sql_ui* function:

```python
from streamlit_sql import ModelOpts, show_sql_ui

conn = st.connection("sql", url="<db_url>")

model_opts = ModelOpts(MyModel)
show_sql_ui(conn, model_opts)
```


## Customize

You can configure the CRUD interface by giving optional arguments to the ModelOpts object. See its docstring for more information:


| Argument                       | Type                                                | Description                                                                                                                                                                                                                                                                              |
|--------------------------------|-----------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Model**                      | *type[DeclarativeBase]*                             | The SQLAlchemy Model to display.                                                                                                                                                                                                                                                         |
| **rolling_total_column**       | *str*, optional                                     | A numeric column name of the Model. A new column will be displayed with the rolling sum of this column.                                                                                                                                                                                  |
| **filter_by**                  | *list[tuple[InstrumentedAttribute, Any]]*, optional | A list of tuples with pairs of column and value. It filters the rows to display as a `st.dataframe`. Adds to the `WHERE` condition like `select(Model).where(COLUMN == VALUE)`. If the column is from a relationship table, add that SQLAlchemy Model to the `joins_filter_by` argument. |
| **joins_filter_by**            | *list[DeclarativeAttributeIntercept]*, optional     | List of Models that need to join if a relationship column is added in the `filter_by` argument.                                                                                                                                                                                          |
| **columns**                    | *list[str]*, optional                               | Select which columns of the Model to display. Defaults to all columns.                                                                                                                                                                                                                   |
| **edit_create_default_values** | *dict*, optional                                    | A dictionary with column names as keys and default values. When the user clicks to create a row, those columns will not show on the form, and their values will be added to the Model object.                                                                                            |
| **read_use_container_width**   | *bool*, optional                                    | Add `use_container_width` to `st.dataframe` arguments. Defaults to `False`.                                                                                                                                                                                                              |
| **available_sidebar_filter**   | *list[str]*, optional                               | Define which columns the user will be able to filter in the sidebar. Defaults to all.                                                                                                                                                                                                    |

### Example

```python
sales_manager_col = Model.__table__.columns.get("name")
model_opts = ModelOpts(
    Model=Invoice,
    rolling_total_column="amount",
    filter_by=[(sales_manager_col, "John")],
    joins_filter_by=[SalesManager],
    columns=["date", "amount", SalesManager.__tablename__],
    edit_create_default_values=dict(department_id=52),
    read_use_container_width=True,
    available_sidebar_filter=["date", SalesManager.__tablename__]
)
```

## Multiple Models

You can set the model_opts argument to a list of ModelOpts objects. In this case, a st.selectbox will let user to select the table to work on.
