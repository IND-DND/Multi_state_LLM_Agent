from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from tools.weather import get_weather
from tools.news import get_news
from tools.dictionary import get_definition

from prompts.prompt import SYSTEM_PROMPT


# ---------------------------------------
# Load Open Source LLM
# ---------------------------------------

llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0
)

# ---------------------------------------
# Bind Tools
# ---------------------------------------

tools = [
    get_weather,
    get_news,
    get_definition
]

llm_with_tools = llm.bind_tools(tools)

tool_map = {
    "get_weather": get_weather,
    "get_news": get_news,
    "get_definition": get_definition
}


# ---------------------------------------
# Chatbot Function
# ---------------------------------------

def chatbot(question):

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=question)
    ]

    try:

        # First LLM call
        ai_message = llm_with_tools.invoke(messages)

        messages.append(ai_message)

        # If LLM wants to call tools
        if ai_message.tool_calls:

            for tool_call in ai_message.tool_calls:

                tool_name = tool_call["name"]

                tool_args = tool_call["args"]

                tool = tool_map[tool_name]

                # Execute Tool
                result = tool.invoke(tool_args)

                # Add Tool Result
                messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"]
                    )
                )

            # Second LLM call
            final_response = llm_with_tools.invoke(messages)

            return final_response.content

        # No tool required
        return ai_message.content

    except Exception as e:

        return f"Error: {str(e)}"