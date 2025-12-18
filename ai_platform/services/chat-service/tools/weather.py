"""
Weather Tool - Get weather information.
This is a MOCK implementation - replace with real weather API later.
"""
from tools.registry import Tool
from dataclasses import dataclass, field
from typing import Dict, Any
import random


@dataclass
class WeatherTool(Tool):
    """Get current weather information for a location."""
    
    name: str = "get_weather"
    description: str = """Get current weather information for a city or location.
    Use this when users ask about weather conditions."""
    
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name to get weather for"
            },
            "unit": {
                "type": "string",
                "description": "Temperature unit",
                "enum": ["celsius", "fahrenheit"],
                "default": "celsius"
            }
        },
        "required": ["city"]
    })
    
    async def execute(self, city: str, unit: str = "celsius") -> str:
        """
        MOCK: Get weather for a city.
        TODO: Replace with real weather API (OpenWeatherMap, etc.)
        """
        # Mock weather data for some cities
        mock_weather = {
            "تهران": {"temp": 15, "condition": "آفتابی", "humidity": 35},
            "tehran": {"temp": 15, "condition": "Sunny", "humidity": 35},
            "اصفهان": {"temp": 18, "condition": "کمی ابری", "humidity": 30},
            "isfahan": {"temp": 18, "condition": "Partly Cloudy", "humidity": 30},
            "شیراز": {"temp": 20, "condition": "آفتابی", "humidity": 25},
            "shiraz": {"temp": 20, "condition": "Sunny", "humidity": 25},
            "مشهد": {"temp": 12, "condition": "ابری", "humidity": 45},
            "mashhad": {"temp": 12, "condition": "Cloudy", "humidity": 45},
            "new york": {"temp": 8, "condition": "Rainy", "humidity": 70},
            "london": {"temp": 10, "condition": "Cloudy", "humidity": 80},
            "paris": {"temp": 12, "condition": "Partly Cloudy", "humidity": 65},
            "tokyo": {"temp": 14, "condition": "Clear", "humidity": 55},
        }
        
        city_lower = city.lower().strip()
        weather = mock_weather.get(city_lower)
        
        if not weather:
            # Generate random mock data for unknown cities
            weather = {
                "temp": random.randint(5, 30),
                "condition": random.choice(["Sunny", "Cloudy", "Partly Cloudy", "Rainy"]),
                "humidity": random.randint(30, 80)
            }
        
        temp = weather["temp"]
        if unit == "fahrenheit":
            temp = round(temp * 9/5 + 32)
            unit_symbol = "°F"
        else:
            unit_symbol = "°C"
        
        return f"""[Weather for {city}]
🌡️ Temperature: {temp}{unit_symbol}
🌤️ Condition: {weather['condition']}
💧 Humidity: {weather['humidity']}%

Note: This is mock data. Real weather API integration pending."""

