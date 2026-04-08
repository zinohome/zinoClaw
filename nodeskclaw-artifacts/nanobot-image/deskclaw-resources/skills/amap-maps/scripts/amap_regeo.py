#!/usr/bin/env python3
"""经纬度 → 地址（逆地理编码）"""
import sys
from amap_utils import amap_request, output

def main():
    if len(sys.argv) < 2:
        print("Usage: amap_regeo.py <lng,lat>")
        sys.exit(1)
    data = amap_request("/v3/geocode/regeo", {"location": sys.argv[1]})
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    comp = data["regeocode"]["addressComponent"]
    output({"formatted_address": data["regeocode"].get("formatted_address"),
            "province": comp.get("province"), "city": comp.get("city"), "district": comp.get("district")})

if __name__ == "__main__":
    main()
