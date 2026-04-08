#!/usr/bin/env python3
"""POI 详情查询"""
import sys
from amap_utils import amap_request, output

def main():
    if len(sys.argv) < 2:
        print("Usage: amap_detail.py <poi_id>")
        sys.exit(1)
    data = amap_request("/v3/place/detail", {"id": sys.argv[1]})
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    poi = data["pois"][0]
    output({"id": poi.get("id"), "name": poi.get("name"), "location": poi.get("location"),
            "address": poi.get("address"), "city": poi.get("cityname"), "type": poi.get("type"),
            "business_area": poi.get("business_area"), "alias": poi.get("alias"),
            "photos": poi.get("photos", [])[:1]})

if __name__ == "__main__":
    main()
