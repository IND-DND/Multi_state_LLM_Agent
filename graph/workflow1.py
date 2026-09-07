from typing import TypedDict

from langgraph.graph import StateGraph, END

from llm.sql_generator import generate_sql

from utils.db import execute_query


class SQLState(TypedDict):

    question:str

    sql:str

    result:str


def sql_node(state):

    sql = generate_sql(state["question"])

    return {"sql":sql}


def execute_node(state):

    result = execute_query(state["sql"])

    return {"result":result.to_string()}


builder = StateGraph(SQLState)

builder.add_node("Generate_SQL",sql_node)

builder.add_node("Execute_SQL",execute_node)

builder.set_entry_point("Generate_SQL")

builder.add_edge("Generate_SQL","Execute_SQL")

builder.add_edge("Execute_SQL",END)

app = builder.compile()
app2 = app
