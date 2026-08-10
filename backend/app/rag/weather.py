from dataclasses import dataclass
from typing import Protocol

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10

CONDITIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Violent showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass
class WeatherReport:
    city: str
    country: str
    temperature_c: float
    feels_like_c: float
    humidity: int
    wind_kmh: float
    condition: str
    weather_code: int
    is_day: bool
    high_c: float
    low_c: float


class WeatherProvider(Protocol):
    def current(self, city: str) -> WeatherReport | None: ...


class OpenMeteoWeather:
    def current(self, city: str) -> WeatherReport | None:
        place = self.geocode(city)
        if place is None:
            return None
        forecast = self.forecast(place["latitude"], place["longitude"])
        now = forecast["current"]
        today = forecast["daily"]
        code = now["weather_code"]
        return WeatherReport(
            city=place["name"],
            country=place.get("country", ""),
            temperature_c=now["temperature_2m"],
            feels_like_c=now["apparent_temperature"],
            humidity=now["relative_humidity_2m"],
            wind_kmh=now["wind_speed_10m"],
            condition=CONDITIONS.get(code, "Unknown"),
            weather_code=code,
            is_day=bool(now["is_day"]),
            high_c=today["temperature_2m_max"][0],
            low_c=today["temperature_2m_min"][0],
        )

    def geocode(self, city: str) -> dict | None:
        response = httpx.get(
            GEOCODING_URL,
            params={"name": city, "count": 1},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        return results[0] if results else None

    def forecast(self, latitude: float, longitude: float) -> dict:
        response = httpx.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,apparent_temperature,relative_humidity_2m,"
                    "weather_code,wind_speed_10m,is_day"
                ),
                "daily": "temperature_2m_max,temperature_2m_min",
                "forecast_days": 1,
                "timezone": "auto",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
