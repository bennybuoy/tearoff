#!/usr/bin/env python3
"""Fetch the computed facts for one day, as JSON ready to paste into an edition.

  facts.py --date 2026-03-12
  facts.py --date 2026-03-12 --lat 51.51 --lon -0.13 --place LONDON

Prints:
  weather   -> paste as the newspaper edition's "weather" block
               (then add your own "notes", "bands", "mark_hours")
  sky_at    -> per-hour {kind, temp, rain} to build the gig edition's "sky" row
  moon, numbers, weekday -> as labelled

Forecasts come from open-meteo.com (free, no key; up to 16 days ahead).
"""
import argparse
import datetime as dt
import json
import math
import sys
import time
import urllib.request

from briefing import CONFIG

ap = argparse.ArgumentParser()
ap.add_argument("--date", help="YYYY-MM-DD: one day in detail")
ap.add_argument("--week", help="YYYY-MM-DD: seven days from this date, one line each")
ap.add_argument("--lat", type=float, default=CONFIG["lat"])
ap.add_argument("--lon", type=float, default=CONFIG["lon"])
ap.add_argument("--place", default=CONFIG["place"])
a = ap.parse_args()
if not a.date and not a.week:
    ap.error("give --date or --week")
if a.lat is None or a.lon is None:
    sys.exit("No location set. Pass --lat and --lon, or run:  "
             "tearoff setup --lat <latitude> --lon <longitude> --place <NAME>")


def get(url):
    err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                return json.load(r)
        except OSError as exc:
            err = exc
            time.sleep(3)
    sys.exit(f"Could not reach open-meteo after 4 tries ({err}). "
             "Wait a minute and run this again; do not invent weather.")


def kind_of(code, rain):
    return "rain" if rain >= 50 or code >= 51 else "cloud" if code in (2, 3, 45, 48) else "sun"


if a.week:
    d0 = dt.date.fromisoformat(a.week)
    d1 = d0 + dt.timedelta(days=6)
    w = get("https://api.open-meteo.com/v1/forecast"
            f"?latitude={a.lat}&longitude={a.lon}"
            "&daily=temperature_2m_max,temperature_2m_min,weathercode,"
            "precipitation_probability_max,uv_index_max"
            f"&timezone=auto&start_date={d0}&end_date={d1}")["daily"]
    print(json.dumps({"place": a.place, "week": [
        {"date": w["time"][i], "weekday": dt.date.fromisoformat(w["time"][i]).strftime("%A"),
         "kind": kind_of(w["weathercode"][i], w["precipitation_probability_max"][i] or 0),
         "hi": f"{round(w['temperature_2m_max'][i])}°",
         "lo": f"{round(w['temperature_2m_min'][i])}°",
         "rain": w["precipitation_probability_max"][i],
         "uv": round(w["uv_index_max"][i] or 0)}
        for i in range(len(w["time"]))]}, indent=2, ensure_ascii=False))
    sys.exit()

day = dt.date.fromisoformat(a.date)

url = ("https://api.open-meteo.com/v1/forecast"
       f"?latitude={a.lat}&longitude={a.lon}"
       "&hourly=temperature_2m,precipitation_probability,weathercode,uv_index"
       "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,"
       "uv_index_max,precipitation_probability_max"
       f"&timezone=auto&start_date={a.date}&end_date={a.date}")
w = None
for attempt in range(4):
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            w = json.load(r)
        break
    except OSError as exc:
        err = exc
        time.sleep(3)
if w is None:
    sys.exit(f"Could not reach open-meteo after 4 tries ({err}). "
             "Wait a minute and run this again; do not invent weather.")
h, d = w["hourly"], w["daily"]


def clock(iso):                      # "2026-03-12T06:48" -> "6:48"
    t = dt.datetime.fromisoformat(iso)
    return f"{t.hour % 12 or 12}:{t.minute:02d}", t


rise_s, rise = clock(d["sunrise"][0])
set_s, sset = clock(d["sunset"][0])
mins = int((sset - rise).total_seconds() // 60)
uv = round(d["uv_index_max"][0])
uv_word = ("low" if uv < 3 else "moderate" if uv < 6 else "high" if uv < 8
           else "very high" if uv < 11 else "extreme")

hours = list(range(6, 23))
weather = {
    "place": a.place,
    "hours": hours,
    "temp": [h["temperature_2m"][i] for i in hours],
    "rain": [h["precipitation_probability"][i] for i in hours],
    "lo": round(d["temperature_2m_min"][0]),
    "hi": round(d["temperature_2m_max"][0]),
    "sunrise": rise_s, "sunset": set_s,
    "daylight": f"{mins // 60}h {mins % 60:02d}m",
    "uv": uv, "uv_word": uv_word,
}

sky_at = {}
for i in range(24):
    code, rain = h["weathercode"][i], h["precipitation_probability"][i]
    night = i < rise.hour + 1 or i > sset.hour
    kind = ("rain" if rain >= 50 or code >= 51 else
            "moon" if night else
            "cloud" if code in (2, 3, 45, 48) else "sun")
    sky_at[f"{i:02d}:00"] = {"kind": kind,
                             "temp": f"{round(h['temperature_2m'][i])}°",
                             "rain": rain}

ref = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
now = dt.datetime(day.year, day.month, day.day, 9, tzinfo=dt.timezone.utc)
p = ((now - ref).total_seconds() / 86400 / 29.530588853) % 1
names = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous",
         "Full moon", "Waning gibbous", "Last quarter", "Waning crescent"]
xmas = dt.date(day.year, 12, 25)
if xmas < day:
    xmas = dt.date(day.year + 1, 12, 25)

print(json.dumps({
    "weekday": day.strftime("%A"),
    "weather": weather,
    "sky_at": sky_at,
    "moon": {"phase": names[int(p * 8 + 0.5) % 8],
             "lit_percent": round((1 - math.cos(2 * math.pi * p)) / 2 * 100)},
    "numbers": [[str(day.timetuple().tm_yday), f"day of {day.year}"],
                [str((xmas - day).days), "sleeps to Christmas"],
                [f"{mins // 60}:{mins % 60:02d}", "hours of daylight"]],
}, indent=2, ensure_ascii=False))
