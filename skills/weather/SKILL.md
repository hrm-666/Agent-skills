---
name: weather
description: Query weather information for a given city, including weather conditions (sunny, overcast, cloudy, light rain, etc.), current temperature, humidity, and air quality index.Use this skill when you need to check the weather for a city.
---

## How to use

1. Extract the city for which the user wants to query the weather from the message. Note the English names for Chinese cities.

2. Run the get_weather script:

       bash: python skills/weather/scripts/get_weather.py --city "city"
3. The script returns results in JSON format; parse them and respond to the user naturally.

## Common Query Examples

Query the weather in Xi'an:

    bash: python skills/weather/scripts/get_weather.py --city "Xi'an"

Query the weather in Beijing:

    bash: python skills/weather/scripts/get_weather.py --city "Beijing"
