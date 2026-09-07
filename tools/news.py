import requests

from langchain.tools import tool

API_KEY = "1d92c12f1c5045ecb96f207643ca2274"


@tool
def get_news(topic: str) -> str:
    """
    Retrieve the latest news headlines for a given topic.
    """
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={API_KEY}"

    response = requests.get(url).json()

    articles = []

    for article in response["articles"][:5]:
        articles.append(article["title"])

    return articles