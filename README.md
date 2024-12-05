# streamlit_sql

## Introduction

This package shows a CRUD frontend to a database using sqlalchemy in a streamlit app. With few lines of code, show the data as table and allow the user to **read, filter, update, create and delete rows** with many useful features.

## Demo

See the package in action [here](https://example-crud.streamlit.app/).

## Features

### READ

- Display as a regular st.dataframe
- Add pagination, displaying only a set of rows each time
- Display the string representation of a ForeignKey column (Using __str__ method), instead of its id number
- Select the columns to display to the user
- Add a column to show the rolling sum of a numeric column

### FILTER

- Filter the data by some columns before presenting the table. It can use columns from relationship tables too.
- Let users filter the columns by selecting conditions in the sidebar
- Give possible candidates when filtering using existing values for the columns
- Let users select ForeignKey's values using the string representation of the foreign table, instead of its id number

### CREATE / UPDATE / DELETE

- Users create new rows with a dialog opened by clicking the create button
- Users update rows with a dialog opened by clicking on desired row
- Text columns offers candidates from existing values
- ForeignKey columns are added by the string representation instead of its id number
- Hide columns to fill by offering default values
- Delete button in the UPDATE field

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

Define a ModelOpts and add it to the argument of *show_sql_ui* function:

```python
from streamlit_sql import ModelOpts, show_sql_ui

conn = st.connection("sql", url="<db_url>")

model_opts = ModelOpts(MyModel)
show_sql_ui(conn, model_opts)
```


## Customize

You can configure the CRUD interface by giving optional arguments to the ModelOpts object. See its docstring for more information or at [documentation webpage](https://edkedk99.github.io/streamlit_sql/api/#streamlit_sql.ModelOpts):


## Multiple Models

You can set the model_opts argument to a list of ModelOpts objects. In this case, a st.selectbox will let user to select the table to work on.

## Only create or update form

You can display just a create or update/delete form without the read interface using functions *show_updade*, and *show_create*.
