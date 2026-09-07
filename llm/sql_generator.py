from langchain_ollama import ChatOllama
from prompts.sql_prompt import prompt

llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0
)

def generate_sql(question):

    final_prompt = prompt.format(question=question)

    response = llm.invoke(final_prompt)

    sql = response.content

    sql = sql.replace("```sql","")

    sql = sql.replace("```","")

    return sql.strip()