from typing import TypedDict, Optional
import pandas as pd

from langgraph.graph import StateGraph, START, END

from agents.nlp_agent import nlp_agent
from agents.sql_agent import sql_agent
from agents.visualization_agent import visualization_agent


class AgentState(TypedDict):

    user_question: str

    intent: Optional[str]

    sql_query: Optional[str]

    query_result: Optional[pd.DataFrame]

    visualization_type: Optional[str]

    figure: object

    error: Optional[str]

    conversation_history: list


workflow = StateGraph(AgentState)


workflow.add_node(
    "nlp_agent",
    nlp_agent
)

workflow.add_node(
    "sql_agent",
    sql_agent
)

workflow.add_node(
    "visualization_agent",
    visualization_agent
)


workflow.add_edge(
    START,
    "nlp_agent"
)

workflow.add_edge(
    "nlp_agent",
    "sql_agent"
)

workflow.add_edge(
    "sql_agent",
    "visualization_agent"
)

workflow.add_edge(
    "visualization_agent",
    END
)


app = workflow.compile()