from langchain_ollama import ChatOllama
import plotly.express as px


llm = ChatOllama(
    model="llama3.1",
    temperature=0
)


def visualization_agent(state):

    print("\n==============================")
    print("VISUALIZATION AGENT STARTED")
    print("==============================")

    question = state["user_question"]

    df = state.get("query_result")

    print("User Question:")
    print(question)

    print("Query Result:")
    print(df)


    # ----------------------------------
    # Check DataFrame
    # ----------------------------------

    if df is None:

        print("Query result is None")

        return {
            **state,
            "visualization_type": "none",
            "figure": None
        }


    if df.empty:

        print("Query result is empty")

        return {
            **state,
            "visualization_type": "none",
            "figure": None
        }


    # ----------------------------------
    # Display Columns
    # ----------------------------------

    print("Columns:")
    print(df.columns.tolist())


    # ----------------------------------
    # Ask LLM for Chart Type
    # ----------------------------------

    prompt = f"""
You are a data visualization expert.

User question:
{question}

Columns:
{list(df.columns)}

Data types:
{df.dtypes.to_dict()}

Choose the best visualization and must return some form of visualization.

Options:

bar
line
pie
scatter
none

Rules:

bar = category comparison

line = time series or trend

pie = percentage or distribution

scatter = relationship between numerical values

none = visualization not appropriate

Return ONLY one word.
"""


    response = llm.invoke(prompt)

    chart_type = response.content.strip().lower()

    print("LLM Selected Chart:")
    print(chart_type)



    chart_type = chart_type.replace(
        "```",
        ""
    ).strip()


   

    x_column = df.columns[0]

    y_column = df.columns[-1]


    print("X Column:")
    print(x_column)

    print("Y Column:")
    print(y_column)


    fig = None


    # ----------------------------------
    # BAR
    # ----------------------------------

    if chart_type == "bar":

        fig = px.bar(
            df,
            x=x_column,
            y=y_column,
            title="Sales Analysis"
        )


    # ----------------------------------
    # LINE
    # ----------------------------------

    elif chart_type == "line":

        fig = px.line(
            df,
            x=x_column,
            y=y_column,
            title="Sales Trend"
        )


    # ----------------------------------
    # PIE
    # ----------------------------------

    elif chart_type == "pie":

        fig = px.pie(
            df,
            names=x_column,
            values=y_column,
            title="Sales Distribution"
        )


    # ----------------------------------
    # SCATTER
    # ----------------------------------

    elif chart_type == "scatter":

        fig = px.scatter(
            df,
            x=x_column,
            y=y_column,
            title="Sales Relationship"
        )


    # ----------------------------------
    # Invalid Response
    # ----------------------------------

    else:

        print(
            "LLM did not select a valid chart."
        )

        chart_type = "none"


    # ----------------------------------
    # Final Output
    # ----------------------------------

    print(
        "Final Visualization Type:",
        chart_type
    )

    print(
        "Figure Created:",
        fig is not None
    )


    return {
        **state,
        "visualization_type": chart_type,
        "figure": fig
    }