"""
JARVIS — weather service.

Open-Meteo: free, no API key, no sign-up, no rate-limit headaches for
personal use. Two calls: geocode the city name, then fetch the forecast.
"""

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes.
WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snowfall", 73: "moderate snowfall", 75: "heavy snowfall",
    77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

ICONS = {
    0: "clear", 1: "clear", 2: "cloud", 3: "cloud", 45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle", 56: "drizzle", 57: "drizzle",
    61: "rain", 63: "rain", 65: "rain", 66: "rain", 67: "rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "rain", 81: "rain", 82: "rain", 85: "snow", 86: "snow",
    95: "storm", 96: "storm", 99: "storm",
}


class WeatherService:
    def __init__(self, config):
        self.config = config
        self.imperial = config.UNITS.lower() == "imperial"

    def _geocode(self, city):
        resp = requests.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=12,
        )
        resp.raise_for_status()
        results = resp.json().get("results")
        if not results:
            return None
        top = results[0]
        return {
            "name": top["name"],
            "country": top.get("country", ""),
            "lat": top["latitude"],
            "lon": top["longitude"],
        }

    def fetch(self, city=None) -> dict:
        """Structured forecast. Raises on network failure."""
        city = city or self.config.DEFAULT_CITY
        place = self._geocode(city)
        if not place:
            return {"error": f"I could not find a place called '{city}'."}

        params = {
            "latitude": place["lat"],
            "longitude": place["lon"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                       "wind_speed_10m,weather_code,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,weather_code",
            "forecast_days": 3,
            "timezone": "auto",
        }
        if self.imperial:
            params.update(
                temperature_unit="fahrenheit",
                wind_speed_unit="mph",
            )

        resp = requests.get(FORECAST_URL, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        current = data["current"]
        daily = data["daily"]
        code = current["weather_code"]

        return {
            "city": place["name"],
            "country": place["country"],
            "temperature": round(current["temperature_2m"]),
            "feels_like": round(current["apparent_temperature"]),
            "humidity": current["relative_humidity_2m"],
            "wind": round(current["wind_speed_10m"]),
            "condition": WMO.get(code, "unclear conditions"),
            "icon": ICONS.get(code, "cloud"),
            "is_day": bool(current["is_day"]),
            "unit": "°F" if self.imperial else "°C",
            "wind_unit": "mph" if self.imperial else "km/h",
            "forecast": [
                {
                    "date": daily["time"][i],
                    "high": round(daily["temperature_2m_max"][i]),
                    "low": round(daily["temperature_2m_min"][i]),
                    "rain_chance": daily["precipitation_probability_max"][i],
                    "condition": WMO.get(daily["weather_code"][i], ""),
                }
                for i in range(len(daily["time"]))
            ],
        }

    def describe(self, city=None) -> str:
        """One spoken-friendly sentence, safe to call — never raises."""
        try:
            w = self.fetch(city)
        except requests.exceptions.RequestException:
            return "I could not reach the weather service just now."
        if "error" in w:
            return w["error"]

        today = w["forecast"][0] if w["forecast"] else None
        line = (
            f"{w['city']} is {w['temperature']}{w['unit']} with {w['condition']}, "
            f"feels like {w['feels_like']}{w['unit']}. "
            f"Humidity {w['humidity']} percent, wind {w['wind']} {w['wind_unit']}."
        )
        if today:
            line += (
                f" Today ranges {today['low']} to {today['high']}{w['unit']}"
                f" with a {today['rain_chance']} percent chance of precipitation."
            )
        return line
