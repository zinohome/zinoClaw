#!/usr/bin/env python3
"""周边搜索 POI"""
import sys, argparse
from amap_utils import amap_request, output

def main():
    parser = argparse.ArgumentParser(description="AMap around search")
    parser.add_argument("location", help="中心点 lng,lat")
    parser.add_argument("--keywords", default="", help="搜索关键词")
    parser.add_argument("--radius", default="1000", help="搜索半径(米)")
    args = parser.parse_args()
    params = {"location": args.location, "radius": args.radius}
    if args.keywords: params["keywords"] = args.keywords
    data = amap_request("/v3/place/around", params)
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    pois = [{"id": p["id"], "name": p["name"], "address": p.get("address", ""),
             "location": p.get("location", ""), "distance": p.get("distance", "")} for p in data.get("pois", [])]
    output({"count": len(pois), "pois": pois})

if __name__ == "__main__":
    main()
