#!/usr/bin/env python3
"""Rebuild docs/gallery from the example files.

Run from the repo root:  python3 tools/make_gallery.py

It ignores your personal tearoff config on purpose, so nothing from your own
setup (masthead name, town, printer) can end up in a published image.
"""
import json
import os
import sys

os.environ["TEAROFF_CONFIG"] = os.path.join(os.path.dirname(__file__), "no-such-config.json")
for var in ("TEAROFF_PRINTER", "BRIEFING_PRINTER", "TEAROFF_WIDTH"):
    os.environ.pop(var, None)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "tearoff", "scripts"))
sys.argv = ["make_gallery"]

from PIL import Image  # noqa: E402

import briefing as N  # noqa: E402
import briefing_gig as G  # noqa: E402
from widgets import render_spec, sampler  # noqa: E402

EX = os.path.join(ROOT, "skills", "tearoff", "examples") + os.sep
OUT = os.path.join(ROOT, "docs", "gallery")
os.makedirs(OUT, exist_ok=True)
for old in os.listdir(OUT):
    if old.endswith(".png"):
        os.remove(os.path.join(OUT, old))
W = 576


def save(im, name):
    im.save(os.path.join(OUT, name + ".png"))
    return im


def spec(widgets, date="2026-03-13"):
    return render_spec({"date": date, "widgets": widgets}, W)[0]


news = save(N.render(W, N.load_edition(EX + "newspaper-event-day.json")), "newspaper")
G.E.clear()
G.E.update(N.load_edition(EX + "gig-event-day.json"))
gig = save(G.render(W, G.body() + [G.main_end]), "gig-poster")
save(G.render(W, [G.card_alone]), "pocket-card")
week = save(render_spec(json.load(open(EX + "week-ahead.json")), W)[0], "week-ahead")
ms = render_spec(json.load(open(EX + "meals-and-shopping.json")), W)
save(ms[0], "meal-plan")
save(ms[1], "shopping-list")

wx = save(spec([
    {"type": "weather_chart", "place": "RIVERTON", "hours": list(range(6, 23)),
     "temp": [14, 15, 17, 20, 23, 25, 27, 28, 28, 27, 26, 25, 23, 21, 20, 18, 17],
     "rain": [0, 0, 0, 0, 0, 0, 2, 5, 10, 22, 28, 45, 61, 55, 35, 20, 12],
     "lo": 14, "hi": 28, "sunrise": "6:49", "sunset": "7:20", "uv": 6, "uv_word": "high",
     "notes": ["Hot and dry until three, then a good chance of an evening storm."],
     "bands": [[8.58, 14.58, "SCHOOL", False]], "mark_hours": [18]},
    {"type": "sky_row", "title": "THE SKY",
     "cells": [["8 am", "sun", "17°", ""], ["noon", "sun", "27°", "peak"],
               ["3 pm", "cloud", "27°", ""], ["6 pm", "rain", "23°", "61%"],
               ["9 pm", "moon", "18°", ""]], "note": ""},
    {"type": "sun_arc", "sunrise": "06:49", "sunset": "19:20", "mark": "14:35",
     "mark_label": "bell"},
    {"type": "moon_week", "start": "2026-03-13"},
    {"type": "gauge", "label": "UV INDEX", "value": 6, "min": 0, "max": 11,
     "word": "high", "ticks": [0, 3, 6, 8, 11]},
    {"type": "sparkline", "rows": [["Highs this week", [22, 23, 25, 28, 21, 19, 20], "°"],
                                   ["Rain chance", [5, 10, 20, 61, 55, 35, 10], "%"]]},
]), "weather")

receipt = save(spec([
    {"type": "receipt", "store": "CLAUDE CODE",
     "header": ["Refactor the billing module", "Fri 13 Mar 2026  4:12 pm"],
     "lines": [["Wall-clock time", "1 h 26 min"], ["Your prompts", "9"],
               ["Model calls", "64"], ["Tool calls", "118"], ["---", ""],
               ["Input tokens", "412"], ["Cache writes", "508.3k"],
               ["Cache reads", "11.74M"], ["Output tokens", "146.2k"], ["---", ""],
               ["Opus 5.5", "$7.31"], ["Haiku 5.5", "$0.04"]],
     "total": ["APPROX COST", "US$7.35"],
     "footer": "API-equivalent estimate at list prices. Not a bill."},
    {"type": "heading", "text": "WHAT GOT DONE"},
    {"type": "checklist", "style": "circle", "size": 22,
     "items": ["Split invoices.py into three modules", "All 212 tests pass",
               "Opened a draft pull request"]},
    {"type": "callout", "label": "NEEDS YOU", "size": 23,
     "text": "Two migrations need a review before merge."},
]), "job-receipt")

arts = [save(spec([{"type": "art", "style": s, "seed": 5}]), f"art-{s}")
        for s in ("flow", "contours", "ridges", "mandala", "phyllotaxis")]
fun = save(spec([
    {"type": "punnett", "p1": "Aa", "p2": "Aa", "solved": True, "title": "MONOHYBRID CROSS"},
    {"type": "maze", "cols": 14, "rows": 14, "seed": 2, "title": "FIND THE WAY OUT"},
    {"type": "sudoku", "level": "medium", "seed": 4},
    {"type": "coupon", "kicker": "THIS COUPON IS GOOD FOR", "text": "ONE SLEEP-IN",
     "to": "Sam", "from": "The kids", "expires": "31 Dec 2026"},
]), "class-and-fun")
save(spec([{"type": "title", "text": "SATURDAY JOBS", "sub": "Sat 14 Mar 2026"},
           {"type": "checklist", "size": 28, "blank": 2,
            "items": ["Mow the lawn", "Bins out", "Collect the parcel", "Start the jigsaw"]}]),
     "todo")
for i, im in enumerate(render_spec(sampler(), W)):
    save(im, f"sampler-{i + 1}")


def sheet(images, height, name):
    pad = 28
    out = Image.new("L", (len(images) * (W + pad) + pad, height + 2 * pad), 210)
    for i, im in enumerate(images):
        out.paste(im.convert("L").crop((0, 0, W, min(height, im.size[1]))),
                  (pad + i * (W + pad), pad))
    out.resize((out.size[0] // 2, out.size[1] // 2), Image.LANCZOS).save(
        os.path.join(OUT, name + ".png"))


sheet([news, gig, week, wx, receipt, fun], 1500, "hero")
sheet(arts, 640, "art-row")
print(f"{len(os.listdir(OUT))} images written to {OUT}")
