from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="llama3.1",
    temperature=0
)


def nlp_agent(state):
    question = state["user_question"]

    prompt = f"""
You are an NLP analysis agent.

Analyze the following user question related to sales data.

Question:
{question}

Identify:

1. User intent
2. Required tables
3. Required metrics
4. Whether visualization is needed
5. Recommended visualization type

Return the answer in this format:

Intent:
Tables:
Metrics:
Visualization Required:
Visualization Type:
"""

    response = llm.invoke(prompt)

    return {
        **state,
        "intent": response.content
    }