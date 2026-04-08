"""Shared utilities for AMap API scripts."""
import os
import sys
import json
import urllib.request
import urllib.parse

def get_api_key():
    key = os.environ.get("AMAP_MAPS_API_KEY", "")
    if not key:
        print(json.dumps({"error": "AMAP_MAPS_API_KEY environment variable is not set. Get one at https://lbs.amap.com/api/webservice/create-project-and-key"}))
        sys.exit(1)
    return key

def amap_request(path, params):
    """Make a request to the AMap REST API and return parsed JSON."""
    key = get_api_key()
    params["key"] = key
    params["source"] = "openclaw_skill"
    url = f"https://restapi.amap.com{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def output(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))
