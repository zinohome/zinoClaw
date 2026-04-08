#!/usr/bin/env python3
"""天气查询"""
import sys
from amap_utils import amap_request, output

def main():
    if len(sys.argv) < 2:
        print("Usage: amap_weather.py <city_name_or_adcode>")
        sys.exit(1)
    data = amap_request("/v3/weather/weatherInfo", {"city": sys.argv[1], "extensions": "all"})
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    forecast = data["forecasts"][0]
    output({"city": forecast["city"], "forecasts": forecast["casts"]})

if __name__ == "__main__":
    main()
