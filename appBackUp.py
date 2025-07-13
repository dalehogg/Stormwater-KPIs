from flask import Flask, render_template_string, request

import requests

import datetime

import urllib.parse


app = Flask(__name__)


BEARER_TOKEN = (

    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."

    "eyJpc3MiOiJodHRwczpcL1wvYXBpLnN0b3JtcG9ydC5ueiIsImF1ZCI6Imh0dHBzOlwvXC9hcGkuc3Rvcm1wb3J0Lm56IiwianRpIjoiS1pvOURhSE5HWWYzIiwiaWF0IjoxNzUyMDg3NDEzLCJuYmYiOjE3NTIwODc0MTMsImV4cCI6MTc1MzI5NzAxMywidWlkIjo4OTV9.mlb4vVqFlSuzy4U3I5W0jpP3vPjatjAml63x4NwBdLM"

)


BASE_URL = (

    "https://api.stormport.nz/api/v1/orders?order_by=releaseDate&sort_by=desc&per_page=100&page=1&includes=claimLinesTotal%2CassignedTo%2CorderSubtypeCode&release_date_start=2025-06-01T00%3A00%3A00%2B12%3A00&firm_id=2"

)


DEFAULT_FILTER_DAYS = 30


HTML_TEMPLATE = """

<!DOCTYPE html>

<html>

<head>

<meta charset="utf-8" />

<title>Due Jobs List</title>

<style>

  body { font-family: sans-serif; padding: 20px; }

  table { border-collapse: collapse; width: 100%; margin-top: 20px; }

  td, th { padding: 7px; text-align: left; cursor: default; }

  button.toggleBtn, .refreshBtn { padding: 5px 10px; font-size: 0.9em; border-radius:4px; border:1px solid #888; background:#f0f0f0; cursor:pointer; transition:background-color 0.3s; }

  td{
    font-size:14px;
  }

  button.toggleBtn:hover, .refreshBtn:hover { background:#ddd; }

  .kpiBox { padding: 4px; text-align: center; }

  .kpiBox::first-letter{
    text-transform: uppercase;
  }

  .pass { background-color: #08f139; }

  .fail { background-color: #ff0000; }

  th.sortableHeader {

    background-color: #f0f0f0;

    cursor: pointer;

    user-select: none;

    transition: background-color 0.3s, box-shadow 0.2s;

  }

  th.sortableHeader:hover {

    background-color: #ddd;

  }

  th.sortableHeader:active {

    background-color: #ccc;

    box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);

  }
  .dueSoon { 
    color: #ff0000;
    font-weight:bold;
  }

  tr{
    box-shadow: 2px 2px 2px lightgrey;
    margin 2px 0px 2px 0px;
  }

  .rowsForMainData:hover{
    background-color: #ecebeb;
  }

  thead{
    background-color: #ecebeb;
  }

</style>

</head>

<body>

<div class="headerBar">

  <h2 style="display:block; text-transform: uppercase;"><span id="currentDays">{{ jobs|length }} of the latest stormwater jobs</span></h2>
  <label for="autoRefreshToggle" style="margin-left:20px; cursor: pointer; user-select: none;">
    <input type="checkbox" id="autoRefreshToggle" checked style="vertical-align: middle; margin-right: 5px;">
    <span>Auto Refresh</span>
  </label>

</div>

{% if jobs %}

<table id="jobsTable">

  <thead>

    <tr>

      <th class="sortableHeader" onclick="sortTableByDate('date')">Date ⬍</th>

      <th>Address</th>

      <th>Job Number</th>

      <th>Priority</th>

      <th>Assigned To</th>

      <th class="sortableHeader" onclick="sortTableByDate('start')">Start Date ⬍</th>

      <th class="sortableHeader" onclick="sortTableByDate('finish')">Finish Date ⬍</th>

      <th>KPI Start</th>

      <th>KPI Finish</th>

      <th>Work Description</th>

    </tr>

  </thead>

  <tbody id="jobsBody">

  {% for job in jobs %}

    <tr class="rowsForMainData">

      <td data-date="{{ job.date_iso }}">{{ job.date_str }}</td>

      <td>{{ job.address }}</td>

      <td>{{ job.number }}</td>

      <td>{{ job.priority }}</td>

      <td>{{ job.assigned_to }}</td>
      <td data-date="{{ job.start_iso }}">{{ job.start_str }}</td>
      <td data-date="{{ job.finish_iso }}">{{ job.finish_str }}</td>
      <td class="kpiBox {{ job.kpi_start_status }}">
        {% if job.kpi_start_due_soon %}
          <span class="dueSoon">{{ job.kpi_start or '-' }}</span>
        {% else %}
          {{ job.kpi_start or '-' }}
        {% endif %}
      </td>
      <td class="kpiBox {{ job.kpi_finish_status }}">
        {% if job.kpi_finish_due_soon %}
          <span class="dueSoon">{{ job.kpi_finish or '-' }}</span>
        {% else %}
          {{ job.kpi_finish or '-' }}
        {% endif %}
      </td>
      <td><button class='toggleBtn' onclick="toggleRow('desc{{ loop.index0 }}')">Description</button></td>

    </tr>

    <tr id="desc{{ loop.index0 }}" style="display:none;" class="commentRow">

      <td colspan="9"><span style='font-weight:bold;'>Work Description</span><br>{{ job.description|replace('\\n','<br>') }}</td>

    </tr>

  {% endfor %}

  </tbody>

</table>

{% else %}

<p>No jobs found in the date range.</p>

{% endif %}


<script>

var openId = null;

var sortDirections = { start: 1, finish: 1, date: 1 };


function toggleRow(id) {

  if (openId && openId == id) {

    document.getElementById(id).style.display = 'none';

    openId = null;

  } else {

    var rows = document.querySelectorAll('.commentRow');

    rows.forEach(function(r) { r.style.display = 'none'; });

    document.getElementById(id).style.display = 'table-row';

    openId = id;

  }

}


function sortTableByDate(type) {

  var table = document.getElementById('jobsTable').getElementsByTagName('tbody')[0];

  var rows = Array.from(table.rows).filter(r => !r.classList.contains('commentRow'));

  var direction = sortDirections[type];

  var colIndexMap = { date: 0, start: 5, finish: 6 };
  var colIndex = colIndexMap[type];

  rows.sort(function(a, b) {
    var dateA = new Date(a.cells[colIndex].getAttribute('data-date') || 0);
    var dateB = new Date(b.cells[colIndex].getAttribute('data-date') || 0);
    return direction * (dateA - dateB);
  });

  rows.forEach(function(r) {
    var desc = document.getElementById(r.nextElementSibling.id);
    table.appendChild(r);
    table.appendChild(desc);
  });

  sortDirections[type] *= -1;
}

var autoRefreshInterval = setInterval(function() {
  if (document.getElementById('autoRefreshToggle').checked) {
    location.reload();
  }
}, 60000);

</script>

</body>

</html>

"""


def parse_date(val):
    if not val:
        return "", ""
    try:
        dt = datetime.datetime.fromisoformat(val)
        return dt.isoformat(), dt.strftime("%d/%m/%Y %H:%M")
    except:
        return "", val


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
    except Exception:
        return "TBC"


def get_due_soon_status(due_iso):
    """Returns 'dueSoon' if within 1 hour or negative, else ''."""
    if not due_iso:
        return ""
    try:
        due_dt = datetime.datetime.fromisoformat(due_iso)
        now = datetime.datetime.now(due_dt.tzinfo)
        diff = due_dt - now
        total_seconds = diff.total_seconds()
        if 0 <= total_seconds <= 3600 or total_seconds < 0:
            return "dueSoon"
        return ""
    except Exception:
        return ""


def kpi_status(val):
    if val.lower() == "pass":
        return "pass"
    if val.lower() == "fail":
        return "fail"
    return "tbc"


def format_date(val):
    if not val:
        return ""
    try: 
        dt = datetime.datetime.fromisoformat(val)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return val


@app.route("/")
def index():
    now = datetime.datetime.now().date()
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

            return f"<pre>Download failed with status {resp.status_code}</pre>"


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

            number = attr.get("orderId", "")

            address = attr.get("address", "")

            priority = attr.get("priority", "")

            assigned_id = str(attr.get("assigned_to", ""))

            assigned_to = person_map.get(assigned_id, "Unassigned")


            start_iso, start_str = parse_date(attr.get("requiredStart"))
            finish_iso, finish_str = parse_date(attr.get("requiredFinish"))

            start_due_soon = get_due_soon_status(start_iso)
            finish_due_soon = get_due_soon_status(finish_iso)


            kpi_start_raw = attr.get("kpi_start")
            kpi_finish_raw = attr.get("kpi_finish")

            if kpi_start_raw and kpi_start_raw.lower() in ("pass", "fail"):
                kpi_start = kpi_start_raw
                kpi_start_due_soon = ""
            else:
                kpi_start = get_relative_due_string(start_iso)
                kpi_start_due_soon = get_due_soon_status(start_iso)

            if kpi_finish_raw and kpi_finish_raw.lower() in ("pass", "fail"):
                kpi_finish = kpi_finish_raw
                kpi_finish_due_soon = ""
            else:
                kpi_finish = get_relative_due_string(finish_iso)
                kpi_finish_due_soon = get_due_soon_status(finish_iso)

            jobs.append({

                "number": number,

                "address": address,

                "assigned_to": assigned_to,

                "start_iso": start_iso,

                "start_str": start_str,

                "priority": priority,

                "finish_iso": finish_iso,

                "finish_str": finish_str,

                "kpi_start": kpi_start,

                "kpi_finish": kpi_finish,

                "start_due_soon": start_due_soon,

                "finish_status": finish_due_soon,

                "kpi_start_status": kpi_status(kpi_start),

                "kpi_finish_status": kpi_status(kpi_finish),

                "kpi_start_due_soon": kpi_start_due_soon,

                "kpi_finish_due_soon": kpi_finish_due_soon,

                "description": attr.get("workDescription", ""),

                "date_iso": attr.get("releaseDate") or "",

                "date_str": parse_date(attr.get("releaseDate"))[1],

            })


        return render_template_string(

            HTML_TEMPLATE,

            jobs=jobs,

            default_days=DEFAULT_FILTER_DAYS

        )


    except Exception as e:

        return f"<pre>Error: {e}</pre>"


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5050, debug=True)
