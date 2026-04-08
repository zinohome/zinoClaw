#!/usr/bin/env python3
"""路径规划：驾车 / 步行 / 骑行 / 公交"""
import sys, argparse, json
from amap_utils import amap_request, output

def parse_path(path, mode):
    """Extract key info from a path result."""
    steps = []
    for s in path.get("steps", []):
        steps.append({"instruction": s.get("instruction", ""), "road": s.get("road", ""),
                       "distance": s.get("distance", ""), "duration": s.get("duration", "")})
    return {"distance": path.get("distance"), "duration": path.get("duration"), "steps": steps}

def main():
    parser = argparse.ArgumentParser(description="AMap direction planning")
    parser.add_argument("mode", choices=["driving", "walking", "bicycling", "transit"], help="规划模式")
    parser.add_argument("origin", help="起点 lng,lat")
    parser.add_argument("destination", help="终点 lng,lat")
    parser.add_argument("--city", default="", help="起点城市(公交模式)")
    parser.add_argument("--cityd", default="", help="终点城市(公交模式)")
    args = parser.parse_args()

    params = {"origin": args.origin, "destination": args.destination}

    if args.mode == "driving":
        data = amap_request("/v3/direction/driving", params)
    elif args.mode == "walking":
        data = amap_request("/v3/direction/walking", params)
    elif args.mode == "bicycling":
        data = amap_request("/v4/direction/bicycling", params)
        # v4 API has different status field
        if data.get("errcode", -1) != 0:
            output({"error": data.get("errmsg", "Unknown error")})
            return
        paths = [parse_path(p, "bicycling") for p in data.get("data", {}).get("paths", [])]
        output({"mode": "bicycling", "origin": args.origin, "destination": args.destination, "paths": paths})
        return
    elif args.mode == "transit":
        params["city"] = args.city
        params["cityd"] = args.cityd
        data = amap_request("/v3/direction/transit/integrated", params)
        if data.get("status") != "1":
            output({"error": data.get("info", "Unknown error")})
            return
        route = data.get("route", {})
        transits = []
        for t in route.get("transits", []):
            segments = []
            for seg in t.get("segments", []):
                seg_info = {}
                if seg.get("walking", {}).get("steps"):
                    seg_info["walking_steps"] = [{"instruction": s.get("instruction", "")} for s in seg["walking"]["steps"]]
                if seg.get("bus", {}).get("buslines"):
                    seg_info["buslines"] = [{"name": b.get("name"), "departure": b.get("departure_stop", {}).get("name"),
                                              "arrival": b.get("arrival_stop", {}).get("name")} for b in seg["bus"]["buslines"]]
                segments.append(seg_info)
            transits.append({"duration": t.get("duration"), "walking_distance": t.get("walking_distance"), "segments": segments})
        output({"mode": "transit", "distance": route.get("distance"), "transits": transits})
        return

    if data.get("status") != "1":
        output({"error": data.get("info", "Unknown error")})
        return
    paths = [parse_path(p, args.mode) for p in data.get("route", {}).get("paths", [])]
    output({"mode": args.mode, "origin": args.origin, "destination": args.destination, "paths": paths})

if __name__ == "__main__":
    main()
