#!/usr/bin/env python3
"""地址 → 经纬度（地理编码）"""
import sys
from amap_utils import amap_request, output

def main():
    if len(sys.argv) < 2:
        print("Usage: amap_geo.py <address> [city]")
        sys.exit(1)
    address = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else ""
    params = {"address": address}
    if city:
        params["city"] = city
    data = amap_request("/v3/geocode/geo", params)
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    geocodes = data.get("geocodes", [])
    results = [{"province": g.get("province"), "city": g.get("city"), "district": g.get("district"),
                "street": g.get("street"), "location": g.get("location"), "level": g.get("level")} for g in geocodes]
    output({"results": results})

if __name__ == "__main__":
    main()
