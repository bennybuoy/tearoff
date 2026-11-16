#!/usr/bin/env python3
"""tearoff widgets: build any print from a list of widgets.

  widgets.py --list                         names and one-line descriptions
  widgets.py --doc                          full reference with example JSON
  widgets.py --spec strip.json --preview-dir DIR      render and slice
  widgets.py --spec strip.json --print                render and print
  widgets.py --sampler --preview-dir DIR [--print]    one of everything

A spec is JSON:  {"date": "2026-03-13", "widgets": [ {"type": "...", ...}, ... ]}
Widgets print top to bottom. {"type": "cut"} ends a print job there, so the
cutter separates the pieces. Any widget may carry "gap": N to change the space
after it (default 20).
"""
import argparse
import calendar
import datetime as dt
import json
import math
import os
import random
import subprocess
import tempfile

from PIL import Image, ImageDraw

import briefing as N
import briefing_gig as G
from briefing import Sheet, moon_phase

WIDGETS = {}


def widget(name, group, doc, example):
    def deco(fn):
        WIDGETS[name] = {"fn": fn, "group": group, "doc": doc,
                         "example": example}
        return fn
    return deco


def _date(o, ctx):
    v = o.get("date") or ctx.get("date")
    return dt.date.fromisoformat(v) if v else dt.date.today()


def _gig(fn, S, **E):
    G.E.clear()
    G.E.update(E)
    fn(S)


def _fit(S, font, text, width, start, floor=14):
    size = start
    while S.f(font, size).getlength(text) > width and size > floor:
        size -= 2
    return S.f(font, size)


def _moon(S, cx, cy, r, p):
    c = math.cos(2 * math.pi * p)
    for yy in range(-r, r + 1):
        hw = math.sqrt(r * r - yy * yy)
        for xx in range(-r, r + 1):
            if abs(xx) > hw:
                continue
            lit = (xx > hw * c) if p < 0.5 else (xx < -hw * c)
            if not lit:
                S.img.putpixel((int(cx) - xx, int(cy) + yy), 0)
    S.d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=S.s(3))


def _hm(t):
    h, m = t.split(":")
    return int(h) + int(m) / 60


def _clock(t):
    h, m = t.split(":")
    h = int(h)
    return f"{h % 12 or 12}:{m} {'am' if h < 12 else 'pm'}"


# ═════════════════════════════ structure ═══════════════════════════════════
@widget("masthead", "structure", "Newspaper masthead: giant weekday, date, "
        "issue number.", {"title": "THE DAILY BRIEFING", "issue": 5,
                          "week": "WK 6"})
def w_masthead(S, o, ctx):
    N.masthead(S, {"date": _date(o, ctx), "issue": o.get("issue", 1),
                   "week": o.get("week", ""),
                   "masthead": o.get("title", N.CONFIG["masthead"])})


@widget("poster_header", "structure", "Black gig-poster header with halftone "
        "sunburst. title max 9 letters; banner max 26.",
        {"top": "ONE DAY ONLY", "title": "FRIDAY",
         "banner": "THE LAST LAP TOUR",
         "strip": "13 MAR 2026 · RIVERTON"})
def w_poster_header(S, o, ctx):
    _gig(G.header, S, top=o.get("top", ""), title=o["title"],
         tour=o.get("banner", " "), strip=o.get("strip", ""))


@widget("bill", "structure", "Festival line-up: headliner huge, supports "
        "smaller. headliner is 1-2 words, each its own line.",
        {"kicker": "ON THE BILL", "headliner": ["11PHY"],
         "second": "8MA  +  9MA", "third": ["BUS BAY DUTY  ·  FRIDAY"],
         "fourth": "doors 8:15"})
def w_bill(S, o, ctx):
    _gig(G.lineup, S, lineup_kicker=o.get("kicker", ""),
         headliner=o["headliner"], second=o.get("second", ""),
         third=o.get("third", []), fourth=o.get("fourth", ""))


@widget("title", "structure", "One big black title line with an optional "
        "small line under it. For lists and notes.",
        {"text": "SATURDAY JOBS", "sub": "Sat 21 Nov"})
def w_title(S, o, ctx):
    W, M = S.W, S.M
    S.y += S.s(8)
    S.rule(6, 6)
    f = _fit(S, "black", o["text"], W - 2 * M, o.get("size", 64))
    S.text(M, S.y - f.size * 0.18, o["text"], f)
    S.y += round(f.size * 1.02)
    if o.get("sub"):
        S.spaced(M, S.y, o["sub"].upper(), S.f("mono", 18), 4)
        S.y += S.s(30)
    S.rule(2, 0)


@widget("heading", "structure", "Section heading. style 'tab' (label + rule) "
        "or 'bar' (full-width black bar).", {"text": "THE DAY", "style": "tab"})
def w_heading(S, o, ctx):
    if o.get("style", "tab") == "bar":
        G.bar(S, o["text"])
        S.y -= S.s(18)
    else:
        S.section(o["text"])
        S.y -= S.s(16)


@widget("headline", "structure", "Big italic serif headline (1-3 short lines) "
        "with an optional sentence under it.",
        {"lines": ["Three classes,", "one long lunch."],
         "deck": "Two before recess, one after, and nothing until Monday."})
def w_headline(S, o, ctx):
    S.y -= S.s(14)
    N.headline(S, {"headline": o["lines"], "deck": o.get("deck", "")})


@widget("text", "structure", "A paragraph. font serif|sans|serifi|bold, "
        "align left|center.", {"text": "Plain words go here. They wrap on "
                               "their own and can run to a few lines.",
                               "font": "serif", "size": 23, "align": "left"})
def w_text(S, o, ctx):
    f = S.f(o.get("font", "serif"), o.get("size", 23))
    if o.get("align") == "center":
        for line in S.wrap(o["text"], f, S.W - 2 * S.M):
            S.text(S.W / 2, S.y, line, f, anchor="ma")
            S.y += round(f.size * 1.3)
    else:
        S.para(o["text"], f, lead=1.3)


@widget("callout", "structure", "Boxed note with a small label on the border. "
        "For the one thing not to miss.",
        {"label": "DON'T FORGET", "text": "9MA is in Lab 1 today, not M2."})
def w_callout(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    pad = S.s(18)
    top = S.y + S.s(12)
    S.y = top + pad + S.s(6)
    f = S.f("bold", o.get("size", 25))
    for line in S.wrap(o["text"], f, W - 2 * M - 2 * pad):
        S.text(M + pad, S.y, line, f)
        S.y += round(f.size * 1.28)
    S.y += pad
    d.rectangle([M, top, W - M, S.y], outline=0, width=S.s(4))
    if o.get("label"):
        fk = S.f("mono", 17)
        kw = sum(fk.getlength(c) + S.s(3) for c in o["label"]) + S.s(16)
        d.rectangle([M + pad, top - S.s(13), M + pad + kw, top + S.s(15)],
                    fill=0)
        S.spaced(M + pad + S.s(9), top - S.s(11), o["label"], fk, 3, fill=255)


@widget("divider", "structure", "A decorative break. style rule|double|dots|"
        "wave|zigzag|helix|stars.", {"style": "wave"})
def w_divider(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    st = o.get("style", "rule")
    if st == "rule":
        S.rule(2, 0)
    elif st == "double":
        S.rule(6, 3)
        S.rule(2, 0)
    elif st == "dots":
        for x in range(M, W - M, S.s(14)):
            d.ellipse([x, S.y, x + S.s(5), S.y + S.s(5)], fill=0)
        S.y += S.s(6)
    elif st in ("wave", "zigzag"):
        h = S.s(9)
        pts = []
        for x in range(M, W - M + 1, 2 if st == "wave" else S.s(14)):
            k = (x - M) / S.s(28) * 2 * math.pi
            y = math.sin(k) if st == "wave" else (1 if (x - M) // S.s(14) % 2 else -1)
            pts.append((x, S.y + h + y * h))
        d.line(pts, fill=0, width=S.s(3), joint="curve")
        S.y += 2 * h + S.s(2)
    elif st == "helix":
        N.helix(S, height=64, turns=4.5)
    elif st == "stars":
        n = 5
        for i in range(n):
            cx = W / 2 + (i - (n - 1) / 2) * S.s(46)
            r = S.s(9 if i != n // 2 else 13)
            pts = []
            for k in range(10):
                a = -math.pi / 2 + k * math.pi / 5
                rr = r if k % 2 == 0 else r * 0.42
                pts.append((cx + rr * math.cos(a), S.y + S.s(14) + rr * math.sin(a)))
            d.polygon(pts, fill=0)
        S.y += S.s(28)


@widget("signoff", "structure", "Closing line in bold italic, plus a tiny "
        "stamp line.", {"text": "Have a good Friday, Sam.",
                        "stamp": "NO. 005  ·  PRINTED BY AN AGENT"})
def w_signoff(S, o, ctx):
    S.y += S.s(6)
    f = _fit(S, "serifbi", o["text"], S.W - 2 * S.M, 36)
    S.text(S.W / 2, S.y, o["text"], f, anchor="ma")
    S.y += S.s(60)
    S.rule(2, 3)
    S.rule(6, 10)
    if o.get("stamp"):
        S.spaced(S.W / 2, S.y, o["stamp"], S.f("mono", 15), 3, anchor="m")
        S.y += S.s(26)


# ═════════════════════════════ the day ═════════════════════════════════════
@widget("timeline", "day", "To-scale day timeline. rows are [start, end, kind, "
        "title, detail]; kind is class|meet|duty|free. Nothing under 20 min.",
        {"title": "THE SCHOOL DAY", "span": ["08:00", "14:50"],
         "rows": [["08:15", "08:35", "duty", "DUTY  Bus bay", ""],
                  ["09:35", "10:35", "class", "8MA", "Year 8 Maths  ·  M2"],
                  ["10:55", "11:55", "class", "11PHY", "Year 11 Physics  ·  Lab 1"],
                  ["13:35", "14:35", "class", "9MA", "Year 9 Maths  ·  M2"]],
         "notes": []})
def w_timeline(S, o, ctx):
    S.y -= S.s(26)
    N.day(S, {"day": o["rows"], "day_span": o["span"],
              "day_notes": o.get("notes", []),
              "day_title": o.get("title", "THE DAY")})


@widget("agenda", "day", "Running order: time chips down the left. rows are "
        "[time, what, where, note]. '__:__' draws a write-in box.",
        {"title": "RUNNING ORDER",
         "rows": [["08:15", "Yard duty", "Bus bay", ""],
                  ["10:55", "11PHY", "Lab 1", "Half the class is at the careers expo."],
                  ["__:__", "Pickup", "Post office", ""]]})
def w_agenda(S, o, ctx):
    S.y -= S.s(30)
    _gig(G.set_times, S, stages=[[o.get("title", "RUNNING ORDER"), o["rows"]]])


@widget("checklist", "day", "Tick-box list. Give 'items' or 'groups' "
        "([[LABEL, [items]], ...]). blank adds write-in lines. style box|circle. "
        "size 23 normal, 28 for a fridge list.",
        {"groups": [["BEFORE SCHOOL", ["Bus bay duty from 8:15."]],
                    ["AFTER SCHOOL", ["Collect the parcel."]]],
         "blank": 2, "style": "box", "size": 23})
def w_checklist(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    size = o.get("size", 23)
    f = S.f("sans", size)
    lh = round(f.size * 1.28)
    bs = S.s(round(size * 1.05))
    tx = M + bs + S.s(14)
    circle = o.get("style") == "circle"

    def box(y):
        if circle:
            d.ellipse([M, y, M + bs, y + bs], outline=0, width=S.s(3))
        else:
            d.rectangle([M, y, M + bs, y + bs], outline=0, width=S.s(3))

    groups = o.get("groups") or [["", o.get("items", [])]]
    for label, items in groups:
        if label:
            S.spaced(M, S.y, label, S.f("mono", 17), 4)
            S.y += S.s(30)
        for item in items:
            box(S.y + S.s(4))
            for line in S.wrap(item, f, W - M - tx):
                S.text(tx, S.y, line, f)
                S.y += lh
            S.y += S.s(round(size * 0.45))
        S.y += S.s(6)
    for _ in range(o.get("blank", 0)):
        box(S.y)
        for xx in range(int(tx), W - M, S.s(8)):
            d.rectangle([xx, S.y + bs - 1, xx + S.s(3), S.y + bs], fill=0)
        S.y += bs + S.s(round(size * 0.9))
    S.y -= S.s(8)


@widget("keyvalue", "day", "Label ..... value rows with dot leaders. Good for "
        "tomorrow's classes, prices, room lists.",
        {"rows": [["08:35", "12PHY", "Lab 3"], ["10:55", "9MA", "M2"]]})
def w_keyvalue(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    fm, fb, fs = S.f("mono", 21), S.f("bold", 24), S.f("sans", 21)
    for row in o["rows"]:
        if len(row) == 3:
            tm, what, where = row
            S.text(M, S.y + S.s(2), tm, fm)
            xw = M + S.s(86)
        else:
            what, where = row
            xw = M
        S.text(xw, S.y, what, fb)
        S.text(W - M, S.y + S.s(2), where, fs, anchor="ra")
        xa = xw + fb.getlength(what) + S.s(10)
        xb = W - M - fs.getlength(where) - S.s(10)
        for xx in range(int(xa), int(xb), S.s(8)):
            d.rectangle([xx, S.y + S.s(22), xx + S.s(2), S.y + S.s(24)], fill=0)
        S.y += S.s(38)
    S.y -= S.s(8)


@widget("table", "day", "Small grid table. head is the column names; rows are "
        "lists of the same length. Up to 4 columns of short text.",
        {"head": ["Class", "Room", "Topic"],
         "rows": [["12PHY", "Lab 3", "Circular motion"], ["9MA", "M2", "Surds"]]})
def w_table(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    n = len(o["head"])
    cw = (W - 2 * M) / n
    rh = S.s(40)
    d.rectangle([M, S.y, W - M, S.y + rh], fill=0)
    for i, hname in enumerate(o["head"]):
        S.spaced(M + cw * i + S.s(10), S.y + S.s(8), hname.upper(),
                 S.f("mono", 17), 3, fill=255)
    S.y += rh
    for row in o["rows"]:
        for i, cell in enumerate(row):
            f = _fit(S, "bold" if i == 0 else "sans", str(cell), cw - S.s(16), 22)
            S.text(M + cw * i + S.s(10), S.y + rh / 2, str(cell), f, anchor="lm")
        S.y += rh
        d.rectangle([M, S.y - 1, W - M, S.y], fill=0)
    top = S.y - rh * (len(o["rows"]) + 1)
    for i in range(n + 1):
        x = M + cw * i
        d.rectangle([x - 1, top, x, S.y], fill=0)


@widget("inbox", "day", "Inbox highlights: a black label chip and a sentence "
        "each. Up to 6.", {"title": "FROM YOUR INBOX",
                           "items": [["PARCEL", "Your walking boots are out "
                                      "for delivery today."],
                                     ["LIBRARY", "Two books are due back on Friday."]]})
def w_inbox(S, o, ctx):
    S.y -= S.s(30)
    _gig(G.inbox, S, inbox=o["items"], inbox_title=o.get("title", "INBOX"))


@widget("ticket", "day", "Ticket stub for an event. act is 1-3 words; cells "
        "is exactly 4 [LABEL, value] pairs.",
        {"kicker": "TONIGHT  ·  SAT 14 MAR", "act": "MOVIE NIGHT",
         "tour": "WITH THE KIDS", "venue": "The couch, front row",
         "cells": [["DOORS", "7:00"], ["ROW", "A"], ["SEATS", "1–4"],
                   ["SNACKS", "YES"]],
         "foot": "Popcorn is not optional", "stub": "ADMIT FOUR"})
def w_ticket(S, o, ctx):
    N.ticket(S, {"ticket": o, "gap": o.get("gap_text", "")})
    S.y -= S.s(10)


@widget("pocket_card", "day", "Black tear-off card of must-not-forget facts. "
        "times is exactly 3 pairs. Put a cut before it to separate it.",
        {"times": [["LEAVE", "3:45"], ["TRAIN", "4:05"], ["DINNER", "5:30"]],
         "seats": "PLATFORM 1  ·  RIVERTON",
         "home_k": "LAST TRAIN", "home": "11:12 pm",
         "home_d": "Central, all stops to Riverton",
         "rules": "TRAVEL CARD  ·  JACKET  ·  PHONE CHARGED"})
def w_pocket_card(S, o, ctx):
    _gig(G.card_alone, S, card=o)
    S.y -= S.s(22)


@widget("rules_box", "day", "Heavy-bordered rules list. rows are [allowed, "
        "headline, detail]: false draws a crossed circle, true a tick.",
        {"title": "CONDITIONS OF ENTRY",
         "rows": [[False, "No umbrellas.", "Ponchos are fine."],
                  [True, "Tickets on your phone", "before you leave."]],
         "source": "From the venue's email."})
def w_rules_box(S, o, ctx):
    S.y -= S.s(30)
    _gig(G.entry, S, entry=o["rows"], entry_title=o.get("title", "RULES"),
         entry_src=o.get("source", ""))


AISLES = [
    ("FRUIT & VEG", "apple banana avocado tomato potato onion garlic carrot lettuce "
     "spinach salad cucumber capsicum mushroom broccoli zucchini pumpkin lemon lime "
     "orange mandarin berries strawberr blueberr grape pear mango melon herb basil "
     "coriander parsley ginger chilli corn celery beans peas kale cabbage "
     "cauliflower sweet potato spring onion fruit veg"),
    ("BAKERY", "bread roll wrap bagel croissant muffin crumpet sourdough pita "
     "tortilla baguette bun"),
    ("MEAT & DELI", "chicken beef mince steak lamb pork bacon ham sausage salami "
     "fish salmon tuna steak prawn turkey chorizo deli snag"),
    ("DAIRY & FRIDGE", "milk cheese butter yoghurt yogurt cream egg eggs feta "
     "parmesan mozzarella haloumi margarine custard dip hummus tofu juice"),
    ("PANTRY", "pasta rice flour sugar oil vinegar sauce stock tin tinned can "
     "canned beans lentil chickpea cereal oats muesli honey jam vegemite peanut "
     "spice salt pepper noodle soup coffee tea cocoa baking yeast soy tomato paste "
     "passata coconut milk curry taco spread nut seeds"),
    ("SNACKS & DRINKS", "chips chocolate biscuit cracker lolly lollies popcorn "
     "muesli bar soft drink cola lemonade water mineral beer wine cordial snack "
     "nuts ice cream cone"),
    ("FROZEN", "frozen ice cream peas pizza nuggets fish fingers ice berries "
     "pastry dumpling"),
    ("HOUSEHOLD", "toilet paper tissue towel detergent dishwash dishwasher sponge "
     "bin bag bags foil wrap baking paper cling soap shampoo conditioner "
     "toothpaste toothbrush deodorant razor laundry bleach spray cleaner battery "
     "batteries light bulb sunscreen nappies wipes pet dog cat litter"),
]


def sort_into_aisles(items):
    """Group loose shopping items by supermarket section, in walking order."""
    groups = {name: [] for name, _ in AISLES}
    other = []
    for item in items:
        low = " " + item.lower() + " "
        best, best_len = None, 0
        for word, name in (("frozen", "FROZEN"), ("tinned", "PANTRY"),
                           ("canned", "PANTRY"), ("dried", "PANTRY")):
            if " " + word in low:       # how it is packed beats what it is
                best, best_len = name, 99
        for name, words in AISLES:
            for kw in words.split():
                if (" " + kw in low) and len(kw) > best_len:
                    best, best_len = name, len(kw)
        (groups[best] if best else other).append(item)
    out = [[name, groups[name]] for name, _ in AISLES if groups[name]]
    if other:
        out.append(["EVERYTHING ELSE", other])
    return out


@widget("shopping_list", "day", "Shopping list in two columns, grouped by "
        "aisle. Give 'groups' ([[AISLE, [items]], ...]) or loose 'items', which "
        "are sorted into aisles automatically.",
        {"title": "SHOPPING", "store": "Corner supermarket",
         "items": ["Milk", "Bananas", "2 avocados", "Sourdough", "Chicken thighs",
                   "Eggs", "Pasta", "Tinned tomatoes", "Dishwasher tablets"],
         "blank": 2})
def w_shopping_list(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    groups = o.get("groups") or sort_into_aisles(o.get("items", []))
    total = sum(len(g[1]) for g in groups)
    S.rule(6, 6)
    f = _fit(S, "black", o.get("title", "SHOPPING"), W - 2 * M, 60)
    S.text(M, S.y - f.size * 0.18, o.get("title", "SHOPPING"), f)
    S.y += round(f.size * 1.02)
    sub = "  ·  ".join(v for v in (o.get("store"), o.get("when"),
                                   f"{total} items") if v).upper()
    S.text(M, S.y, sub, _fit(S, "mono", sub, W - 2 * M, 18, 11))
    S.y += S.s(30)
    S.rule(2, 14)
    fi = S.f("sans", o.get("size", 24))
    lh = round(fi.size * 1.2)
    bs = S.s(24)
    gut = S.s(16)
    colw = (W - 2 * M - gut) / 2
    tw = colw - bs - S.s(12)
    for name, items in groups:
        fk = S.f("mono", 17)
        kw = sum(fk.getlength(c) + S.s(3) for c in name) + S.s(16)
        d.rectangle([M, S.y, M + kw, S.y + S.s(28)], fill=0)
        S.spaced(M + S.s(9), S.y + S.s(3), name, fk, 3, fill=255)
        d.rectangle([M + kw + S.s(8), S.y + S.s(13), W - M, S.y + S.s(14)], fill=0)
        S.y += S.s(40)
        for i in range(0, len(items), 2):
            rows = 1
            for k, item in enumerate(items[i:i + 2]):
                x = M + k * (colw + gut)
                d.rectangle([x, S.y + S.s(2), x + bs, S.y + S.s(2) + bs],
                            outline=0, width=S.s(3))
                lines = S.wrap(item[:1].upper() + item[1:], fi, tw)
                rows = max(rows, len(lines))
                for j, line in enumerate(lines):
                    S.text(x + bs + S.s(12), S.y + j * lh - S.s(2), line, fi)
            S.y += rows * lh + S.s(12)
        S.y += S.s(8)
    for i in range(o.get("blank", 2)):
        for k in range(2):
            x = M + k * (colw + gut)
            d.rectangle([x, S.y + S.s(2), x + bs, S.y + S.s(2) + bs], outline=0,
                        width=S.s(3))
            for xx in range(int(x + bs + S.s(12)), int(x + colw), S.s(8)):
                d.rectangle([xx, S.y + bs, xx + S.s(3), S.y + bs + 1], fill=0)
        S.y += lh + S.s(14)
    S.y -= S.s(6)


@widget("week_plan", "day", "The week ahead: one block per day with its "
        "entries ([time, what, where]), an optional note, and optional weather "
        "([kind, temp]; kind is sun|cloud|rain).",
        {"days": [{"date": "2026-03-16", "sky": ["sun", "26°"],
                   "entries": [["08:35", "12PHY", "Lab 3"], ["09:35", "9MA", "M2"],
                               ["13:35", "8MA", "M2"]], "note": ""},
                  {"date": "2026-03-17", "sky": ["rain", "21°"],
                   "entries": [["09:35", "10MA", "M5"], ["10:55", "11PHY", "Lab 1"]],
                   "note": "Faculty meeting after school."},
                  {"date": "2026-03-18", "sky": ["cloud", "20°"], "entries": [],
                   "note": ""}]})
def w_week_plan(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    bw = S.s(92)
    tx = M + bw + S.s(16)
    fm, fb, fs = S.f("mono", 19), S.f("bold", 22), S.f("sans", 19)
    for k, day in enumerate(o["days"]):
        date = dt.date.fromisoformat(day["date"])
        top = S.y
        d.rounded_rectangle([M, top, M + bw, top + S.s(78)], radius=S.s(10), fill=0)
        S.spaced(M + bw / 2, top + S.s(6), date.strftime("%a").upper(), S.f("mono", 18), 3,
                 fill=255, anchor="m")
        S.text(M + bw / 2, top + S.s(24), str(date.day), S.f("black", 38), fill=255,
               anchor="ma")
        if day.get("sky"):
            G.E.clear()
            G.E.update(date=date)
            G.icon(S, day["sky"][0], M + S.s(24), top + S.s(104), S.s(15))
            S.text(M + S.s(46), top + S.s(104), day["sky"][1], S.f("bold", 20), anchor="lm")
        y = top + S.s(2)
        for tm, what, where in day.get("entries", []):
            S.text(tx, y + S.s(2), tm, fm)
            S.text(tx + S.s(74), y, what, _fit(S, "bold", what, W - M - tx - S.s(74) - fs.getlength(where) - S.s(12), 22, 13))
            S.text(W - M, y + S.s(3), where, fs, anchor="ra")
            y += S.s(30)
        if not day.get("entries") and not day.get("note"):
            S.text(tx, y + S.s(2), "Nothing booked.", S.f("serifi", 21))
            y += S.s(30)
        if day.get("note"):
            fn = S.f("serifi", 20)
            for line in S.wrap(day["note"], fn, W - M - tx):
                S.text(tx, y + S.s(2), line, fn)
                y += S.s(26)
        S.y = max(y, top + S.s(124 if day.get("sky") else 82)) + S.s(8)
        if k < len(o["days"]) - 1:
            for x in range(M, W - M, S.s(8)):
                d.rectangle([x, S.y, x + S.s(3), S.y + 1], fill=0)
            S.y += S.s(12)


@widget("meal_plan", "home", "Dinners for the week: a day chip, the meal, an "
        "optional short note. rows are [DAY, meal, note].",
        {"title": "DINNERS", "rows": [["MON", "Chicken fried rice", "20 min"],
                                      ["TUE", "Tacos", ""],
                                      ["WED", "Pasta with pesto", "kids cook"],
                                      ["THU", "Leftovers", ""],
                                      ["FRI", "Fish and chips", "takeaway"]]})
def w_meal_plan(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    if o.get("title"):
        S.text(M, S.y - S.s(6), o["title"], S.f("black", 36))
        S.y += S.s(50)
    cw = S.s(74)
    for day, meal, note in o["rows"]:
        d.rounded_rectangle([M, S.y, M + cw, S.y + S.s(36)], radius=S.s(6), fill=0)
        S.text(M + cw / 2, S.y + S.s(17), day[:3].upper(), S.f("mono", 20), fill=255,
               anchor="mm")
        fb = S.f("bold", 24)
        y0 = S.y
        for line in S.wrap(meal, fb, W - M - (M + cw + S.s(14))):
            S.text(M + cw + S.s(14), S.y + S.s(2), line, fb)
            S.y += S.s(30)
        if note:
            S.text(M + cw + S.s(14), S.y, note, S.f("serifi", 20))
            S.y += S.s(26)
        S.y = max(S.y, y0 + S.s(36)) + S.s(12)
        d.rectangle([M, S.y - S.s(6), W - M, S.y - S.s(5)], fill=0)
    S.y -= S.s(4)


# ═════════════════════════════ numbers and sky ═════════════════════════════
@widget("weather_chart", "data", "Full weather block: big high, moon, hourly "
        "temperature curve over rain bars. Paste facts.py's weather block and "
        "add notes/bands/mark_hours.",
        {"place": "RIVERTON", "hours": list(range(6, 23)),
         "temp": [13, 14, 16, 18, 20, 22, 24, 25, 25, 24, 23, 22, 20, 19, 18, 16, 15],
         "rain": [0, 0, 0, 0, 0, 5, 10, 20, 40, 55, 45, 30, 15, 10, 5, 0, 0],
         "lo": 13, "hi": 25, "sunrise": "6:48", "sunset": "7:21",
         "uv": 6, "uv_word": "high",
         "notes": ["Warm and dry through lunch, then an afternoon shower."],
         "bands": [[8.58, 14.58, "SCHOOL", False]], "mark_hours": []})
def w_weather_chart(S, o, ctx):
    S.y -= S.s(26)
    N.weather(S, {"weather": o, "date": _date(o, ctx)})


@widget("sky_row", "data", "Row of 4-6 weather icons with times and temps. "
        "cells are [when, kind, temp, tag]; kind is sun|cloud|rain|moon.",
        {"title": "THE SKY", "cells": [["8 am", "sun", "16°", ""],
                                      ["noon", "sun", "24°", "peak"],
                                      ["3 pm", "rain", "24°", "55%"],
                                      ["6 pm", "cloud", "20°", ""],
                                      ["9 pm", "moon", "16°", ""]],
         "note": "One shower mid-afternoon."})
def w_sky_row(S, o, ctx):
    S.y -= S.s(30)
    _gig(G.sky, S, sky=o["cells"], sky_note=o.get("note", ""),
         sky_title=o.get("title", "THE SKY"), date=_date(o, ctx))


@widget("stats", "data", "2-4 big numbers side by side, each with a small "
        "label.", {"items": [["72", "day of 2026"], ["287", "sleeps to Christmas"],
                             ["12:33", "hours of daylight"]]})
def w_stats(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    items = o["items"]
    cw = (W - 2 * M) / len(items)
    S.rule(2, 14)
    for i, (num, lab) in enumerate(items):
        cx = M + cw * i + cw / 2
        f = _fit(S, "display", str(num), cw - S.s(16), 46)
        S.text(cx, S.y - S.s(8), str(num), f, anchor="ma")
        S.text(cx, S.y + S.s(52), lab, _fit(S, "sans", lab, cw - S.s(10), 17, 11),
               anchor="ma")
        if i:
            d.rectangle([M + cw * i, S.y, M + cw * i + 1, S.y + S.s(72)], fill=0)
    S.y += S.s(84)
    S.rule(2, 0)


@widget("countdown", "data", "Days until something: a huge number, plus one "
        "dot per day to cross off (up to 70).",
        {"label": "the summer holidays", "date": "2026-12-18", "dots": True})
def w_countdown(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    n = (dt.date.fromisoformat(o["date"]) - _date({}, ctx)).days
    num = str(max(n, 0))
    f = _fit(S, "black", num, S.s(250), 150)
    S.text(M, S.y - f.size * 0.22, num, f)
    x = M + f.getlength(num) + S.s(20)
    S.spaced(x, S.y + S.s(18), "DAY" if n == 1 else "DAYS", S.f("mono", 22), 6)
    S.text(x, S.y + S.s(48), "until", S.f("serifi", 26))
    fl = S.f("bold", 27)
    yy = S.y + S.s(82)
    for line in S.wrap(o["label"], fl, W - M - x):
        S.text(x, yy, line, fl)
        yy += S.s(34)
    S.y = max(S.y + round(f.size * 0.98), yy) + S.s(10)
    if o.get("dots", True) and 0 < n <= 70:
        per = 14
        gap = (W - 2 * M) / per
        r = gap * 0.34
        for i in range(n):
            cx = M + gap * (i % per) + gap / 2
            cy = S.y + gap * (i // per) + gap / 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=S.s(3))
        S.y += gap * math.ceil(n / per) + S.s(4)


@widget("progress", "data", "Labelled progress bars. rows are [label, value, "
        "max, right-hand text].",
        {"rows": [["Term 1", 6, 10, "week 6 of 10"],
                  ["2026", 72, 365, "20%"]]})
def w_progress(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    for label, val, mx, txt in o["rows"]:
        S.text(M, S.y, label, S.f("bold", 22))
        S.text(W - M, S.y + S.s(2), txt, S.f("sans", 20), anchor="ra")
        S.y += S.s(34)
        h = S.s(24)
        x1 = M + (W - 2 * M) * max(0, min(1, val / mx))
        d.rectangle([M, S.y, x1, S.y + h], fill=0)
        S.hatch([x1 + 2, S.y + 2, W - M - 2, S.y + h - 2], gap=8, weight=1)
        d.rectangle([M, S.y, W - M, S.y + h], outline=0, width=S.s(3))
        S.y += h + S.s(18)
    S.y -= S.s(18)


@widget("gauge", "data", "Half-circle dial with a needle. Good for UV, "
        "energy, marking pile.",
        {"label": "UV INDEX", "value": 6, "min": 0, "max": 11,
         "word": "high", "ticks": [0, 3, 6, 8, 11]})
def w_gauge(S, o, ctx):
    d, W = S.d, S.W
    R = S.s(150)
    cx, cy = W / 2, S.y + R + S.s(26)
    lo, hi = o.get("min", 0), o.get("max", 10)
    frac = max(0, min(1, (o["value"] - lo) / (hi - lo)))
    d.pieslice([cx - R, cy - R, cx + R, cy + R], 180, 180 + 180 * frac, fill=0)
    ri = R - S.s(34)
    d.pieslice([cx - ri, cy - ri, cx + ri, cy + ri], 180, 360, fill=255)
    d.arc([cx - R, cy - R, cx + R, cy + R], 180, 360, fill=0, width=S.s(4))
    d.arc([cx - ri, cy - ri, cx + ri, cy + ri], 180, 360, fill=0, width=S.s(3))
    d.rectangle([cx - R, cy - 1, cx + R, cy + S.s(2)], fill=0)
    for t in o.get("ticks", []):
        a = math.pi + math.pi * (t - lo) / (hi - lo)
        S.text(cx + (R + S.s(16)) * math.cos(a), cy + (R + S.s(16)) * math.sin(a),
               str(t), S.f("mono", 17), anchor="mm")
    a = math.pi + math.pi * frac
    d.line([cx, cy, cx + (ri - S.s(8)) * math.cos(a), cy + (ri - S.s(8)) * math.sin(a)],
           fill=0, width=S.s(6))
    d.ellipse([cx - S.s(11), cy - S.s(11), cx + S.s(11), cy + S.s(11)], fill=0)
    S.y = cy + S.s(14)
    S.spaced(cx, S.y, o["label"], S.f("mono", 19), 5, anchor="m")
    S.y += S.s(28)
    txt = f"{o['value']}  {o.get('word', '')}".strip()
    S.text(cx, S.y - S.s(6), txt, S.f("black", 40), anchor="ma")
    S.y += S.s(50)


@widget("sparkline", "data", "A tiny trend line with first and last values "
        "labelled. One row per series: [label, [values], unit].",
        {"rows": [["Highs this week", [22, 23, 25, 26, 21, 19, 20], "°"],
                  ["Rain chance", [5, 10, 55, 20, 60, 35, 10], "%"]]})
def w_sparkline(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    for label, vals, unit in o["rows"]:
        S.text(M, S.y + S.s(14), label, S.f("bold", 21), anchor="lm")
        x0, x1 = M + S.s(230), W - M - S.s(70)
        lo, hi = min(vals), max(vals)
        h = S.s(40)
        pts = [(x0 + (x1 - x0) * i / (len(vals) - 1),
                S.y + h - (v - lo) / ((hi - lo) or 1) * (h - S.s(8)) - S.s(4))
               for i, v in enumerate(vals)]
        d.line(pts, fill=0, width=S.s(3), joint="curve")
        px, py = pts[-1]
        d.ellipse([px - S.s(5), py - S.s(5), px + S.s(5), py + S.s(5)], fill=0)
        S.text(W - M, S.y + S.s(14), f"{vals[-1]}{unit}", S.f("black", 26),
               anchor="rm")
        S.y += h + S.s(16)
    S.y -= S.s(16)


@widget("bars", "data", "Simple bar chart: one bar per label, value printed "
        "on top. Up to 8 bars.",
        {"title": "LESSONS THIS WEEK", "labels": ["M", "T", "W", "T", "F"],
         "values": [3, 4, 4, 3, 3]})
def w_bars(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    if o.get("title"):
        S.spaced(M, S.y, o["title"], S.f("mono", 18), 4)
        S.y += S.s(34)
    vals = o["values"]
    n = len(vals)
    cw = (W - 2 * M) / n
    H = S.s(130)
    base = S.y + H + S.s(26)
    for i, v in enumerate(vals):
        bh = H * v / (max(vals) or 1)
        x0, x1 = M + cw * i + cw * 0.18, M + cw * (i + 1) - cw * 0.18
        d.rectangle([x0, base - bh, x1, base], fill=0)
        S.text((x0 + x1) / 2, base - bh - S.s(4), str(v), S.f("bold", 20),
               anchor="md")
        S.text((x0 + x1) / 2, base + S.s(8), str(o["labels"][i]),
               S.f("mono", 18), anchor="ma")
    d.rectangle([M, base, W - M, base + S.s(2)], fill=0)
    S.y = base + S.s(36)


@widget("sun_arc", "data", "The day's light as an arc: sunrise, sunset, and "
        "an optional marked time. Times are 24-hour.",
        {"sunrise": "06:48", "sunset": "19:21", "mark": "14:35",
         "mark_label": "bell"})
def w_sun_arc(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    x0, x1 = M + S.s(6), W - M - S.s(6)
    X = lambda h: x0 + (x1 - x0) * h / 24
    r, s_ = _hm(o["sunrise"]), _hm(o["sunset"])
    H = S.s(120)
    base = S.y + H + S.s(40)
    mins = round((s_ - r) * 60)
    S.text(W / 2, S.y, f"{mins // 60} h {mins % 60:02d} min of daylight",
           S.f("serifi", 23), anchor="ma")
    arc = lambda h: base - math.sin(math.pi * (h - r) / (s_ - r)) * H
    pts = [(X(r + (s_ - r) * i / 80), arc(r + (s_ - r) * i / 80)) for i in range(81)]
    d.line(pts, fill=0, width=S.s(3), joint="curve")
    bh = S.s(18)
    d.rectangle([x0, base, X(r), base + bh], fill=0)
    d.rectangle([X(s_), base, x1, base + bh], fill=0)
    d.rectangle([x0, base, x1, base + bh], outline=0, width=S.s(2))
    for h in range(0, 25, 3):
        d.rectangle([X(h) - 1, base + bh, X(h), base + bh + S.s(6)], fill=0)
    for h, lab in ((6, "6a"), (12, "noon"), (18, "6p")):
        S.text(X(h), base + bh + S.s(9), lab, S.f("mono", 15), anchor="ma")
    if o.get("mark"):
        m = _hm(o["mark"])
        if r < m < s_:
            px, py = X(m), arc(m)
            rr = S.s(13)
            for k in range(8):
                a = k * math.pi / 4
                d.line([px + math.cos(a) * rr * 1.3, py + math.sin(a) * rr * 1.3,
                        px + math.cos(a) * rr * 1.9, py + math.sin(a) * rr * 1.9],
                       fill=0, width=S.s(3))
            d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=0)
            if o.get("mark_label"):
                S.text(px, py + rr * 2.2, o["mark_label"], S.f("mono", 15),
                       anchor="ma")
    S.y = base + bh + S.s(32)
    S.text(X(r), S.y, _clock(o["sunrise"]), S.f("bold", 20), anchor="la")
    S.text(X(s_), S.y, _clock(o["sunset"]), S.f("bold", 20), anchor="ra")
    S.y += S.s(26)


@widget("moon_week", "data", "The moon for each of the next 7 nights, as "
        "seen from the southern hemisphere.", {"start": "2026-03-13"})
def w_moon_week(S, o, ctx):
    W, M = S.W, S.M
    start = dt.date.fromisoformat(o["start"]) if o.get("start") else _date(o, ctx)
    n = o.get("days", 7)
    cw = (W - 2 * M) / n
    r = int(min(S.s(30), cw * 0.4))
    for i in range(n):
        day = start + dt.timedelta(days=i)
        cx = M + cw * i + cw / 2
        S.text(cx, S.y, day.strftime("%a").upper(), S.f("mono", 16), anchor="ma")
        _moon(S, cx, S.y + S.s(30) + r, r, moon_phase(day)[0])
        S.text(cx, S.y + S.s(38) + 2 * r, str(day.day), S.f("bold", 20), anchor="ma")
    S.y += S.s(66) + 2 * r
    S.text(W / 2, S.y, moon_phase(start)[1] + " tonight", S.f("serifi", 22),
           anchor="ma")
    S.y += S.s(28)


@widget("week_strip", "data", "Seven day boxes with a few words in each. "
        "marks maps a date to a short note (max 9 letters per line, use \\n).",
        {"start": "2026-03-09", "today": "2026-03-11",
         "marks": {"2026-03-10": "dentist", "2026-03-12": "The\nLanterns",
                   "2026-03-14": "markets"}})
def w_week_strip(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    start = dt.date.fromisoformat(o["start"])
    cw = (W - 2 * M) / 7
    H = S.s(132)
    for i in range(7):
        day = start + dt.timedelta(days=i)
        x = M + cw * i
        today = o.get("today") == day.isoformat()
        if today:
            d.rectangle([x, S.y, x + cw, S.y + H], fill=0)
        d.rectangle([x, S.y, x + cw, S.y + H], outline=0, width=S.s(2))
        ink = 255 if today else 0
        S.text(x + cw / 2, S.y + S.s(8), day.strftime("%a").upper(),
               S.f("mono", 16), fill=ink, anchor="ma")
        S.text(x + cw / 2, S.y + S.s(26), str(day.day), S.f("black", 34),
               fill=ink, anchor="ma")
        note = o.get("marks", {}).get(day.isoformat(), "")
        for k, line in enumerate(note.split("\n")[:2]):
            S.text(x + cw / 2, S.y + S.s(80) + k * S.s(20), line,
                   _fit(S, "sans", line, cw - S.s(8), 16, 10), fill=ink,
                   anchor="ma")
    S.y += H


@widget("month", "data", "A month calendar, Monday first. today is drawn as "
        "a black disc; marks get a dot; ring draws circles round dates.",
        {"month": "2026-12", "today": 0, "marks": [4, 11, 17], "ring": [25]})
def w_month(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    y, m = [int(v) for v in o["month"].split("-")]
    S.text(M, S.y - S.s(8), calendar.month_name[m].upper(), S.f("black", 44))
    S.text(W - M, S.y + S.s(8), str(y), S.f("mono", 26), anchor="ra")
    S.y += S.s(60)
    cw = (W - 2 * M) / 7
    d.rectangle([M, S.y, W - M, S.y + S.s(32)], fill=0)
    for i, name in enumerate("MTWTFSS"):
        S.text(M + cw * i + cw / 2, S.y + S.s(15), name, S.f("mono", 18),
               fill=255, anchor="mm")
    S.y += S.s(40)
    ch = S.s(58)
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(y, m):
        for i, day in enumerate(week):
            if not day:
                continue
            cx, cy = M + cw * i + cw / 2, S.y + ch / 2
            rr = S.s(22)
            if day == o.get("today"):
                d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=0)
                S.text(cx, cy - S.s(2), str(day), S.f("bold", 24), fill=255,
                       anchor="mm")
            else:
                if day in o.get("ring", []):
                    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=0,
                              width=S.s(3))
                S.text(cx, cy - S.s(2), str(day),
                       S.f("bold" if i < 5 else "sans", 24), anchor="mm")
            if day in o.get("marks", []):
                d.ellipse([cx - S.s(4), cy + S.s(17), cx + S.s(4), cy + S.s(25)],
                          fill=0)
        S.y += ch
        d.rectangle([M, S.y - 1, W - M, S.y], fill=0)


@widget("habit_grid", "data", "Empty tick grid: one row per habit, one "
        "column per day. For a week on the fridge.",
        {"habits": ["Water", "Walk", "Marking", "Bed by 10"],
         "start": "2026-03-16", "days": 7})
def w_habit_grid(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    n = o.get("days", 7)
    start = dt.date.fromisoformat(o["start"]) if o.get("start") else _date(o, ctx)
    lx = M + S.s(176)
    cw = (W - M - lx) / n
    for i in range(n):
        day = start + dt.timedelta(days=i)
        lab = day.strftime("%a")[0] if n <= 14 else str(day.day)
        S.text(lx + cw * i + cw / 2, S.y, lab, S.f("mono", 17), anchor="ma")
    S.y += S.s(28)
    rh = min(cw, S.s(52))
    for habit in o["habits"]:
        S.text(M, S.y + rh / 2, habit, _fit(S, "bold", habit, S.s(166), 22),
               anchor="lm")
        for i in range(n):
            x = lx + cw * i
            d.rectangle([x + S.s(3), S.y + S.s(3), x + cw - S.s(3), S.y + rh - S.s(3)],
                        outline=0, width=S.s(2))
        S.y += rh
    S.y += S.s(2)


# ═════════════════════════════ words ═══════════════════════════════════════
@widget("quote", "words", "A quotation in large italic serif with its "
        "source. Only real, attributable quotes.",
        {"text": "Nothing in biology makes sense except in the light of "
                 "evolution.", "by": "Theodosius Dobzhansky, 1973"})
def w_quote(S, o, ctx):
    W, M = S.W, S.M
    S.text(M - S.s(4), S.y - S.s(46), "“", S.f("display", 170))
    S.y += S.s(84)
    f = S.f("serifi", o.get("size", 31))
    for line in S.wrap(o["text"], f, W - 2 * M - S.s(20)):
        S.text(M + S.s(20), S.y, line, f)
        S.y += round(f.size * 1.3)
    if o.get("by"):
        S.y += S.s(10)
        S.text(W - M, S.y, "– " + o["by"], S.f("sans", 20), anchor="ra")
        S.y += S.s(28)


@widget("fact", "words", "The fun fact: a DNA helix, a small heading and a "
        "centred paragraph. art helix|none.",
        {"head": "ONE TRUE THING", "art": "helix",
         "text": "Outdoor light, even under cloud, is far brighter than a "
                 "classroom, and it is what sets your body clock. A walk at "
                 "lunch beats the ceiling lights."})
def w_fact(S, o, ctx):
    W, M = S.W, S.M
    if o.get("art", "helix") == "helix":
        N.helix(S)
        S.y += S.s(14)
    S.spaced(W / 2, S.y, o.get("head", "ONE TRUE THING"), S.f("mono", 18), 5,
             anchor="m")
    S.y += S.s(34)
    f = S.f("serif", 25)
    for line in S.wrap(o["text"], f, W - 2 * M - S.s(20)):
        S.text(W / 2, S.y, line, f, anchor="ma")
        S.y += round(f.size * 1.32)


@widget("big_note", "words", "A few words as large as will fit, for a note "
        "left on a desk or fridge. invert makes it white on black.",
        {"text": "BACK IN 10 MINUTES", "invert": False, "max_lines": 3})
def w_big_note(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    pad = S.s(22) if o.get("invert") else 0
    width = W - 2 * M - 2 * pad
    words = o["text"].split()
    for size in range(170, 26, -4):
        f = S.f("black", size)
        lines = S.wrap(o["text"], f, width)
        if len(lines) <= o.get("max_lines", 3) and \
                all(f.getlength(wd) <= width for wd in words):
            break
    lh = round(f.size * 1.0)
    top = S.y
    H = lh * len(lines) + 2 * pad + S.s(16)
    if o.get("invert"):
        d.rounded_rectangle([M, top, W - M, top + H], radius=S.s(16), fill=0)
    yy = top + pad
    for line in lines:
        S.text(W / 2, yy - f.size * 0.12, line, f,
               fill=255 if o.get("invert") else 0, anchor="ma")
        yy += lh
    S.y = top + H


@widget("lines", "words", "Blank writing space: ruled lines or a dot grid. "
        "style ruled|dots|grid (5 mm squares).", {"title": "NOTES", "count": 5, "style": "ruled"})
def w_lines(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    if o.get("title"):
        S.spaced(M, S.y, o["title"], S.f("mono", 18), 4)
        S.y += S.s(26)
    step = S.s(44)
    if o.get("style") == "grid":          # 5 mm squares
        g = 40 * S.k
        rows_ = o.get("count", 5) * 2
        cols_ = int((W - 2 * M) // g)
        x0 = (W - cols_ * g) / 2
        for r in range(rows_ + 1):
            d.rectangle([x0, S.y + r * g, x0 + cols_ * g, S.y + r * g + (1 if r % 2 else 0)], fill=0)
        for c in range(cols_ + 1):
            d.rectangle([x0 + c * g, S.y, x0 + c * g + (1 if c % 2 else 0), S.y + rows_ * g], fill=0)
        S.y += rows_ * g + S.s(4)
    elif o.get("style") == "dots":
        g = S.s(24)
        for r in range(o.get("count", 5) * 2):
            for x in range(M + g // 2, W - M, g):
                d.ellipse([x - 1, S.y + r * g, x + S.s(2), S.y + r * g + S.s(3)],
                          fill=0)
        S.y += o.get("count", 5) * 2 * g
    else:
        for _ in range(o.get("count", 5)):
            S.y += step
            d.rectangle([M, S.y, W - M, S.y + 1], fill=0)
        S.y += S.s(4)


# ═════════════════════════════ fun ═════════════════════════════════════════
@widget("maze", "fun", "A solvable maze, different for every seed. cols 10 "
        "(easy) to 26 (hard).", {"cols": 16, "rows": 16, "seed": 7,
                                 "title": "FIND THE WAY OUT"})
def w_maze(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    cols, rows = o.get("cols", 16), o.get("rows", 16)
    rnd = random.Random(o.get("seed"))
    if o.get("title"):
        S.spaced(W / 2, S.y, o["title"], S.f("mono", 19), 5, anchor="m")
        S.y += S.s(34)
    cell = (W - 2 * M) // cols
    x0 = (W - cell * cols) // 2
    y0 = S.y + S.s(22)
    right = [[True] * cols for _ in range(rows)]
    down = [[True] * cols for _ in range(rows)]
    seen = [[False] * cols for _ in range(rows)]
    stack = [(0, 0)]
    seen[0][0] = True
    while stack:
        r, c = stack[-1]
        nb = [(r + dr, c + dc) for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0))
              if 0 <= r + dr < rows and 0 <= c + dc < cols
              and not seen[r + dr][c + dc]]
        if not nb:
            stack.pop()
            continue
        nr, nc = rnd.choice(nb)
        if nr == r:
            right[r][min(c, nc)] = False
        else:
            down[min(r, nr)][c] = False
        seen[nr][nc] = True
        stack.append((nr, nc))
    w = S.s(4)
    hline = lambda r, c: d.rectangle([x0 + c * cell, y0 + r * cell - w // 2,
                                      x0 + (c + 1) * cell, y0 + r * cell + w // 2], fill=0)
    vline = lambda r, c: d.rectangle([x0 + c * cell - w // 2, y0 + r * cell,
                                      x0 + c * cell + w // 2, y0 + (r + 1) * cell], fill=0)
    for c in range(cols):
        if c != 0:
            hline(0, c)
        if c != cols - 1:
            hline(rows, c)
    for r in range(rows):
        vline(r, 0)
        vline(r, cols)
        for c in range(cols):
            if right[r][c] and c < cols - 1:
                vline(r, c + 1)
            if down[r][c] and r < rows - 1:
                hline(r + 1, c)
    def arrow(cx, ty):
        a = S.s(9)
        d.polygon([(cx - a, ty), (cx + a, ty), (cx, ty + a * 1.4)], fill=0)
    arrow(x0 + cell / 2, y0 - S.s(20))
    S.y = y0 + rows * cell + S.s(8)
    arrow(x0 + cell * cols - cell / 2, S.y)
    S.y += S.s(22)


@widget("wordsearch", "fun", "Word search from your own word list (class "
        "vocabulary, names). Letters only; size 10-16.",
        {"title": "CELL DIVISION", "size": 12, "seed": 3,
         "words": ["MEIOSIS", "MITOSIS", "GAMETE", "ZYGOTE", "ALLELE",
                   "CHROMATID", "HAPLOID", "DIPLOID"]})
def w_wordsearch(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    n = o.get("size", 12)
    rnd = random.Random(o.get("seed"))
    words = sorted({"".join(ch for ch in w.upper() if ch.isalpha())
                    for w in o["words"]}, key=len, reverse=True)
    words = [w for w in words if 0 < len(w) <= n]
    grid = [[""] * n for _ in range(n)]
    dirs = [(0, 1), (1, 0), (1, 1), (-1, 1)]
    if o.get("backwards"):
        dirs += [(0, -1), (-1, 0), (-1, -1), (1, -1)]
    placed = []
    for w in words:
        for _ in range(400):
            dr, dc = rnd.choice(dirs)
            r, c = rnd.randrange(n), rnd.randrange(n)
            er, ec = r + dr * (len(w) - 1), c + dc * (len(w) - 1)
            if not (0 <= er < n and 0 <= ec < n):
                continue
            if all(grid[r + dr * i][c + dc * i] in ("", ch) for i, ch in enumerate(w)):
                for i, ch in enumerate(w):
                    grid[r + dr * i][c + dc * i] = ch
                placed.append(w)
                break
    if o.get("title"):
        S.text(W / 2, S.y - S.s(6), o["title"], _fit(S, "black", o["title"], W - 2 * M, 40),
               anchor="ma")
        S.y += S.s(54)
    cell = (W - 2 * M) / n
    f = S.f("mono", int(cell / S.k * 0.6))
    top = S.y
    for r in range(n):
        for c in range(n):
            ch = grid[r][c] or rnd.choice("ABCDEFGHIKLMNOPRSTUWY")
            S.text(M + cell * c + cell / 2, top + cell * r + cell / 2, ch, f,
                   anchor="mm")
    d.rectangle([M, top - S.s(4), W - M, top + cell * n + S.s(4)], outline=0,
                width=S.s(3))
    S.y = top + cell * n + S.s(22)
    fw = S.f("bold", 20)
    colw = (W - 2 * M) / 3
    for i, w in enumerate(sorted(placed)):
        x = M + colw * (i % 3)
        yy = S.y + (i // 3) * S.s(30)
        d.rectangle([x, yy + S.s(4), x + S.s(14), yy + S.s(18)], outline=0, width=S.s(2))
        S.text(x + S.s(22), yy, w, _fit(S, "bold", w, colw - S.s(26), 20, 12))
    S.y += math.ceil(len(placed) / 3) * S.s(30)


@widget("art", "fun", "Generative art, new for every seed. style phyllotaxis|"
        "flow|contours|ridges|mandala (mandala is line art to colour in).",
        {"style": "phyllotaxis", "seed": 1})
def w_art(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    rnd = random.Random(o.get("seed"))
    st = o.get("style", "phyllotaxis")
    if st == "phyllotaxis":
        n = o.get("n", 760)
        R = W / 2 - M - S.s(6)
        cx, cy = W / 2, S.y + R + S.s(6)
        ga = math.pi * (3 - math.sqrt(5))
        for i in range(1, n):
            rr = R * math.sqrt(i / n)
            a = i * ga
            dot = S.s(1) + S.s(7) * (i / n) ** 1.2
            x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
            d.ellipse([x - dot, y - dot, x + dot, y + dot], fill=0)
        S.y = cy + R + S.s(10)
    elif st == "flow":
        H = S.s(o.get("height", 560))
        ph = [(rnd.uniform(0.004, 0.014), rnd.uniform(0.004, 0.014),
               rnd.uniform(0, 6.28)) for _ in range(4)]
        ang = lambda x, y: sum(math.sin(fx * x + fy * y + p) for fx, fy, p in ph) * 1.6
        for _ in range(o.get("lines", 420)):
            x, y = rnd.uniform(M, W - M), rnd.uniform(0, H)
            pts = [(x, S.y + y)]
            for _ in range(rnd.randint(20, 90)):
                a = ang(x, y)
                x += math.cos(a) * 4
                y += math.sin(a) * 4
                if not (M <= x <= W - M and 0 <= y <= H):
                    break
                pts.append((x, S.y + y))
            if len(pts) > 3:
                d.line(pts, fill=0, width=rnd.choice([1, 2, 2, 3]), joint="curve")
        S.y += H
    elif st == "contours":
        import numpy as np
        H = S.s(o.get("height", 560))
        yy, xx = np.mgrid[0:H, 0:W - 2 * M]
        f = np.zeros(xx.shape)
        for _ in range(7):
            px, py = rnd.uniform(0, xx.shape[1]), rnd.uniform(0, H)
            sg = rnd.uniform(60, 190) * S.k
            f += rnd.uniform(0.5, 1.2) * np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * sg * sg))
        q = np.floor(f / f.max() * o.get("levels", 16))
        edge = np.zeros(q.shape, bool)
        edge[:, 1:] |= q[:, 1:] != q[:, :-1]
        edge[1:, :] |= q[1:, :] != q[:-1, :]
        edge[:, :-1] |= edge[:, 1:]
        img = Image.fromarray(np.where(edge, 0, 255).astype("uint8"))
        S.img.paste(img, (M, int(S.y)))
        d.rectangle([M, S.y, W - M, S.y + H], outline=0, width=S.s(3))
        S.y += H
    elif st == "mandala":          # line art with radial symmetry, to colour in
        R = W / 2 - M - S.s(4)
        cx, cy = W / 2, S.y + R + S.s(4)
        n = rnd.choice([8, 10, 12, 16])
        lw = S.s(3)
        edges = sorted(rnd.sample(range(18, 96, 6), 5))
        radii = [S.s(14)] + [R * e / 100 for e in edges] + [R]
        for a, b in zip(radii, radii[1:]):
            d.ellipse([cx - b, cy - b, cx + b, cy + b], outline=0, width=lw)
            kind = rnd.choice(["petal", "petal", "circle", "spoke", "scallop"])
            mid = (a + b) / 2
            for k in range(n):
                t0 = 2 * math.pi * k / n
                half = math.pi / n
                if kind == "petal":
                    pts = [(cx + (a + (b - a) * math.sin(math.pi * u)) * math.cos(t0 + half * (2 * u - 1)),
                            cy + (a + (b - a) * math.sin(math.pi * u)) * math.sin(t0 + half * (2 * u - 1)))
                           for u in [i / 24 for i in range(25)]]
                    d.line(pts, fill=0, width=lw, joint="curve")
                elif kind == "circle":
                    rr = min((b - a) / 2 - lw, mid * math.sin(half) - lw)
                    if rr > 3:
                        x, y = cx + mid * math.cos(t0), cy + mid * math.sin(t0)
                        d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=0, width=lw)
                elif kind == "spoke":
                    for tt in (t0, t0 + half):
                        d.line([cx + a * math.cos(tt), cy + a * math.sin(tt),
                                cx + b * math.cos(tt), cy + b * math.sin(tt)], fill=0, width=lw)
                else:
                    pts = [(cx + (b - (b - a) * 0.8 * math.sin(math.pi * u)) * math.cos(t0 + half * (2 * u - 1)),
                            cy + (b - (b - a) * 0.8 * math.sin(math.pi * u)) * math.sin(t0 + half * (2 * u - 1)))
                           for u in [i / 24 for i in range(25)]]
                    d.line(pts, fill=0, width=lw, joint="curve")
        d.ellipse([cx - S.s(14), cy - S.s(14), cx + S.s(14), cy + S.s(14)], outline=0, width=lw)
        S.y = cy + R + S.s(10)
    else:  # ridges
        rows_ = o.get("rows", 44)
        step = S.s(11)
        top = S.y + S.s(90)
        bumps = [(rnd.uniform(0.3, 0.7), rnd.uniform(0.05, 0.16)) for _ in range(3)]
        for r in range(rows_):
            y0 = top + r * step
            ph = [(rnd.uniform(0.02, 0.09), rnd.uniform(0, 6.28), rnd.uniform(0.3, 1))
                  for _ in range(5)]
            pts = []
            for x in range(M + S.s(20), W - M - S.s(20) + 1, 3):
                t = (x - M) / (W - 2 * M)
                env = sum(math.exp(-((t - c) ** 2) / (2 * wd * wd)) for c, wd in bumps)
                nz = sum(a * math.sin(fq * x + p) for fq, p, a in ph)
                pts.append((x, y0 - env * (0.5 + 0.5 * abs(nz)) * S.s(34)))
            d.polygon(pts + [(pts[-1][0], y0 + step), (pts[0][0], y0 + step)], fill=255)
            d.line(pts, fill=0, width=S.s(2), joint="curve")
        S.y = top + rows_ * step + S.s(10)
    if o.get("caption"):
        S.spaced(W / 2, S.y + S.s(6), o["caption"], S.f("mono", 15), 4, anchor="m")
        S.y += S.s(30)


@widget("qr", "fun", "A QR code with a caption: a link, wifi details, a "
        "phone number. Needs the qrencode command.",
        {"data": "https://transportnsw.info", "caption": "Trip planner"})
def w_qr(S, o, ctx):
    W = S.W
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            path = tf.name
        subprocess.run(["qrencode", "-o", path, "-s", "1", "-m", "0", "-l", "M",
                        o["data"]], check=True, capture_output=True)
        q = Image.open(path).convert("L")
        os.unlink(path)
    except (OSError, subprocess.CalledProcessError):
        S.text(W / 2, S.y, "[QR needs the qrencode command]", S.f("sans", 20),
               anchor="ma")
        S.y += S.s(30)
        return
    scale = max(1, min(S.s(o.get("size", 300)) // q.size[0], 12))
    q = q.resize((q.size[0] * scale, q.size[1] * scale), Image.NEAREST)
    S.img.paste(q, (int(W / 2 - q.size[0] / 2), int(S.y)))
    S.y += q.size[1] + S.s(12)
    if o.get("caption"):
        S.text(W / 2, S.y, o["caption"], S.f("bold", 22), anchor="ma")
        S.y += S.s(30)


@widget("exit_ticket", "fun", "Classroom exit ticket: a question, answer "
        "lines, name line, confidence scale. Print one per student with cuts.",
        {"title": "EXIT TICKET", "class": "12PHY", "lines": 4,
         "question": "In one sentence: why does a satellite in orbit not fall "
                     "to the ground?", "scale": True})
def w_exit_ticket(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    d.rectangle([0, S.y, W, S.y + S.s(52)], fill=0)
    S.text(M, S.y + S.s(25), o.get("title", "EXIT TICKET"), S.f("black", 30),
           fill=255, anchor="lm")
    if o.get("class"):
        S.text(W - M, S.y + S.s(26), o["class"], S.f("mono", 22), fill=255,
               anchor="rm")
    S.y += S.s(70)
    f = S.f("bold", 25)
    for line in S.wrap(o["question"], f, W - 2 * M):
        S.text(M, S.y, line, f)
        S.y += round(f.size * 1.28)
    for _ in range(o.get("lines", 4)):
        S.y += S.s(46)
        d.rectangle([M, S.y, W - M, S.y + 1], fill=0)
    S.y += S.s(26)
    if o.get("scale", True):
        S.text(M, S.y + S.s(4), "How sure are you?", S.f("sans", 20))
        for i in range(5):
            cx = W - M - S.s(22) - (4 - i) * S.s(50)
            d.ellipse([cx - S.s(18), S.y - S.s(2), cx + S.s(18), S.y + S.s(34)],
                      outline=0, width=S.s(2))
            S.text(cx, S.y + S.s(15), str(i + 1), S.f("bold", 20), anchor="mm")
        S.y += S.s(52)
    S.text(M, S.y, "Name", S.f("sans", 20))
    d.rectangle([M + S.s(64), S.y + S.s(24), W - M, S.y + S.s(25)], fill=0)
    S.y += S.s(36)


@widget("coupon", "fun", "A gift coupon with a fancy border. For the kids, "
        "or a class reward.", {"kicker": "THIS COUPON IS GOOD FOR",
                               "text": "ONE SLEEP-IN", "to": "Sam",
                               "from": "The kids", "expires": "31 Dec 2026"})
def w_coupon(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    top = S.y + S.s(6)
    body = S.s(250)
    d.rectangle([M, top, W - M, top + body], outline=0, width=S.s(5))
    d.rectangle([M + S.s(10), top + S.s(10), W - M - S.s(10), top + body - S.s(10)],
                outline=0, width=S.s(2))
    rr = S.s(24)
    for cx, cy, a0 in ((M, top, 0), (W - M, top, 90),
                       (W - M, top + body, 180), (M, top + body, 270)):
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=255)
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], a0, a0 + 90, fill=0,
              width=S.s(4))
    S.spaced(W / 2, top + S.s(36), o.get("kicker", "GOOD FOR"), S.f("mono", 18), 5,
             anchor="m")
    f = _fit(S, "display", o["text"], W - 2 * M - S.s(70), 80)
    S.text(W / 2, top + S.s(72), o["text"], f, anchor="ma")
    yy = top + body - S.s(74)
    bits = []
    if o.get("to"):
        bits.append(f"To: {o['to']}")
    if o.get("from"):
        bits.append(f"From: {o['from']}")
    S.text(W / 2, yy, "    ".join(bits), S.f("serifi", 23), anchor="ma")
    if o.get("expires"):
        S.text(W / 2, yy + S.s(30), f"Valid until {o['expires']}", S.f("sans", 18),
               anchor="ma")
    S.y = top + body + S.s(10)


@widget("games", "fun", "Pen-and-paper games. kind noughts (six grids) or "
        "dots (dots-and-boxes field).", {"kind": "noughts"})
def w_games(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    if o.get("kind", "noughts") == "dots":
        g = S.s(48)
        n = (W - 2 * M) // g
        x0 = (W - n * g) / 2
        for r in range(o.get("rows", 9)):
            for c in range(n + 1):
                x, y = x0 + c * g, S.y + S.s(8) + r * g
                d.ellipse([x - S.s(4), y - S.s(4), x + S.s(4), y + S.s(4)], fill=0)
        S.y += S.s(16) + (o.get("rows", 9) - 1) * g
        return
    per = 3
    cw = (W - 2 * M) / per
    g = cw * 0.8
    for row in range(o.get("rows", 2)):
        for i in range(per):
            x0 = M + cw * i + (cw - g) / 2
            y0 = S.y + row * (g + S.s(30))
            for k in (1, 2):
                d.rectangle([x0 + g * k / 3 - 2, y0, x0 + g * k / 3 + 1, y0 + g], fill=0)
                d.rectangle([x0, y0 + g * k / 3 - 2, x0 + g, y0 + g * k / 3 + 1], fill=0)
    S.y += o.get("rows", 2) * (g + S.s(30)) - S.s(30)


@widget("raffle_ticket", "fun", "A numbered ticket: merit award, raffle, "
        "queue number. Print many with a cut between each.",
        {"title": "MERIT", "number": 17, "sub": "Ms Rivera  ·  Science"})
def w_raffle_ticket(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    top = S.y + S.s(4)
    H = S.s(170)
    d.rounded_rectangle([M, top, W - M, top + H], radius=S.s(16), outline=0,
                        width=S.s(4))
    split = W - M - S.s(190)
    for yy in range(int(top + S.s(10)), int(top + H - S.s(8)), S.s(12)):
        d.rectangle([split, yy, split + S.s(2), yy + S.s(6)], fill=0)
    f = _fit(S, "black", o.get("title", "TICKET"), split - M - S.s(40), 64)
    S.text(M + S.s(22), top + S.s(22), o.get("title", "TICKET"), f)
    if o.get("sub"):
        S.text(M + S.s(24), top + H - S.s(44), o["sub"],
               _fit(S, "sans", o["sub"], split - M - S.s(40), 19, 12))
    num = f"{int(o.get('number', 1)):03d}"
    S.spaced((split + W - M) / 2, top + S.s(20), "NO.", S.f("mono", 17), 4, anchor="m")
    S.text((split + W - M) / 2, top + S.s(42), num, S.f("display", 78), anchor="ma")
    S.y = top + H + S.s(4)


# ═════════════════════════════ classroom ═══════════════════════════════════
def _canvas(S, need):
    """Grow the drawing surface for very long widgets (banners, rulers)."""
    if need > S.img.size[1]:
        big = Image.new("L", (S.W, int(need) + 50), 255)
        big.paste(S.img, (0, 0))
        S.img = big
        S.d = ImageDraw.Draw(big)


@widget("punnett", "class", "Punnett square from two parent genotypes: 'Aa' x "
        "'Aa' (2x2) or 'AaBb' x 'AaBb' (4x4). solved false leaves it blank for "
        "students.", {"p1": "Aa", "p2": "Aa", "solved": True,
                      "title": "MONOHYBRID CROSS"})
def w_punnett(S, o, ctx):
    d, W, M = S.d, S.W, S.M

    def gametes(g):
        pairs = [g[i:i + 2] for i in range(0, len(g), 2)]
        out = [""]
        for pr in pairs:
            out = [x + a for x in out for a in pr]
        return out

    g1, g2 = gametes(o["p1"]), gametes(o["p2"])
    n = len(g1)
    if o.get("title"):
        S.spaced(W / 2, S.y, o["title"], S.f("mono", 19), 5, anchor="m")
        S.y += S.s(32)
    S.text(W / 2, S.y, f"{o['p1']}  ×  {o['p2']}", S.f("black", 40), anchor="ma")
    S.y += S.s(64)
    hd = S.s(54 if n == 2 else 44)
    cell = (W - 2 * M - hd) / n
    ch = min(cell, S.s(150))
    x0, y0 = M + hd, S.y + hd
    fg = S.f("black", 34 if n == 2 else 22)
    fc = S.f("bold", 44 if n == 2 else 22)
    counts = {}
    for i, a in enumerate(g2):
        S.text(x0 + cell * i + cell / 2, S.y + hd / 2, a, fg, anchor="mm")
    for r, b in enumerate(g1):
        S.text(M + hd / 2, y0 + ch * r + ch / 2, b, fg, anchor="mm")
        for c, a in enumerate(g2):
            kid = "".join("".join(sorted(b[k] + a[k], key=lambda ch_: (ch_.islower(), ch_)))
                          for k in range(len(a)))
            counts[kid] = counts.get(kid, 0) + 1
            if o.get("solved", True):
                S.text(x0 + cell * c + cell / 2, y0 + ch * r + ch / 2, kid, fc,
                       anchor="mm")
    for i in range(n + 1):
        d.rectangle([x0 + cell * i - 2, y0, x0 + cell * i + 1, y0 + ch * n], fill=0)
        d.rectangle([x0, y0 + ch * i - 2, x0 + cell * n, y0 + ch * i + 1], fill=0)
    S.y = y0 + ch * n + S.s(16)
    if o.get("solved", True):
        order = sorted(counts, key=lambda k: (-sum(c.isupper() for c in k), k))
        txt = "  :  ".join(f"{counts[k]} {k}" for k in order)
        f = S.f("bold", 22)
        for line in S.wrap(txt, f, W - 2 * M):
            S.text(W / 2, S.y, line, f, anchor="ma")
            S.y += S.s(30)
    else:
        S.text(M, S.y, "Genotype ratio:", S.f("sans", 21))
        d.rectangle([M + S.s(170), S.y + S.s(26), W - M, S.y + S.s(27)], fill=0)
        S.y += S.s(46)
        S.text(M, S.y, "Phenotype ratio:", S.f("sans", 21))
        d.rectangle([M + S.s(170), S.y + S.s(26), W - M, S.y + S.s(27)], fill=0)
        S.y += S.s(34)


@widget("bingo", "class", "One 5x5 bingo card from a word list (needs 24+ "
        "words). Each seed gives a different card; print a class set with cuts.",
        {"title": "CELL BINGO", "seed": 1,
         "words": ["Nucleus", "Ribosome", "Mitosis", "Meiosis", "Gamete", "Zygote",
                   "Allele", "Gene", "DNA", "RNA", "Enzyme", "Protein", "Codon",
                   "Mutation", "Haploid", "Diploid", "Centromere", "Chromatid",
                   "Spindle", "Cytoplasm", "Membrane", "Genotype", "Phenotype",
                   "Dominant", "Recessive"]})
def w_bingo(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    words = list(dict.fromkeys(o["words"]))
    if len(words) < 24:
        raise SystemExit(f"bingo needs at least 24 different words, got {len(words)}.")
    rnd = random.Random(o.get("seed"))
    pick = rnd.sample(words, 24)
    pick.insert(12, None)
    d.rectangle([M, S.y, W - M, S.y + S.s(56)], fill=0)
    t = o.get("title", "BINGO")
    S.text(W / 2, S.y + S.s(26), t, _fit(S, "black", t, W - 2 * M - S.s(20), 38),
           fill=255, anchor="mm")
    S.y += S.s(56)
    cw = (W - 2 * M) / 5
    for i, word in enumerate(pick):
        x, y = M + cw * (i % 5), S.y + cw * (i // 5)
        if word is None:
            d.rectangle([x, y, x + cw, y + cw], fill=0)
            S.text(x + cw / 2, y + cw / 2, "FREE", S.f("black", 24), fill=255,
                   anchor="mm")
            continue
        for size in range(21, 9, -1):
            f = S.f("bold", size)
            lines = S.wrap(word, f, cw - S.s(16))
            if len(lines) <= 2 and all(f.getlength(l) <= cw - S.s(16) for l in lines):
                break
        lh = round(f.size * 1.15)
        yy = y + cw / 2 - lh * (len(lines) - 1) / 2
        for l in lines:
            S.text(x + cw / 2, yy, l, f, anchor="mm")
            yy += lh
    for i in range(6):
        d.rectangle([M + cw * i - 1, S.y, M + cw * i + 1, S.y + cw * 5], fill=0)
        d.rectangle([M, S.y + cw * i - 1, W - M, S.y + cw * i + 1], fill=0)
    S.y += cw * 5 + S.s(4)


@widget("cryptogram", "class", "A sentence in a letter-substitution code to "
        "crack. hints reveals that many of its most common letters.",
        {"text": "The mitochondria is the powerhouse of the cell", "seed": 4,
         "hints": 2, "title": "CRACK THE CODE"})
def w_cryptogram(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    rnd = random.Random(o.get("seed"))
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    while True:
        sh = list(abc)
        rnd.shuffle(sh)
        if all(a != b for a, b in zip(abc, sh)):
            break
    key = dict(zip(abc, sh))
    text = o["text"].upper()
    freq = sorted(set(c for c in text if c in abc), key=lambda c: -text.count(c))
    shown = set(freq[:o.get("hints", 0)])
    if o.get("title"):
        S.spaced(W / 2, S.y, o["title"], S.f("mono", 19), 5, anchor="m")
        S.y += S.s(36)
    cw, rowh = S.s(29), S.s(78)
    per = int((W - 2 * M) // cw)
    lines, cur = [], []
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > per:
            lines.append(cur)
            cur = []
        cur += ([" "] if cur else []) + list(word)
    lines.append(cur)
    fa, fc = S.f("bold", 24), S.f("mono", 20)
    for row in lines:
        x = (W - len(row) * cw) / 2
        for ch in row:
            if ch in abc:
                if ch in shown:
                    S.text(x + cw / 2, S.y + S.s(16), ch, fa, anchor="mm")
                d.rectangle([x + S.s(3), S.y + S.s(32), x + cw - S.s(3), S.y + S.s(34)],
                            fill=0)
                S.text(x + cw / 2, S.y + S.s(52), key[ch], fc, anchor="mm")
            elif ch != " ":
                S.text(x + cw / 2, S.y + S.s(16), ch, fa, anchor="mm")
            x += cw
        S.y += rowh
    S.text(W / 2, S.y - S.s(6), "Each letter stands for a different letter.",
           S.f("serifi", 20), anchor="ma")
    S.y += S.s(26)


def _sudoku(rnd, clues):
    base = lambda r, c: (r * 3 + r // 3 + c) % 9
    def shuf(n):
        out = []
        for band in rnd.sample(range(3), 3):
            out += [band * 3 + k for k in rnd.sample(range(3), 3)]
        return out
    rows, cols, nums = shuf(9), shuf(9), rnd.sample(range(1, 10), 9)
    full = [nums[base(r, c)] for r in rows for c in cols]

    def count(g, limit=2):
        best, cand = None, None
        for i in range(81):
            if g[i]:
                continue
            r, c = divmod(i, 9)
            used = {g[r * 9 + k] for k in range(9)} | {g[k * 9 + c] for k in range(9)}
            br, bc = r - r % 3, c - c % 3
            used |= {g[(br + a) * 9 + bc + b] for a in range(3) for b in range(3)}
            opts = [v for v in range(1, 10) if v not in used]
            if not opts:
                return 0
            if cand is None or len(opts) < len(cand):
                best, cand = i, opts
                if len(opts) == 1:
                    break
        if best is None:
            return 1
        total = 0
        for v in cand:
            g[best] = v
            total += count(g, limit)
            if total >= limit:
                break
        g[best] = 0
        return total

    puzzle = full[:]
    left = 81
    for i in rnd.sample(range(81), 81):
        if left <= clues:
            break
        keep = puzzle[i]
        puzzle[i] = 0
        if count(puzzle[:]) != 1:
            puzzle[i] = keep
        else:
            left -= 1
    return puzzle, full


@widget("sudoku", "class", "A sudoku with exactly one solution. level easy|"
        "medium|hard. solution true prints a small answer grid underneath.",
        {"level": "easy", "seed": 2, "solution": True})
def w_sudoku(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    rnd = random.Random(o.get("seed"))
    clues = {"easy": 40, "medium": 33, "hard": 28}.get(o.get("level", "easy"), 40)
    puzzle, full = _sudoku(rnd, clues)
    S.spaced(M, S.y, "SUDOKU", S.f("mono", 20), 6)
    S.text(W - M, S.y, o.get("level", "easy"), S.f("serifi", 22), anchor="ra")
    S.y += S.s(36)

    def grid(x0, y0, cell, vals, font, thick):
        for i, v in enumerate(vals):
            if v:
                S.text(x0 + cell * (i % 9) + cell / 2, y0 + cell * (i // 9) + cell / 2 - 1,
                       str(v), font, anchor="mm")
        for k in range(10):
            w = thick if k % 3 == 0 else 1
            d.rectangle([x0 + cell * k - w // 2, y0, x0 + cell * k + (w - 1) // 2 + (w == 1),
                         y0 + cell * 9], fill=0)
            d.rectangle([x0, y0 + cell * k - w // 2, x0 + cell * 9,
                         y0 + cell * k + (w - 1) // 2 + (w == 1)], fill=0)

    cell = (W - 2 * M) // 9
    grid((W - cell * 9) / 2, S.y, cell, puzzle, S.f("black", 34), S.s(5))
    S.y += cell * 9 + S.s(18)
    if o.get("solution"):
        S.spaced(W / 2, S.y, "ANSWER (NO PEEKING)", S.f("mono", 14), 3, anchor="m")
        S.y += S.s(24)
        c2 = S.s(22)
        grid((W - c2 * 9) / 2, S.y, c2, full, S.f("sans", 15), S.s(3))
        S.y += c2 * 9 + S.s(6)


# ═════════════════════════════ home ════════════════════════════════════════
@widget("recipe", "home", "Recipe card: title, serves/time, ingredients in two "
        "columns, numbered method.",
        {"title": "Weeknight fried rice", "serves": "4", "time": "20 min",
         "ingredients": ["3 cups cooked rice", "2 eggs", "1 cup frozen peas",
                         "2 spring onions", "2 tbsp soy sauce", "1 tbsp oil"],
         "method": ["Scramble the eggs in a hot oiled pan, then set aside.",
                    "Fry the rice and peas for five minutes.",
                    "Return the eggs, add soy and spring onions, toss and serve."],
         "note": ""})
def w_recipe(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    S.rule(6, 10)
    f = S.f("display", 46)
    for line in S.wrap(o["title"], f, W - 2 * M):
        S.text(M, S.y - S.s(10), line, f)
        S.y += S.s(50)
    meta = "  ·  ".join(v for v in (o.get("serves") and f"SERVES {o['serves']}",
                                    o.get("time") and o["time"].upper()) if v)
    if meta:
        S.y += S.s(6)
        S.spaced(M, S.y, meta, S.f("mono", 18), 3)
        S.y += S.s(30)
    S.rule(2, 14)
    fi = S.f("sans", 22)
    colw = (W - 2 * M - S.s(16)) / 2
    ing = o.get("ingredients", [])
    for i in range(0, len(ing), 2):
        rows = 1
        for k, item in enumerate(ing[i:i + 2]):
            x = M + k * (colw + S.s(16))
            d.rectangle([x, S.y + S.s(7), x + S.s(12), S.y + S.s(19)], outline=0,
                        width=S.s(2))
            lines = S.wrap(item, fi, colw - S.s(24))
            rows = max(rows, len(lines))
            for j, l in enumerate(lines):
                S.text(x + S.s(22), S.y + j * S.s(27), l, fi)
        S.y += rows * S.s(27) + S.s(8)
    S.y += S.s(6)
    S.rule(2, 16)
    fm = S.f("serif", 23)
    for n, step in enumerate(o.get("method", []), 1):
        r = S.s(17)
        d.ellipse([M, S.y, M + 2 * r, S.y + 2 * r], fill=0)
        S.text(M + r, S.y + r - 1, str(n), S.f("bold", 21), fill=255, anchor="mm")
        y0 = S.y
        for l in S.wrap(step, fm, W - 2 * M - S.s(50)):
            S.text(M + S.s(50), S.y, l, fm)
            S.y += S.s(30)
        S.y = max(S.y, y0 + 2 * r) + S.s(12)
    if o.get("note"):
        S.para(o["note"], S.f("serifi", 21))


@widget("receipt", "home", "An itemised receipt: for a joke, an IOU, pocket "
        "money, or an agent's summary of a finished job. lines are [text, "
        "amount]; amount may be ''; ['---', ''] draws a divider.",
        {"store": "AGENT & CO", "header": ["Job receipt", "Fri 13 Mar 2026"],
         "lines": [["Files changed", "14"], ["Tests passing", "212"],
                   ["Coffee consumed", "2"], ["Regrets", "0"]],
         "total": ["BALANCE DUE", "one high five"],
         "footer": "Thank you for printing with us."})
def w_receipt(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    pad = S.s(30)
    t = o.get("store", "RECEIPT")
    S.text(W / 2, S.y, t, _fit(S, "black", t, W - 2 * M, 44), anchor="ma")
    S.y += S.s(58)
    fm = S.f("mono", 20)
    for line in o.get("header", []):
        S.text(W / 2, S.y, line, fm, anchor="ma")
        S.y += S.s(28)

    def dashes():
        S.y += S.s(8)
        for x in range(M + pad, W - M - pad, S.s(12)):
            d.rectangle([x, S.y, x + S.s(6), S.y + S.s(2)], fill=0)
        S.y += S.s(16)

    dashes()
    for text, amt in o["lines"]:
        if text == "---":                  # a divider between groups of lines
            dashes()
            continue
        aw = fm.getlength(str(amt)) + S.s(16)
        lines = S.wrap(text, fm, W - 2 * M - 2 * pad - aw)
        S.text(W - M - pad, S.y, str(amt), fm, anchor="ra")
        for l in lines:
            S.text(M + pad, S.y, l, fm)
            S.y += S.s(28)
    dashes()
    if o.get("total"):
        fb = S.f("black", 26)
        S.text(M + pad, S.y, o["total"][0], fb)
        S.text(W - M - pad, S.y, str(o["total"][1]),
               _fit(S, "black", str(o["total"][1]),
                    W - 2 * M - 2 * pad - fb.getlength(o["total"][0]) - S.s(20), 26),
               anchor="ra")
        S.y += S.s(42)
        dashes()
    if o.get("stripes", True):
        rnd = random.Random(t)
        x = M + pad + S.s(30)
        while x < W - M - pad - S.s(30):
            w = rnd.choice([2, 2, 4, 6])
            d.rectangle([x, S.y, x + S.s(w) - 1, S.y + S.s(54)], fill=0)
            x += S.s(w) + rnd.choice([2, 3, 5]) * S.k
        S.y += S.s(66)
    if o.get("footer"):
        for l in S.wrap(o["footer"], S.f("serifi", 21), W - 2 * M - 2 * pad):
            S.text(W / 2, S.y, l, S.f("serifi", 21), anchor="ma")
            S.y += S.s(28)


@widget("scorepad", "home", "Score sheet for a card or board game: a column "
        "per player (up to 6), blank rows, a total row.",
        {"title": "SCORES", "players": ["Sam", "Ana", "Tom", "Jo"],
         "rows": 8})
def w_scorepad(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    pl = o["players"]
    n = len(pl)
    if o.get("title"):
        S.text(M, S.y - S.s(6), o["title"], S.f("black", 36))
        S.y += S.s(48)
    cw = (W - 2 * M) / n
    hh = S.s(40)
    d.rectangle([M, S.y, W - M, S.y + hh], fill=0)
    for i, name in enumerate(pl):
        S.text(M + cw * i + cw / 2, S.y + hh / 2 - 1, name,
               _fit(S, "bold", name, cw - S.s(10), 22, 11), fill=255, anchor="mm")
    top = S.y
    S.y += hh
    rh = S.s(46)
    for _ in range(o.get("rows", 8)):
        S.y += rh
        d.rectangle([M, S.y, W - M, S.y + 1], fill=0)
    d.rectangle([M, S.y, W - M, S.y + S.s(4)], fill=0)
    S.y += S.s(60)
    S.spaced(M + S.s(6), S.y - S.s(54), "TOTAL", S.f("mono", 13), 2)
    for i in range(n + 1):
        d.rectangle([M + cw * i - 1, top, M + cw * i + 1, S.y], fill=0)
    d.rectangle([M, S.y - S.s(2), W - M, S.y + S.s(2)], fill=0)
    S.y += S.s(4)


# ═════════════════════════════ make ════════════════════════════════════════
@widget("label", "make", "A bold label for a box, jar, shelf or lab bottle. "
        "Print a batch with cuts between.", {"text": "GLASSWARE",
                                             "sub": "Lab 2  ·  shelf B"})
def w_label(S, o, ctx):
    d, W, M = S.d, S.W, S.M
    top = S.y + S.s(4)
    width = W - 2 * M - S.s(44)
    words = o["text"].split()
    for size in range(120, 24, -4):
        f = S.f("black", size)
        lines = S.wrap(o["text"], f, width)
        if len(lines) <= o.get("max_lines", 2) and all(f.getlength(w_) <= width for w_ in words):
            break
    yy = top + S.s(22)
    for l in lines:
        S.text(W / 2, yy - f.size * 0.14, l, f, anchor="ma")
        yy += round(f.size * 1.0)
    if o.get("sub"):
        yy += S.s(8)
        S.text(W / 2, yy, o["sub"], _fit(S, "sans", o["sub"], width, 22, 12), anchor="ma")
        yy += S.s(30)
    yy += S.s(22)
    d.rounded_rectangle([M, top, W - M, yy], radius=S.s(18), outline=0, width=S.s(6))
    S.y = yy + S.s(4)


@widget("photo", "make", "Any picture file, dithered to black dots: a photo, "
        "a kid's drawing, a diagram. rotate true turns a wide picture to run "
        "down the strip.", {"path": "~/Pictures/example.jpg", "caption": "",
                            "rotate": False, "contrast": 1.2})
def w_photo(S, o, ctx):
    from PIL import ImageEnhance, ImageOps
    W, M = S.W, S.M
    path = os.path.expanduser(o["path"])
    if not os.path.exists(path):
        raise SystemExit(f"photo: no file at {path}")
    im = ImageOps.exif_transpose(Image.open(path)).convert("L")
    if o.get("rotate") and im.size[0] > im.size[1]:
        im = im.rotate(90, expand=True)
    w = W - 2 * M
    im = im.resize((w, max(1, round(im.size[1] * w / im.size[0]))), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=1)
    im = ImageEnhance.Contrast(im).enhance(o.get("contrast", 1.2))
    im = im.convert("1").convert("L")          # Floyd-Steinberg dots
    _canvas(S, S.y + im.size[1] + 200)
    S.img.paste(im, (M, int(S.y)))
    S.y += im.size[1] + S.s(10)
    if o.get("caption"):
        S.text(W / 2, S.y, o["caption"], S.f("serifi", 22), anchor="ma")
        S.y += S.s(30)


@widget("banner", "make", "Giant letters running down the length of the "
        "paper: a birthday banner, a door sign. About 6 cm of paper per letter.",
        {"text": "HELLO"})
def w_banner(S, o, ctx):
    W = S.W
    f = S.f("black", 400)
    text = o["text"]
    tmp = Image.new("L", (10, 10), 255)
    box = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=f)
    scale = (W - S.s(60)) / (box[3] - box[1])
    f = S.f("black", int(400 * scale))
    box = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=f)
    pad = S.s(40)
    strip = Image.new("L", (box[2] - box[0] + 2 * pad, W), 255)
    ImageDraw.Draw(strip).text((pad - box[0], (W - (box[3] - box[1])) / 2 - box[1]),
                               text, font=f, fill=0)
    strip = strip.rotate(90, expand=True)
    _canvas(S, S.y + strip.size[1] + 100)
    S.img.paste(strip, (0, int(S.y)))
    S.y += strip.size[1]


@widget("ruler", "make", "A real ruler printed down the strip, in mm and cm. "
        "Any length: a 15 cm ruler or a 1.5 m height chart. Check it once "
        "against a real ruler.", {"length_mm": 100})
def w_ruler(S, o, ctx):
    W, M = S.W, S.M
    mm = o.get("length_mm", 150)
    ppm = 8 * S.k                      # 203 dpi is 8 dots per millimetre
    _canvas(S, S.y + mm * ppm + 200)
    d = S.d
    top = S.y + S.s(20)
    x0 = M + S.s(6)
    d.rectangle([x0 - S.s(4), top, x0 - 1, top + mm * ppm], fill=0)
    for i in range(mm + 1):
        y = top + i * ppm
        ln = S.s(70) if i % 10 == 0 else S.s(44) if i % 5 == 0 else S.s(26)
        d.rectangle([x0, y - (1 if i % 10 == 0 else 0), x0 + ln, y + 1], fill=0)
        if i % 10 == 0:
            S.text(x0 + S.s(84), y, str(i // 10), S.f("black", 30), anchor="lm")
    if o.get("label", True):
        S.text(W - M, top + S.s(6), "cm", S.f("serifi", 26), anchor="ra")
    S.y = top + mm * ppm + S.s(20)


@widget("paper_chain", "make", "Three patterned paper-chain links per piece: "
        "cut along the two dotted lines, loop and glue. Different seed, "
        "different patterns.", {"length_mm": 110, "seed": 1})
def w_paper_chain(S, o, ctx):
    W, M = S.W, S.M
    H = int(o.get("length_mm", 180) * 8 * S.k)
    _canvas(S, S.y + H + 100)
    d = S.d
    rnd = random.Random(o.get("seed"))
    cw = (W - 2 * M) / 3
    top = int(S.y)
    pats = rnd.sample(["dots", "bars", "zigzag", "checks", "diag", "rings"], 3)
    for i, pat in enumerate(pats):
        x0, x1 = int(M + cw * i + S.s(6)), int(M + cw * (i + 1) - S.s(6))
        if pat == "dots":
            g = S.s(30)
            for r, y in enumerate(range(top + g // 2, top + H, g)):
                for x in range(x0 + g // 2 + (g // 2 if r % 2 else 0), x1 - S.s(6), g):
                    d.ellipse([x - S.s(8), y - S.s(8), x + S.s(8), y + S.s(8)], fill=0)
        elif pat == "bars":
            for y in range(top, top + H, S.s(34)):
                d.rectangle([x0, y, x1, y + S.s(14)], fill=0)
        elif pat == "zigzag":
            for y in range(top, top + H, S.s(34)):
                pts = [(x0 + k * (x1 - x0) / 6, y + (S.s(20) if k % 2 else 0)) for k in range(7)]
                d.line(pts, fill=0, width=S.s(7), joint="curve")
        elif pat == "checks":
            g = S.s(24)
            for r, y in enumerate(range(top, top + H, g)):
                for c, x in enumerate(range(x0, x1, g)):
                    if (r + c) % 2 == 0:
                        d.rectangle([x, y, min(x + g, x1), min(y + g, top + H)], fill=0)
        elif pat == "diag":
            tile = Image.new("L", (x1 - x0, H), 255)
            td = ImageDraw.Draw(tile)
            for k in range(-H, x1 - x0 + H, S.s(30)):
                td.line([k, H, k + H, 0], fill=0, width=S.s(9))
            S.img.paste(tile, (x0, top))
        else:
            g = S.s(52)
            for y in range(top + g // 2, top + H, g):
                cx = (x0 + x1) / 2
                for rr in (S.s(22), S.s(12)):
                    d.ellipse([cx - rr, y - rr, cx + rr, y + rr], outline=0, width=S.s(5))
    for i in (1, 2):
        x = int(M + cw * i)
        d.rectangle([x - S.s(5), top, x + S.s(5), top + H], fill=255)
        for y in range(top, top + H, S.s(12)):
            d.rectangle([x, y, x + 1, y + S.s(5)], fill=0)
    S.y = top + H


# ═════════════════════════════ engine ══════════════════════════════════════
FULL_BLEED = {"poster_header", "exit_ticket"}


def render_spec(spec, width=None):
    width = width or N.CONFIG["width"]
    return _render_spec(spec, width)


def _render_spec(spec, width):
    """Returns a list of 1-bit images, one per print job (split at cuts)."""
    ctx = {"date": spec.get("date")}
    jobs, parts = [], []

    def flush():
        if not parts:
            return
        h = sum(p.size[1] for p in parts)
        strip = Image.new("L", (width, h + 12), 255)
        y = 6
        for p in parts:
            strip.paste(p, (0, y))
            y += p.size[1]
        jobs.append(strip.point(lambda v: 0 if v < 150 else 255).convert("1"))
        parts.clear()

    blob = json.dumps(spec, ensure_ascii=False)
    if "REPLACE ME" in blob:
        raise SystemExit("This spec still contains REPLACE ME placeholder text. "
                         "Write the real words before rendering.")
    for i, o in enumerate(spec["widgets"]):
        kind = o.get("type")
        if kind == "cut":
            flush()
            continue
        if kind == "spacer":
            parts.append(Image.new("L", (width, round(o.get("height", 30) * width / 576)), 255))
            continue
        if kind not in WIDGETS:
            raise SystemExit(f"widget {i + 1}: unknown type {kind!r}. "
                             f"Run widgets.py --list for the names.")
        S = Sheet(width)
        S.img = Image.new("L", (width, 5000), 255)
        S.d = ImageDraw.Draw(S.img)
        S.y = 0 if kind in FULL_BLEED else S.s(4)
        try:
            WIDGETS[kind]["fn"](S, o, ctx)
        except KeyError as exc:
            raise SystemExit(f"widget {i + 1} ({kind}): missing key {exc}. "
                             f"Compare with: widgets.py --doc")
        S.y = int(S.y) + S.s(o.get("gap", 20))
        parts.append(S.img.crop((0, 0, width, max(1, S.y))))
    flush()
    return jobs


GROUPS = ("structure", "day", "data", "words", "fun", "class", "home", "make")
NO_SAMPLE = {"photo"}


def sampler(groups=None):
    out = []
    for group in groups or GROUPS:
        out.append({"type": "big_note", "text": group.upper(), "invert": True,
                    "max_lines": 1})
        for name, w in WIDGETS.items():
            if w["group"] != group or name in NO_SAMPLE:
                continue
            out.append({"type": "text", "font": "mono", "size": 16,
                        "text": f"widget: {name}", "gap": 6})
            out.append({"type": name, **w["example"], "gap": 34})
        out.append({"type": "cut"})
    return {"date": "2026-03-13", "widgets": out}


def doc():
    lines = ["# Widget reference", "",
             "Generated by `widgets.py --doc`. Every widget is one JSON object "
             "in a spec's `widgets` list; `type` picks the widget. The example "
             "under each one is a complete, working object.", ""]
    for group in GROUPS:
        lines += [f"## {group}", ""]
        for name, w in WIDGETS.items():
            if w["group"] == group:
                lines += [f"### `{name}`", "", w["doc"], "", "```json",
                          json.dumps({"type": name, **w["example"]},
                                     ensure_ascii=False), "```", ""]
    lines += ["## special", "",
              "- `{\"type\": \"cut\"}` ends the print job here; the next widget "
              "starts a new piece of paper.",
              "- `{\"type\": \"spacer\", \"height\": 30}` adds blank space.",
              "- Any widget accepts `\"gap\": N` for the space after it.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="strip spec JSON file")
    ap.add_argument("--sampler", action="store_true", help="one of every widget")
    ap.add_argument("--groups", help="with --sampler: comma list, e.g. class,make")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--doc", action="store_true")
    ap.add_argument("--width", type=int, default=N.CONFIG["width"])
    ap.add_argument("--out")
    ap.add_argument("--preview-dir")
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    if a.list:
        for name, w in WIDGETS.items():
            print(f"{name:14} [{w['group']}] {w['doc']}")
    elif a.doc:
        print(doc())
    else:
        if a.sampler:
            spec = sampler(a.groups.split(",") if a.groups else None)
        elif a.spec:
            with open(a.spec, encoding="utf-8") as fh:
                spec = json.load(fh)
        else:
            ap.error("give --spec FILE, --sampler, --list or --doc")
        N.run(render_spec(spec, a.width), a, "strip")
