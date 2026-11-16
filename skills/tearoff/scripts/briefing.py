#!/usr/bin/env python3
"""tearoff: newspaper briefing layout, plus the shared drawing and printing kit.

  briefing.py --edition day.json --preview-dir /tmp/prev    render + slices
  briefing.py --edition day.json --print                    render and print

All content comes from the edition JSON (see examples/newspaper-*.json).
"""
import argparse
import datetime as dt
import json
import math
import os
import socket
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont

DEFAULTS = {
    "printer_host": None,        # e.g. "192.168.1.50"
    "printer_port": 9100,
    "width": 576,                # dots across: 576 for 80 mm paper, 384 for 58 mm
    "masthead": "THE DAILY BRIEFING",
    "place": "HOME", "lat": None, "lon": None,
    "schedule_cmd": None,        # optional command printing a timetable as JSON
    "fonts": {},                 # optional {"display": "/path/to/font.ttf", ...}
}


def load_config():
    """~/.config/tearoff/config.json, overridden by TEAROFF_* environment vars."""
    cfg = dict(DEFAULTS)
    path = os.path.expanduser(os.environ.get("TEAROFF_CONFIG",
                                             "~/.config/tearoff/config.json"))
    try:
        with open(path, encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except FileNotFoundError:
        pass
    host = os.environ.get("TEAROFF_PRINTER") or os.environ.get("BRIEFING_PRINTER")
    if host:
        cfg["printer_host"] = host
    if os.environ.get("TEAROFF_WIDTH"):
        cfg["width"] = int(os.environ.get("TEAROFF_WIDTH"))
    return cfg


CONFIG = load_config()
PRINTER = (CONFIG["printer_host"], int(CONFIG["printer_port"]))
NO_PRINTER = ("No printer configured. Run:  tearoff setup --printer <ip address>  "
              "(or set TEAROFF_PRINTER).")

# ───────────────────────────── drawing kit ─────────────────────────────────
# Fonts are looked up by name through fontconfig, so any system with the Noto
# families installed looks the same. Missing fonts fall back to whatever
# fontconfig offers; set "fonts" in the config to force specific files.
FONT_SPECS = {
    "display": "Noto Serif Display:black",
    "displayi": "Noto Serif Display:black:italic",
    "serif": "Noto Serif:medium",
    "serifi": "Noto Serif:medium:italic",
    "serifbi": "Noto Serif:black:italic",
    "sans": "Noto Sans:medium",
    "bold": "Noto Sans:bold",
    "black": "Noto Sans:black",
    "mono": "Noto Sans Mono:bold",
}
_FONT_FILES = {}


def font_file(name):
    if name not in _FONT_FILES:
        path = CONFIG["fonts"].get(name)
        if not path:
            try:
                path = subprocess.run(["fc-match", "-f", "%{file}", FONT_SPECS[name]],
                                      capture_output=True, text=True, timeout=10,
                                      check=True).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                path = None
        if not path or not os.path.exists(path):
            raise SystemExit(
                f"No font found for '{name}' ({FONT_SPECS[name]}). Install the Noto "
                "fonts (noto-fonts / fonts-noto), or set \"fonts\" in "
                "~/.config/tearoff/config.json to point at .ttf files.")
        _FONT_FILES[name] = path
    return _FONT_FILES[name]


class Sheet:
    def __init__(self, width):
        self.W = width
        self.k = width / 576
        self.img = Image.new("L", (width, 6000), 255)
        self.d = ImageDraw.Draw(self.img)
        self.y = 0
        self.M = self.s(14)
        self._fc = {}

    def s(self, n):
        return max(1, round(n * self.k))

    def f(self, name, size):
        key = (name, size)
        if key not in self._fc:
            self._fc[key] = ImageFont.truetype(font_file(name), self.s(size))
        return self._fc[key]

    def text(self, x, y, t, font, fill=0, anchor="la"):
        self.d.text((x, y), t, font=font, fill=fill, anchor=anchor)

    def spaced(self, x, y, t, font, track=3, fill=0, anchor="l"):
        """Letter-spaced caps. anchor l / m / r (top aligned)."""
        tr = self.s(track)
        w = sum(font.getlength(c) + tr for c in t) - tr
        cx = x if anchor == "l" else x - w / 2 if anchor == "m" else x - w
        for c in t:
            self.d.text((cx, y), c, font=font, fill=fill)
            cx += font.getlength(c) + tr
        return w

    def wrap(self, t, font, width):
        lines, cur = [], ""
        for word in t.split():
            trial = (cur + " " + word).strip()
            if font.getlength(trial) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def para(self, t, font, x=None, width=None, lead=1.28, fill=0):
        x = self.M if x is None else x
        width = self.W - x - self.M if width is None else width
        lh = round(font.size * lead)
        for line in self.wrap(t, font, width):
            self.text(x, self.y, line, font, fill)
            self.y += lh

    def rule(self, weight=2, gap=0, x0=None, x1=None):
        x0 = self.M if x0 is None else x0
        x1 = self.W - self.M if x1 is None else x1
        w = self.s(weight)
        self.d.rectangle([x0, self.y, x1, self.y + w - 1], fill=0)
        self.y += w + self.s(gap)

    def section(self, label):
        self.y += self.s(26)
        f = self.f("mono", 19)
        h = self.s(32)
        w = sum(f.getlength(c) + self.s(4) for c in label) + self.s(20)
        self.d.rectangle([self.M, self.y, self.M + w, self.y + h], fill=0)
        self.spaced(self.M + self.s(12), self.y + self.s(3), label, f,
                    track=4, fill=255)
        mid = self.y + h // 2
        self.d.rectangle([self.M + w + self.s(8), mid - 1, self.W - self.M,
                          mid + self.s(1)], fill=0)
        self.y += h + self.s(16)

    def stipple(self, box, step=2):
        x0, y0, x1, y1 = [int(v) for v in box]
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if ((xx // step) + (yy // step)) % 2 == 0:
                    self.img.putpixel((xx, yy), 0)

    def hatch(self, box, gap=7, weight=2):
        x0, y0, x1, y1 = [int(v) for v in box]
        g = self.s(gap)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if (xx + yy) % g < weight:
                    self.img.putpixel((xx, yy), 0)

    def finish(self):
        img = self.img.crop((0, 0, self.W, self.y))
        return img.point(lambda p: 0 if p < 150 else 255).convert("1")


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def moon_phase(date):
    ref = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
    now = dt.datetime(date.year, date.month, date.day, 9, 0,
                      tzinfo=dt.timezone.utc)  # ~8 pm Sydney
    p = ((now - ref).total_seconds() / 86400 / 29.530588853) % 1
    names = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous",
             "Full moon", "Waning gibbous", "Last quarter", "Waning crescent"]
    return p, names[int((p * 8) + 0.5) % 8], (1 - math.cos(2 * math.pi * p)) / 2


# ───────────────────────────── sections ────────────────────────────────────
def masthead(S, E):
    d, W, M = S.d, S.W, S.M
    date = E["date"]
    S.y = S.s(10)
    S.rule(6, 3)
    S.rule(2, 10)
    f = S.f("mono", 17)
    S.spaced(M, S.y, f"NO. {E['issue']:03d}", f, 3)
    S.spaced(W / 2, S.y, E.get("masthead", CONFIG["masthead"]), f, 5,
             anchor="m")
    S.spaced(W - M, S.y, E.get("week", ""), f, 3, anchor="r")
    S.y += S.s(30)
    S.rule(2, 2)

    day = date.strftime("%A")
    size = 128
    while S.f("display", size).getlength(day) > W - 2 * M:
        size -= 2
    fd = S.f("display", size)
    top = S.y
    S.text(W / 2, top - S.s(size * 0.14), day, fd, anchor="ma")
    S.y = top + S.s(size * 1.12)

    S.rule(2, 8)
    f = S.f("mono", 21)
    S.spaced(W / 2, S.y, date.strftime("%-d %B %Y").upper(), f, 6, anchor="m")
    S.y += S.s(36)
    S.rule(2, 3)
    S.rule(6, 0)


def headline(S, E):
    S.y += S.s(26)
    size = 66
    while max(S.f("displayi", size).getlength(l) for l in E["headline"]) \
            > S.W - 2 * S.M:
        size -= 2
    f = S.f("displayi", size)
    for line in E["headline"]:
        S.text(S.M, S.y - S.s(size * 0.2), line, f)
        S.y += S.s(size * 1.02)
    S.y += S.s(14)
    S.para(E["deck"], S.f("serif", 25), lead=1.32)


def weather(S, E):
    w = E["weather"]
    d, W, M = S.d, S.W, S.M
    S.section(f"SKY OVER {w['place']}")

    # big numbers + moon
    top = S.y
    fb, fs = S.f("display", 84), S.f("mono", 17)
    hi = f"{w['hi']}°"
    S.text(M, top - S.s(18), hi, fb)
    xw = M + fb.getlength(hi) + S.s(12)
    S.spaced(xw, top + S.s(6), "HIGH", fs, 3)
    S.text(xw, top + S.s(30), f"low {w['lo']}°", S.f("bold", 26))
    S.text(xw, top + S.s(62), f"UV {w['uv']}  {w.get('uv_word', '')}", S.f("sans", 21))

    p, pname, lit = moon_phase(E["date"])
    r = S.s(38)
    cx, cy = W - M - r - S.s(2), top + r + S.s(4)
    c = math.cos(2 * math.pi * p)
    for yy in range(-r, r + 1):
        hw = math.sqrt(r * r - yy * yy)
        for xx in range(-r, r + 1):
            if abs(xx) > hw:
                continue
            bright = (xx > hw * c) if p < 0.5 else (xx < -hw * c)
            if not bright:
                S.img.putpixel((cx - xx, cy + yy), 0)  # mirrored: southern sky
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=S.s(3))
    xr = cx - r - S.s(14)
    S.spaced(xr, top + S.s(6), "MOON", fs, 3, anchor="r")
    S.text(xr, top + S.s(30), pname, S.f("bold", 22), anchor="ra")
    S.text(xr, top + S.s(60), f"{round(lit * 100)}% lit", S.f("sans", 21),
           anchor="ra")
    S.y = top + S.s(108)

    # chart
    x0, x1 = M + S.s(8), W - M - S.s(8)
    ch = S.s(170)
    y0, y1 = S.y + S.s(34), S.y + S.s(34) + ch
    hrs, n = w["hours"], len(w["hours"])
    X = lambda i: x0 + (x1 - x0) * i / (n - 1)
    tmin, tmax = min(w["temp"]) - 2, max(w["temp"]) + 1
    Y = lambda t: y1 - (t - tmin) / (tmax - tmin) * (ch - S.s(52)) - S.s(48)
    bw = (x1 - x0) / (n - 1)
    for i, r_ in enumerate(w["rain"]):
        if r_ > 0:
            bh = r_ / 100 * S.s(88)
            S.stipple([X(i) - bw * 0.36, y1 - bh, X(i) + bw * 0.36, y1])
    pk = max(range(n), key=lambda i: w["rain"][i])
    if w["rain"][pk] >= 20:          # a 2% "peak" is not worth a label
        S.text(X(pk), y1 - w["rain"][pk] / 100 * S.s(88) - S.s(4),
               f"{w['rain'][pk]}% rain", S.f("mono", 15), anchor="md")
    pts = [(X(i), Y(t)) for i, t in enumerate(w["temp"])]
    # white halo then line, so the curve reads over the rain bars
    d.line(pts, fill=255, width=S.s(11), joint="curve")
    d.line(pts, fill=0, width=S.s(5), joint="curve")
    ft = S.f("bold", 21)
    imax = max(range(n), key=lambda i: w["temp"][i])
    marks = {1, imax, n - 1} | {hrs.index(h) for h in w.get("mark_hours", [])
                              if h in hrs}
    for i in sorted(marks):
        px, py = pts[i]
        rr = S.s(7)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=255, outline=0,
                  width=S.s(3))
        anc = "ld" if i == 1 else "rd" if i == n - 1 else "md"
        S.text(px, py - S.s(11), f"{round(w['temp'][i])}°", ft, anchor=anc)
    d.rectangle([x0, y1, x1, y1 + S.s(2)], fill=0)
    fa = S.f("mono", 16)
    for i, h in enumerate(hrs):
        tall = h % 3 == 0
        d.rectangle([X(i) - 1, y1, X(i), y1 + S.s(8 if tall else 4)], fill=0)
        if tall:
            lab = "12p" if h == 12 else f"{h}a" if h < 12 else f"{h - 12}p"
            S.text(X(i), y1 + S.s(11), lab, fa, anchor="ma")
    # what the day does under that sky
    by = y1 + S.s(40)
    Xh = lambda hh: x0 + (x1 - x0) * (hh - hrs[0]) / (hrs[-1] - hrs[0])
    for a, b, lab, solid in w.get("bands", []):
        box = [Xh(a), by, Xh(b), by + S.s(26)]
        if solid:
            d.rectangle(box, fill=0)
        else:
            d.rectangle(box, outline=0, width=S.s(2))
        S.spaced((box[0] + box[2]) / 2, by + S.s(2), lab, S.f("mono", 16), 4,
                 fill=255 if solid else 0, anchor="m")
    S.y = by + S.s(42)
    S.text(M, S.y, f"Sun up {w['sunrise']} am", S.f("sans", 20))
    S.text(W - M, S.y, f"down {w['sunset']} pm", S.f("sans", 20), anchor="ra")
    S.y += S.s(38)
    for note in w.get("notes", []):
        S.para(note, S.f("serif", 23))
        S.y += S.s(8)


def day(S, E):
    d, W, M = S.d, S.W, S.M
    S.section(E.get("day_title", "THE SCHOOL DAY"))
    a, b = mins(E["day_span"][0]), mins(E["day_span"][1])
    pph = S.s(102)
    top = S.y + S.s(6)
    Y = lambda m: top + (m - a) / 60 * pph
    ax = M + S.s(86)
    bx0, bx1 = ax + S.s(16), W - M
    d.rectangle([ax - 1, top, ax + S.s(1), Y(b)], fill=0)
    fm = S.f("mono", 19)
    stamps = set()
    for st, en, kind, title, detail in E["day"]:
        ya, yb = Y(mins(st)), Y(mins(en))
        box = [bx0, ya + S.s(2), bx1, yb - S.s(2)]
        short = (yb - ya) < S.s(64)
        if kind == "class":
            d.rounded_rectangle(box, radius=S.s(8), fill=0)
            S.text(bx0 + S.s(16), (ya + yb) / 2 - S.s(14), title,
                   S.f("black", 40), fill=255, anchor="lm")
            S.text(bx0 + S.s(18), (ya + yb) / 2 + S.s(24), detail,
                   S.f("bold", 21), fill=255, anchor="lm")
        elif kind == "duty":
            S.hatch(box)
            d.rectangle(box, outline=0, width=S.s(2))
            ft = S.f("bold", 19)
            tw = ft.getlength(title)
            d.rectangle([bx0 + S.s(12), box[1] + S.s(2),
                         bx0 + S.s(28) + tw, box[3] - S.s(2)], fill=255)
            S.text(bx0 + S.s(20), (ya + yb) / 2, title, ft, anchor="lm")
        elif kind == "meet":
            d.rectangle(box, outline=0, width=S.s(2))
            S.text(bx0 + S.s(16), (ya + yb) / 2 - S.s(1), title,
                   S.f("bold", 19), anchor="lm")
        else:  # free: dotted outline, quiet type
            for xx in range(int(bx0), int(bx1), S.s(8)):
                d.rectangle([xx, box[1], xx + S.s(3), box[1] + 1], fill=0)
                d.rectangle([xx, box[3] - 1, xx + S.s(3), box[3]], fill=0)
            for yy in range(int(box[1]), int(box[3]), S.s(8)):
                d.rectangle([bx0, yy, bx0 + 1, yy + S.s(3)], fill=0)
                d.rectangle([bx1 - 1, yy, bx1, yy + S.s(3)], fill=0)
            label = f"{title}  ·  {detail}" if short and detail else title
            S.text(bx0 + S.s(16), (ya + yb) / 2 - (0 if short else S.s(13)),
                   label, S.f("serifi", 22 if short else 26), anchor="lm")
            if not short:
                S.text(bx0 + S.s(16), (ya + yb) / 2 + S.s(17), detail,
                       S.f("sans", 20), anchor="lm")
        for t in (st, en):
            if t not in stamps:
                stamps.add(t)
                yy = Y(mins(t))
                d.rectangle([ax - S.s(7), yy - 1, ax + S.s(7), yy + S.s(1)],
                            fill=0)
                S.text(ax - S.s(13), yy, t, fm, anchor="rm")
    S.y = Y(b) + S.s(8)
    for note in E.get("day_notes", []):
        S.para(note, S.f("sans", 20), lead=1.3)
        S.y += S.s(8)


def ticket(S, E):
    t = E["ticket"]
    d, W, M = S.d, S.W, S.M
    if E.get("gap"):
        # the gap between bell and gates
        S.y += S.s(10)
        cx = W / 2
        for i in range(3):
            yy = S.y + i * S.s(12)
            d.ellipse([cx - S.s(3), yy, cx + S.s(3), yy + S.s(6)], fill=0)
        S.y += S.s(40)
        S.text(cx, S.y, E.get("gap", ""), S.f("serifi", 24), anchor="ma")
        S.y += S.s(38)
        for i in range(3):
            yy = S.y + i * S.s(12)
            d.ellipse([cx - S.s(3), yy, cx + S.s(3), yy + S.s(6)], fill=0)
        S.y += S.s(46)

    else:
        S.y += S.s(10)
        cx = W / 2
    top = S.y
    stub = S.s(64)
    H = S.s(372)
    x0, x1 = M, W - M
    d.rounded_rectangle([x0, top, x1, top + H], radius=S.s(18), outline=0,
                        width=S.s(4))
    # black marquee band
    band = S.s(54)
    d.rounded_rectangle([x0, top, x1, top + band + S.s(18)], radius=S.s(18),
                        fill=0)
    d.rectangle([x0 + S.s(4), top + band, x1 - S.s(4), top + band + S.s(20)],
                fill=255)
    d.rectangle([x0, top + band, x0 + S.s(3), top + band + S.s(20)], fill=0)
    d.rectangle([x1 - S.s(3), top + band, x1, top + band + S.s(20)], fill=0)
    S.spaced((x0 + x1) / 2, top + S.s(13), t["kicker"], S.f("mono", 21), 5,
             fill=255, anchor="m")
    # perforation + stub
    px = x1 - stub
    for yy in range(int(top + band + S.s(10)), int(top + H - S.s(8)), S.s(12)):
        d.rectangle([px, yy, px + S.s(2), yy + S.s(6)], fill=0)
    nr = S.s(13)
    for ny in (top, top + H):
        d.ellipse([px - nr, ny - nr, px + nr, ny + nr], fill=255)
    d.arc([px - nr, top + H - nr, px + nr, top + H + nr], 180, 360, fill=0,
          width=S.s(4))
    d.arc([px - nr, top - nr, px + nr, top + nr], 0, 180, fill=255,
          width=S.s(4))
    d.rectangle([px - nr - S.s(2), top - nr - 2, px + nr + S.s(2), top - 1],
                fill=255)
    fs = S.f("mono", 22)
    label = t["stub"]
    tmp = Image.new("L", (H - band - S.s(30), stub - S.s(14)), 255)
    td = ImageDraw.Draw(tmp)
    tw = sum(fs.getlength(c) + S.s(6) for c in label)
    cx_ = (tmp.width - tw) / 2
    for ch in label:
        td.text((cx_, (tmp.height - fs.size) / 2 - S.s(4)), ch, font=fs, fill=0)
        cx_ += fs.getlength(ch) + S.s(6)
    S.img.paste(tmp.rotate(90, expand=True),
                (int(px + S.s(6)), int(top + band + S.s(8))))

    # body
    bx, bw = x0 + S.s(22), px - x0 - S.s(40)
    yy = top + band + S.s(16)
    size = 60
    words = t["act"].split()
    while max(S.f("display", size).getlength(wd) for wd in words) > bw:
        size -= 2
    fa = S.f("display", size)
    for wd in words:
        S.text(bx, yy - S.s(size * 0.2), wd, fa)
        yy += S.s(size * 0.98)
    yy += S.s(8)
    S.spaced(bx, yy, t["tour"], S.f("mono", 20), 4)
    yy += S.s(32)
    S.text(bx, yy, t["venue"], S.f("sans", 20))
    yy += S.s(36)
    d.rectangle([bx, yy, bx + bw, yy + S.s(2)], fill=0)
    yy += S.s(10)
    fl, fv = S.f("mono", 15), S.f("black", 30)
    widths = [max(fv.getlength(v), fl.getlength(k) + 3 * len(k))
              for k, v in t["cells"]]
    gap = (bw - sum(widths)) / (len(widths) - 1)
    cxp = bx
    for (k, v), cw in zip(t["cells"], widths):
        S.spaced(cxp, yy, k, fl, 3)
        S.text(cxp, yy + S.s(18), v, fv)
        cxp += cw + gap
    S.y = top + H + S.s(12)
    S.text(W / 2, S.y, t["foot"], S.f("sans", 18), anchor="ma")
    S.y += S.s(26)


def todos(S, E):
    d, W, M = S.d, S.W, S.M
    S.section("TO DO")
    f = S.f("sans", 23)
    lh = round(f.size * 1.28)
    bs = S.s(24)
    tx = M + bs + S.s(14)
    for group, items in E["todo"]:
        S.spaced(M, S.y, group, S.f("mono", 17), 4)
        S.y += S.s(30)
        for item in items:
            d.rectangle([M, S.y + S.s(4), M + bs, S.y + S.s(4) + bs],
                        outline=0, width=S.s(3))
            for line in S.wrap(item, f, W - M - tx):
                S.text(tx, S.y, line, f)
                S.y += lh
            S.y += S.s(10)
        S.y += S.s(8)
    S.spaced(M, S.y, "YOURS", S.f("mono", 17), 4)
    S.y += S.s(34)
    for _ in range(E.get("blank_todos", 3)):
        d.rectangle([M, S.y, M + bs, S.y + bs], outline=0, width=S.s(3))
        for xx in range(int(tx), W - M, S.s(8)):
            d.rectangle([xx, S.y + bs - 1, xx + S.s(3), S.y + bs], fill=0)
        S.y += bs + S.s(22)


def tomorrow(S, E):
    t = E["tomorrow"]
    d, W, M = S.d, S.W, S.M
    S.section(f"THEN {t['title']}")
    fm, fb, fs = S.f("mono", 21), S.f("bold", 24), S.f("sans", 21)
    for tm, what, where in t["rows"]:
        S.text(M, S.y + S.s(2), tm, fm)
        xw = M + S.s(86)
        S.text(xw, S.y, what, fb)
        S.text(W - M, S.y + S.s(2), where, fs, anchor="ra")
        xa = xw + fb.getlength(what) + S.s(10)
        xb = W - M - fs.getlength(where) - S.s(10)
        for xx in range(int(xa), int(xb), S.s(8)):
            d.rectangle([xx, S.y + S.s(22), xx + S.s(2), S.y + S.s(24)],
                        fill=0)
        S.y += S.s(38)
    S.y += S.s(2)
    S.text(M, S.y, t["note"], S.f("serifi", 22))
    S.y += S.s(34)


def helix(S, height=84, turns=3.5):
    d, W = S.d, S.W
    h = S.s(height)
    cy, A = S.y + h / 2, h / 2 - S.s(8)
    x0, x1 = S.M, W - S.M
    T = lambda x: (x - x0) / (x1 - x0) * turns * 2 * math.pi
    def strand(sign, want_front):
        prev = None
        for x in range(int(x0), int(x1) + 1):
            t = T(x)
            pt = (x, cy + sign * A * math.sin(t))
            if prev and (want_front is None or (sign * math.cos(t) > 0)):
                if want_front:
                    d.line([prev, pt], fill=255, width=S.s(15))
                else:
                    d.line([prev, pt], fill=0, width=S.s(3))
            prev = pt
    def strand_ink(sign):
        prev = None
        for x in range(int(x0), int(x1) + 1):
            t = T(x)
            pt = (x, cy + sign * A * math.sin(t))
            if prev and sign * math.cos(t) > 0:
                d.line([prev, pt], fill=0, width=S.s(8))
            prev = pt
    for sign in (1, -1):
        strand(sign, None)
    for x in range(int(x0), int(x1), S.s(13)):       # base pairs
        s_ = math.sin(T(x))
        if abs(s_) > 0.18:
            d.rectangle([x, cy - A * abs(s_) + S.s(4), x + S.s(2),
                         cy + A * abs(s_) - S.s(4)], fill=0)
    for sign in (1, -1):
        strand(sign, True)
    for sign in (1, -1):
        strand_ink(sign)
    S.y += h


def closing(S, E):
    d, W, M = S.d, S.W, S.M
    S.y += S.s(30)
    S.rule(2, 14)
    n = len(E["numbers"])
    cw = (W - 2 * M) / n
    for i, (num, lab) in enumerate(E["numbers"]):
        cx = M + cw * i + cw / 2
        S.text(cx, S.y - S.s(8), num, S.f("display", 46), anchor="ma")
        f = S.f("sans", 17)
        S.text(cx, S.y + S.s(52), lab, f, anchor="ma")
        if i:
            d.rectangle([M + cw * i, S.y, M + cw * i + 1, S.y + S.s(72)],
                        fill=0)
    S.y += S.s(84)
    S.rule(2, 22)

    helix(S)
    S.y += S.s(14)
    S.spaced(W / 2, S.y, E["fact_head"], S.f("mono", 18), 5, anchor="m")
    S.y += S.s(34)
    f = S.f("serif", 25)
    for line in S.wrap(E["fact"], f, W - 2 * M - S.s(20)):
        S.text(W / 2, S.y, line, f, anchor="ma")
        S.y += round(f.size * 1.32)

    S.y += S.s(26)
    S.text(W / 2, S.y, E["signoff"], S.f("serifbi", 36), anchor="ma")
    S.y += S.s(64)
    S.rule(2, 3)
    S.rule(6, 10)
    stamp = E["date"].strftime("PRINTED FOR %a %-d %b").upper()
    S.spaced(W / 2, S.y, stamp + "  ·  SET BY CLAUDE", S.f("mono", 15), 3,
             anchor="m")
    S.y += S.s(30)


def load_edition(path):
    with open(path, encoding="utf-8") as fh:
        E = json.load(fh)
    E["date"] = dt.date.fromisoformat(E["date"])
    return E


def render(width, E):
    S = Sheet(width)
    masthead(S, E)
    headline(S, E)
    weather(S, E)
    day(S, E)
    if "ticket" in E:
        ticket(S, E)
    todos(S, E)
    if "tomorrow" in E:
        tomorrow(S, E)
    closing(S, E)
    return S.finish()


# ───────────────────────────── printer ─────────────────────────────────────
# ESC/POS commands, written as byte lists so they read as what they are.
ESC_INIT = bytes([0x1B, 0x40])            # ESC @   reset
GS_RASTER = bytes([0x1D, 0x76, 0x30, 0])  # GS v 0  print raster image
ESC_FEED = bytes([0x1B, 0x64])            # ESC d n feed n lines
GS_CUT = bytes([0x1D, 0x56, 0x42, 0])     # GS V B  feed and partial cut
DLE_EOT = bytes([0x10, 0x04])             # DLE EOT n  real-time status


def send(img, feed=5, cut=True):
    """Send a 1-bit image as ESC/POS raster, then feed and cut."""
    w, h = img.size
    assert w % 8 == 0
    raw = img.point(lambda p: 255 - p).tobytes()  # 1 = black dot
    rowbytes = w // 8
    out = bytearray(ESC_INIT)
    band = 96
    for y in range(0, h, band):
        rows = min(band, h - y)
        out += GS_RASTER + bytes([rowbytes % 256, rowbytes // 256,
                                      rows % 256, rows // 256])
        out += raw[y * rowbytes:(y + rows) * rowbytes]
    out += ESC_FEED + bytes([feed])
    if cut:
        out += GS_CUT
    # The printer takes data only as fast as it prints, so allow a long stall
    # per chunk, and report exactly how far we got if it stops answering.
    if not PRINTER[0]:
        raise SystemExit("NOT PRINTED. " + NO_PRINTER)
    sent = 0
    try:
        with socket.create_connection(PRINTER, timeout=10) as s:
            s.settimeout(90)
            for i in range(0, len(out), 4096):
                s.sendall(bytes(out[i:i + 4096]))
                sent = i + 4096
    except OSError as exc:
        pct = min(100, round(sent / len(out) * 100))
        raise SystemExit(
            f"PRINT FAILED: the printer stopped responding after about {pct}% "
            f"of the job ({exc}). Part of the strip may have printed. Do NOT "
            "resend. Tell the user, and ask them to check the printer (power, paper, "
            f"network) at {PRINTER[0]}.")
    return len(out)


def status():
    """Ask the printer how it is. Returns a one-line human summary."""
    if not PRINTER[0]:
        return "PRINTER UNREACHABLE: " + NO_PRINTER
    try:
        with socket.create_connection(PRINTER, timeout=5) as s:
            s.settimeout(5)
            got = {}
            for name, n in (("printer", 1), ("error", 3), ("paper", 4)):
                s.sendall(DLE_EOT + bytes([n]))
                got[name] = s.recv(8)[-1]
    except OSError as exc:
        return f"PRINTER UNREACHABLE at {PRINTER[0]}:9100 ({exc})"
    notes = []
    notes.append("OFFLINE" if got["printer"] & 0x08 else "online")
    notes.append("ERROR FLAGGED" if got["error"] & 0x6C else "no error")
    if got["paper"] & 0x60:
        notes.append("PAPER OUT")
    elif got["paper"] & 0x0C:
        notes.append("paper low")
    else:
        notes.append("paper ok")
    return "printer status: " + ", ".join(notes)


def save_slices(img, folder, stem, max_h=1000):
    """Save the strip as numbered PNG slices short enough to look at."""
    os.makedirs(folder, exist_ok=True)
    paths = []
    g = img.convert("L")
    for i, y in enumerate(range(0, g.size[1], max_h)):
        path = os.path.join(folder, f"{stem}-{i + 1:02d}.png")
        g.crop((0, y, g.size[0], min(g.size[1], y + max_h))).save(path)
        paths.append(path)
    return paths


def run(jobs, a, stem):
    """Shared CLI tail: report, save, preview, print a list of images."""
    for i, im in enumerate(jobs):
        tag = stem if i == 0 else f"{stem}-part{i + 1}"
        print(f"{tag}: {im.size[0]}x{im.size[1]} px "
              f"(~{im.size[1] / 8:.0f} mm of paper)")
        if a.out:
            im.save(a.out if i == 0 else a.out.replace(".png", f"-part{i + 1}.png"))
        if a.preview_dir:
            for path in save_slices(im, a.preview_dir, tag):
                print("preview", path)
    if a.print:
        first = status()
        if "UNREACHABLE" in first or "OFFLINE" in first or "PAPER OUT" in first:
            raise SystemExit(f"NOT PRINTED. {first}. Nothing was sent. Tell "
                             "the user; do not retry in a loop.")
        for im in jobs:
            print("sent", send(im), "bytes")
        time.sleep(8 + sum(im.size[1] for im in jobs) / 400)
        print(status())


def cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", required=True, help="edition JSON file")
    ap.add_argument("--width", type=int, default=CONFIG["width"],
                    help="dots across (default from config; 576 = 80 mm paper)")
    ap.add_argument("--out", help="save the full strip as one PNG")
    ap.add_argument("--preview-dir", help="save PNG slices here to inspect")
    ap.add_argument("--print", action="store_true", help="send to printer")
    return ap


if __name__ == "__main__":
    a = cli().parse_args()
    run([render(a.width, load_edition(a.edition))], a, "newspaper")
