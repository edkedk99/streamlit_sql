# streamlit_sql

## Introduction

This package shows a CRUD frontend to a database using sqlalchemy in a streamlit app. With just one line of code, show the data as table and allow the user to **read, filter, update, create and delete rows** with many useful features.

## Demo

See the package in action [here](https://example-crud.streamlit.app/).

## Features

### READ

- Display as a regular st.dataframe
- Add pagination, displaying only a set of rows each time
- Set the dataframe to be displayed using standard sqlalchemy select statement, where you can JOIN, ORDER BY, WHERE, etc.
- Add a column to show the rolling sum of a numeric column
- Conditional styling if the DataFrame based on each row value. For instance, changing its background color

### FILTER

- Filter the data by some columns before presenting the table.
- Let users filter the columns by selecting conditions in the filter expander
- Give possible candidates when filtering using existing values for the columns
- Let users select ForeignKey's values using the string representation of the foreign table, instead of its id number

### UPDATE

- Users update rows with a dialog opened by selecting the row and clicking the icon
- Text columns offers candidates from existing values
- ForeignKey columns are added by the string representation instead of its id number
- In Update form, list all ONE-TO-MANY related rows with pagination, where you can directly create and delete related table rows. 


### CREATE

- Users create new rows with a dialog opened by clicking the create button
- Text columns offers candidates from existing values
- Hide columns to fill by offering default values
- ForeignKey columns are added by the string representation instead of its id number

### DELETE

- Delete one or multiple rows by selecting in DataFrame and clicking the corresponding button. I dialog will list selected rows and confirm deletion.



## Requirements

All the requirements you should probably have anyway.

1. streamlit and sqlalchemy
2. Sqlalchemy models needs a __str__ method
2. Id column should be called "id"
3. Relationships should be added for all ForeignKey columns 


## Basic Usage

Install the package using pip:

```bash
pip install streamlit_sql
```

Run `show_sql_ui` as the example below:

```python
from streamlit_sql import show_sql_ui
from sqlalchemy import select

conn = st.connection("sql", url="<db_url>")

stmt = (
    select(
        db.Invoice.id,
        db.Invoice.Date,
        db.Invoice.amount,
        db.Client.name,
    )
    .join(db.Client)
    .where(db.Invoice.amount > 1000)
    .order_by(db.Invoice.date)
)

show_sql_ui(conn=conn,
            read_instance=stmt,
            edit_create_model=db.Invoice,
            available_filter=["name"],
            rolling_total_column="amount",
)

show_sql_ui(conn, model_opts)
```

!!! warning
    In the statement, **always** include the primary_key column, that should be named *id*

### Interface

- Filter: Open the "Filter" expander and fill the inputs
- Add row: Click on "plus" button (no dataframe row can be selected)
- Edit row: Click on "pencil" button (one and only one dataframe row should be selected)
- Delete row: Click on "trash" button (one or more dataframe rows should be selected)


## Customize

You can adjust the CRUD interface by the select statement you provide to *read_instance* arg and giving optional arguments to the *show_sql_ui* function. See the docstring for more information or at [documentation webpage](https://edkedk99.github.io/streamlit_sql/api/#streamlit_sql.show_sql_ui):


## Only create or update form

You can display just a create or update/delete form without the read interface using functions *show_updade*, and *show_create*.
