# app.py
from flask import Flask, jsonify
import requests
import datetime
import urllib.parse

app = Flask(__name__)

BEARER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczpcL1wvYXBpLnN0b3JtcG9ydC5ueiIsImF1ZCI6Imh0dHBzOlwvXC9hcGkuc3Rvcm1wb3J0Lm56IiwianRpIjoiS1pvOURhSE5HWWYzIiwiaWF0IjoxNzUyMDg3NDEzLCJuYmYiOjE3NTIwODc0MTMsImV4cCI6MTc1MzI5NzAxMywidWlkIjo4OTV9.mlb4vVqFlSuzy4U3I5W0jpP3vPjatjAml63x4NwBdLM"
BASE_URL = "https://api.stormport.nz/api/v1/orders?order_by=releaseDate&sort_by=desc&per_page=100&page=1&includes=claimLinesTotal%2CassignedTo%2CorderSubtypeCode&release_date_start=2025-06-01T00%3A00%3A00%2B12%3A00&firm_id=2"

def parse_date(val):
    if not val:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(val)
        return dt.isoformat()
    except:
        return ""

def get_relative_due_string(due_iso):
    if not due_iso:
        return "TBC"
    try:
        due_dt = datetime.datetime.fromisoformat(due_iso)
        now = datetime.datetime.now(due_dt.tzinfo)
        diff = due_dt - now
        total_minutes = int(diff.total_seconds() // 60)
        sign = "-" if total_minutes < 0 else ""
        total_minutes = abs(total_minutes)
        days = total_minutes // (24 * 60)
        hours = (total_minutes % (24 * 60)) // 60
        minutes = total_minutes % 60
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
        return sign + " ".join(parts)
    except:
        return "TBC"

def get_due_soon_status(due_iso):
    if not due_iso:
        return False
    try:
        due_dt = datetime.datetime.fromisoformat(due_iso)
        now = datetime.datetime.now(due_dt.tzinfo)
        diff = due_dt - now
        total_seconds = diff.total_seconds()
        return 0 <= total_seconds <= 3600 or total_seconds < 0
    except:
        return False

def kpi_status(val):
    if val and val.lower() == "pass":
        return "pass"
    if val and val.lower() == "fail":
        return "fail"
    return "tbc"

@app.route("/")
def get_jobs():
    query = {
        "order_by": "releaseDate",
        "sort_by": "desc",
        "per_page": "100",
        "page": "1",
        "includes": "claimLinesTotal,assignedTo,orderSubtypeCode",
        "release_date_start": "2025-06-01T00:00:00+12:00",
        "firm_id": "2"
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(query)
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return jsonify({"error": f"Download failed with status {resp.status_code}"}), 500

        data = resp.json()
        items = data.get("data", [])
        included = data.get("included", [])

        person_map = {
            p["id"]: p["attributes"].get("first_name", "")
            for p in included
            if p.get("type") == "persons" and "attributes" in p
        }

        jobs = []
        for item in items:
            attr = item.get("attributes", {})
            assigned_id = str(attr.get("assigned_to", ""))
            assigned_to = person_map.get(assigned_id, "Unassigned")

            start_iso = parse_date(attr.get("requiredStart"))
            finish_iso = parse_date(attr.get("requiredFinish"))

            kpi_start_raw = attr.get("kpi_start")
            kpi_finish_raw = attr.get("kpi_finish")

            if kpi_start_raw and kpi_start_raw.lower() in ("pass", "fail"):
                kpi_start = kpi_start_raw
                kpi_start_due_soon = False
            else:
                kpi_start = get_relative_due_string(start_iso)
                kpi_start_due_soon = get_due_soon_status(start_iso)

            if kpi_finish_raw and kpi_finish_raw.lower() in ("pass", "fail"):
                kpi_finish = kpi_finish_raw
                kpi_finish_due_soon = False
            else:
                kpi_finish = get_relative_due_string(finish_iso)
                kpi_finish_due_soon = get_due_soon_status(finish_iso)

            jobs.append({
                "number": attr.get("orderId", ""),
                "address": attr.get("address", ""),
                "priority": attr.get("priority", ""),
                "assigned_to": assigned_to,
                "start_iso": start_iso,
                "finish_iso": finish_iso,
                "kpi_start": kpi_start,
                "kpi_start_status": kpi_status(kpi_start),
                "kpi_start_due_soon": kpi_start_due_soon,
                "kpi_finish": kpi_finish,
                "kpi_finish_status": kpi_status(kpi_finish),
                "kpi_finish_due_soon": kpi_finish_due_soon,
                "description": attr.get("workDescription", ""),
                "date_iso": parse_date(attr.get("releaseDate"))
            })

        return jsonify({"jobs": jobs})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
