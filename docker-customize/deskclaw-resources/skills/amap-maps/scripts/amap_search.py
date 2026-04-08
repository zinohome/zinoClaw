#!/usr/bin/env python3
"""关键词搜索 POI"""
import sys, argparse
from amap_utils import amap_request, output

def main():
    parser = argparse.ArgumentParser(description="AMap text search")
    parser.add_argument("keywords", help="搜索关键词")
    parser.add_argument("--city", default="", help="限定城市")
    parser.add_argument("--types", default="", help="POI类型")
    args = parser.parse_args()
    params = {"keywords": args.keywords}
    if args.city: params["city"] = args.city
    if args.types: params["types"] = args.types
    data = amap_request("/v3/place/text", params)
    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    pois = [{"id": p["id"], "name": p["name"], "address": p.get("address", ""),
             "location": p.get("location", ""), "type": p.get("type", "")} for p in data.get("pois", [])]
    output({"count": len(pois), "pois": pois})

if __name__ == "__main__":
    main()
