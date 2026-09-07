
from langchain_ollama import ChatOllama
from utils.db_connection import execute_sql


# Initialize LLM
llm = ChatOllama(
    model="llama3.1",
    temperature=0
)


def sql_agent(state):
    """
    SQL Agent:
    Converts the user's natural language question
    into a PostgreSQL SQL query and executes it.
    """

    question = state["user_question"]

    # Get NLP analysis if available
    intent = state.get("intent", "")

    prompt = f"""
You are an expert PostgreSQL SQL developer.

Database schema:

customers(
    customer_id,
    customer_name,
    city,
    region
)

products(
    product_id,
    product_name,
    category,
    price
)

sales(
    sale_id,
    product_id,
    customer_id,
    sale_date,
    quantity,
    revenue
)

transactions(
    transaction_id,
    sale_id,
    payment_method,
    transaction_status
)

NLP Analysis:
{intent}

User Question:
{question}

Generate ONLY a valid PostgreSQL SQL query.

Rules:

1. Use correct JOIN operations.
2. Use table aliases.
3. Never use DELETE, UPDATE, INSERT or DROP.
4. Only generate SELECT queries.
5. Do not include markdown.
6. Do not include explanations.
7. Use PostgreSQL syntax.
8. Use aggregate functions such as SUM, AVG, COUNT, MIN, and MAX when required.
9. Use GROUP BY when required.
10. Use ORDER BY when required.
11. Use LIMIT when the user asks for top or bottom results.
12. Use appropriate date functions for date-based questions.

SQL Query:
"""

    # Generate SQL using Llama 3.1
    response = llm.invoke(prompt)

    sql_query = response.content.strip()

    # Remove markdown code blocks if the LLM returns them
    sql_query = sql_query.replace("```sql", "")
    sql_query = sql_query.replace("```", "")
    sql_query = sql_query.strip()

    print("Generated SQL:")
    print(sql_query)

    try:

        # Execute PostgreSQL query
        result = execute_sql(sql_query)

        return {
            **state,
            "sql_query": sql_query,
            "query_result": result,
            "error": None
        }

    except Exception as e:

        return {
            **state,
            "sql_query": sql_query,
            "query_result": None,
            "error": str(e)
        }

