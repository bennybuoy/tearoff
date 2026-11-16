#!/usr/bin/env python3
"""Start a week-ahead strip: classes from the live timetable plus the forecast.

  week_ahead.py --start 2026-03-16 --out ~/tearoff-prints/2026-03-16-week.json

Writes a widget spec with the school week filled in. Then YOU add what the
timetable feed cannot know (duties, meetings, personal events, a real fun fact),
replace every REPLACE ME, and render it with widgets.py.

--schedule CMD (or "schedule_cmd" in the config) is any command that prints your
timetable as JSON: a list of {"start": "2026-03-16T08:35:00", "class_code": "...",
"location": "..."}. With no timetable it still builds the week from the forecast.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--start", required=True, help="Monday of the week, YYYY-MM-DD")
ap.add_argument("--days", type=int, default=5)
ap.add_argument("--out", required=True)
ap.add_argument("--schedule")
ap.add_argument("--title", default="THE WEEK AHEAD")
a = ap.parse_args()
start = dt.date.fromisoformat(a.start)

sys.path.insert(0, HERE)
from briefing import CONFIG  # noqa: E402

cmd = a.schedule or CONFIG.get("schedule_cmd")
lessons = []
if cmd:
    try:
        lessons = json.loads(subprocess.run(cmd, shell=True, check=True, capture_output=True,
                                            text=True, timeout=60).stdout)
    except (subprocess.SubprocessError, ValueError) as exc:
        print(f"note: timetable not available ({exc}); building without classes",
              file=sys.stderr)

wx = {}
try:
    out = subprocess.run([sys.executable, os.path.join(HERE, "facts.py"), "--week", a.start],
                         check=True, capture_output=True, text=True, timeout=120).stdout
    wx = {d["date"]: d for d in json.loads(out)["week"]}
except (subprocess.SubprocessError, ValueError):
    print("note: forecast not available; building without weather", file=sys.stderr)

days, total = [], 0
for i in range(a.days):
    day = start + dt.timedelta(days=i)
    rows = sorted((l["start"][11:16], l["class_code"], l.get("location", ""))
                  for l in lessons if l["start"][:10] == day.isoformat())
    total += len(rows)
    entry = {"date": day.isoformat(), "entries": [list(r) for r in rows], "note": ""}
    if day.isoformat() in wx:
        entry["sky"] = [wx[day.isoformat()]["kind"], wx[day.isoformat()]["hi"]]
    days.append(entry)

end = start + dt.timedelta(days=a.days - 1)
spec = {"date": a.start, "widgets": [
    {"type": "title", "text": a.title,
     "sub": f"{start.strftime('%a %-d %b')} to {end.strftime('%a %-d %b %Y')}"},
    {"type": "text", "font": "serif", "size": 23,
     "text": "REPLACE ME: one or two sentences on the shape of the week."},
    {"type": "week_plan", "days": days},
    {"type": "stats", "items": [[str(total), "lessons"],
                                [str(sum(1 for d in days if d["entries"])), "teaching days"],
                                [max((wx[d]["hi"] for d in wx), default="–",
                                     key=lambda v: int(v.rstrip("°"))), "warmest day"]]},
    {"type": "checklist", "groups": [["THIS WEEK", []]], "blank": 4},
    {"type": "fact", "head": "ONE TRUE THING",
     "text": "REPLACE ME: a true, checkable fact tied to something in this week."},
    {"type": "signoff", "text": "Have a good week.", "stamp": "PRINTED BY AN AGENT"},
]}
os.makedirs(os.path.dirname(os.path.expanduser(a.out)) or ".", exist_ok=True)
with open(os.path.expanduser(a.out), "w", encoding="utf-8") as fh:
    json.dump(spec, fh, indent=2, ensure_ascii=False)
print(f"wrote {a.out}: {total} lessons over {a.days} days"
      f"{'' if wx else ' (no forecast)'}. Now edit it: add duties, meetings and "
      "personal events, and replace both REPLACE ME lines.")
