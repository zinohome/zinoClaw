#!/usr/bin/env python3
"""IP 定位"""
import sys
from amap_utils import amap_request, output

def main():
    if len(sys.argv) < 2:
        print("Usage: amap_ip.py <ip_address>")
        sys.exit(1)
    data = amap_request("/v3/ip", {"ip": sys.argv[1]})
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    output({"province": data.get("province"), "city": data.get("city"),
            "adcode": data.get("adcode"), "rectangle": data.get("rectangle")})

if __name__ == "__main__":
    main()
