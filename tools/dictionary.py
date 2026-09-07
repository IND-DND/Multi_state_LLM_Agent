from langchain_core.tools import tool
import requests

@tool
def get_definition(word: str) -> str:
    """
    Returns the definition of an English word.
    """

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

    response = requests.get(url)

    if response.status_code != 200:
        return "Definition not found."

    data = response.json()

    return data[0]["meanings"][0]["definitions"][0]["definition"]