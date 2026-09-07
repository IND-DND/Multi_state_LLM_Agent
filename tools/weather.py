from langchain_core.tools import tool
import requests
import os

API_KEY = "51927359b6f9f11056a492cbd8d27cf8"

@tool
def get_weather(city: str) -> str:
    """
    Get the current weather for a given city.
    Returns temperature, humidity, and weather description.
    """

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={API_KEY}&units=metric"
    )

    response = requests.get(url)

    data = response.json()

    if response.status_code != 200:
        return "Unable to fetch weather."

    return (
        f"City: {city}\n"
        f"Temperature: {data['main']['temp']}°C\n"
        f"Humidity: {data['main']['humidity']}%\n"
        f"Condition: {data['weather'][0]['description']}"
    )