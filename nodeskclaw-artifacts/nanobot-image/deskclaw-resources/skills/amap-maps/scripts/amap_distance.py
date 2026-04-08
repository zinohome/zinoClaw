#!/usr/bin/env python3
"""距离测量"""
import sys, argparse
from amap_utils import amap_request, output

def main():
    parser = argparse.ArgumentParser(description="AMap distance measurement")
    parser.add_argument("origins", help="起点 lng,lat（多个用 | 分隔）")
    parser.add_argument("destination", help="终点 lng,lat")
    parser.add_argument("--type", default="1", choices=["0", "1", "3"], help="0=直线 1=驾车 3=步行")
    args = parser.parse_args()
    data = amap_request("/v3/distance", {"origins": args.origins, "destination": args.destination, "type": args.type})
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    results = [{"origin_id": r.get("origin_id"), "distance": r.get("distance"), "duration": r.get("duration")}
               for r in data.get("results", [])]
    output({"results": results})

if __name__ == "__main__":
    main()
