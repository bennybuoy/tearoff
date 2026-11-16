#!/usr/bin/env python3
"""Thermal briefing, layout 2: the day as a gig poster.

  briefing_gig.py --edition day.json --preview-dir /tmp/prev
  briefing_gig.py --edition day.json --print [--split]

--split prints the pocket card as its own job so the cutter separates it.
All content comes from the edition JSON (see examples/gig-*.json).
"""
import argparse
import math

from PIL import Image, ImageDraw

from briefing import Sheet, cli, load_edition, moon_phase, run

E = {}   # filled from the edition JSON in main


# ───────────────────────────── pieces ──────────────────────────────────────
def bar(S, label):
    """Full-bleed black bar with centred letter-spaced caps."""
    S.y += S.s(30)
    h = S.s(44)
    S.d.rectangle([0, S.y, S.W, S.y + h], fill=0)
    S.spaced(S.W / 2, S.y + S.s(8), label, S.f("mono", 21), 5, fill=255,
             anchor="m")
    S.y += h + S.s(18)


def header(S):
    d, W = S.d, S.W
    H = S.s(430)
    d.rectangle([0, 0, W, H], fill=0)
    # halftone sunburst: dots grow with distance from the centre
    cx, cy = W / 2, H * 0.50
    cell = S.s(7)
    rmax = math.hypot(W / 2, H / 2)
    for gy in range(0, H, cell):
        for gx in range(0, W, cell):
            px, py = gx + cell / 2 + (cell / 2 if (gy // cell) % 2 else 0), gy + cell / 2
            ang = math.atan2(py - cy, px - cx)
            if int((ang + math.pi) / (2 * math.pi) * 28) % 2:
                continue
            r = math.hypot(px - cx, py - cy) / rmax
            rad = cell * 0.62 * min(1, 0.25 + r * 1.1)
            d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=255)
    # top + bottom strips
    d.rectangle([0, 0, W, S.s(50)], fill=0)
    S.spaced(W / 2, S.s(12), E["top"], S.f("mono", 22), 9, fill=255,
             anchor="m")
    d.rectangle([0, H - S.s(46), W, H], fill=0)
    S.spaced(W / 2, H - S.s(36), E["strip"], S.f("mono", 16), 1, fill=255,
             anchor="m")
    # title
    size = 150
    while S.f("black", size).getlength(E["title"]) > W - S.s(64):
        size -= 2
    f = S.f("black", size)
    d.text((W / 2, H * 0.44), E["title"], font=f, fill=255, anchor="mm",
           stroke_width=S.s(12), stroke_fill=0)
    # tour banner
    fb = S.f("black", 27)
    bw = fb.getlength(E["tour"]) + S.s(44)
    by = H * 0.44 + S.s(size * 0.5)
    d.rounded_rectangle([W / 2 - bw / 2, by, W / 2 + bw / 2, by + S.s(52)],
                        radius=S.s(8), fill=255, outline=0, width=S.s(4))
    S.text(W / 2, by + S.s(25), E["tour"], fb, anchor="mm")
    S.y = H


def lineup(S):
    W = S.W
    S.y += S.s(26)
    S.spaced(W / 2, S.y, E["lineup_kicker"], S.f("mono", 17), 4, anchor="m")
    S.y += S.s(34)
    for word in E["headliner"]:
        size = 150
        while S.f("black", size).getlength(word) > W - 2 * S.M:
            size -= 2
        f = S.f("black", size)
        S.text(W / 2, S.y - S.s(size * 0.27), word, f, anchor="ma")
        S.y += S.s(size * 0.86)
    S.y += S.s(14)
    S.rule(5, 10)
    size = 62
    while S.f("black", size).getlength(E["second"]) > W - 2 * S.M:
        size -= 2
    S.text(W / 2, S.y - S.s(size * 0.2), E["second"], S.f("black", size),
           anchor="ma")
    S.y += S.s(size * 1.06)
    S.rule(2, 12)
    for line in E.get("third", []):
        size = 22
        while S.f("bold", size).getlength(line) > W - 2 * S.M and size > 12:
            size -= 1
        S.text(W / 2, S.y, line, S.f("bold", size), anchor="ma")
        S.y += S.s(32)
    if E.get("fourth"):
        S.y += S.s(4)
        S.text(W / 2, S.y, E["fourth"], S.f("serifi", 24), anchor="ma")
        S.y += S.s(34)


def set_times(S):
    d, W, M = S.d, S.W, S.M
    cw, chh = S.s(92), S.s(36)
    tx = M + cw + S.s(14)
    for stage, rows in E["stages"]:
        bar(S, stage)
        first = True
        for tm, what, where, note in rows:
            if not first:
                d.rectangle([M + cw / 2 - 1, S.y - S.s(14), M + cw / 2 + 1,
                             S.y], fill=0)
            first = False
            blank = "_" in tm
            if blank:
                d.rounded_rectangle([M, S.y, M + cw, S.y + chh],
                                    radius=S.s(6), outline=0, width=S.s(3))
                S.text(M + cw / 2, S.y + chh / 2 - S.s(2), ":",
                       S.f("mono", 22), anchor="mm")
            else:
                d.rounded_rectangle([M, S.y, M + cw, S.y + chh],
                                    radius=S.s(6), fill=0)
                S.text(M + cw / 2, S.y + chh / 2 - S.s(1), tm,
                       S.f("mono", 22), fill=255, anchor="mm")
            S.text(tx, S.y + chh / 2 - S.s(2), what, S.f("black", 27),
                   anchor="lm")
            S.text(W - M, S.y + chh / 2, where, S.f("sans", 20), anchor="rm")
            y0 = S.y
            S.y += chh + S.s(4)
            if note:
                f = S.f("sans", 20)
                for line in S.wrap(note, f, W - M - tx):
                    S.text(tx, S.y, line, f)
                    S.y += round(f.size * 1.28)
            # connector down the chip column
            d.rectangle([M + cw / 2 - 1, y0 + chh, M + cw / 2 + 1, S.y],
                        fill=0)
            S.y += S.s(14)
        S.y -= S.s(14)


def icon(S, kind, cx, cy, r):
    d = S.d
    w = S.s(3)
    if kind == "sun":
        rr = r * 0.48
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=0)
        for i in range(8):
            a = i * math.pi / 4
            d.line([cx + math.cos(a) * r * 0.68, cy + math.sin(a) * r * 0.68,
                    cx + math.cos(a) * r, cy + math.sin(a) * r], fill=0,
                   width=w)
    elif kind in ("cloud", "rain"):
        oy = -r * 0.15 if kind == "rain" else r * 0.1
        for dx, dy, rr in [(-0.42, 0.1, 0.42), (0.05, -0.18, 0.55),
                           (0.5, 0.12, 0.4)]:
            d.ellipse([cx + dx * r - rr * r, cy + oy + dy * r - rr * r,
                       cx + dx * r + rr * r, cy + oy + dy * r + rr * r],
                      fill=0)
        d.rectangle([cx - r * 0.5, cy + oy + r * 0.1, cx + r * 0.55,
                     cy + oy + r * 0.5], fill=0)
        if kind == "rain":
            for dx in (-0.45, 0, 0.45):
                d.line([cx + dx * r + r * 0.1, cy + r * 0.55,
                        cx + dx * r - r * 0.1, cy + r], fill=0, width=w)
    elif kind == "moon":      # real phase for the date, as seen from the south
        rr = int(r * 0.7)
        p = moon_phase(E["date"])[0]
        c = math.cos(2 * math.pi * p)
        for yy in range(-rr, rr + 1):
            hw = math.sqrt(rr * rr - yy * yy)
            for xx in range(-rr, rr + 1):
                if abs(xx) > hw:
                    continue
                lit = (xx > hw * c) if p < 0.5 else (xx < -hw * c)
                if not lit:
                    S.img.putpixel((int(cx) - xx, int(cy) + yy), 0)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=0, width=w)


def sky(S):
    d, W, M = S.d, S.W, S.M
    bar(S, E.get("sky_title", "OUTDOOR SHOW  ·  THE SKY"))
    n = len(E["sky"])
    cw = (W - 2 * M) / n
    top = S.y
    for i, (when, kind, temp, tag) in enumerate(E["sky"]):
        cx = M + cw * i + cw / 2
        S.text(cx, top, when, S.f("mono", 17), anchor="ma")
        icon(S, kind, cx, top + S.s(58), S.s(26))
        S.text(cx, top + S.s(92), temp, S.f("black", 30), anchor="ma")
        if tag:
            f = S.f("mono", 15)
            tw = f.getlength(tag) + S.s(12)
            d.rectangle([cx - tw / 2, top + S.s(134), cx + tw / 2,
                         top + S.s(156)], fill=0)
            S.text(cx, top + S.s(145), tag, f, fill=255, anchor="mm")
        if i:
            for yy in range(int(top), int(top + S.s(156)), S.s(8)):
                d.rectangle([M + cw * i, yy, M + cw * i + 1, yy + S.s(3)],
                            fill=0)
    S.y = top + S.s(172)
    if E.get("sky_note"):
        S.para(E["sky_note"], S.f("serif", 23))


def entry(S):
    d, W, M = S.d, S.W, S.M
    S.y += S.s(30)
    top = S.y
    pad = S.s(18)
    S.y += S.s(16)
    S.text(W / 2, S.y, E.get("entry_title", "CONDITIONS OF ENTRY"),
           S.f("black", 32), anchor="ma")
    S.y += S.s(52)
    d.rectangle([M + pad, S.y, W - M - pad, S.y + S.s(3)], fill=0)
    S.y += S.s(18)
    r = S.s(15)
    tx = M + pad + 2 * r + S.s(16)
    fb, fs = S.f("bold", 23), S.f("sans", 21)
    for ok, head, sub in E["entry"]:
        cx, cy = M + pad + r, S.y + S.s(16)
        if ok:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
            d.line([cx - r * 0.5, cy, cx - r * 0.1, cy + r * 0.42,
                    cx + r * 0.52, cy - r * 0.4], fill=255, width=S.s(4),
                   joint="curve")
        else:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0,
                      width=S.s(4))
            k = r * 0.68
            d.line([cx - k, cy - k, cx + k, cy + k], fill=0, width=S.s(4))
        for line in S.wrap(head, fb, W - M - pad - tx):
            S.text(tx, S.y, line, fb)
            S.y += round(fb.size * 1.25)
        if sub:
            for line in S.wrap(sub, fs, W - M - pad - tx):
                S.text(tx, S.y, line, fs)
                S.y += round(fs.size * 1.25)
        S.y += S.s(12)
    S.y += S.s(2)
    f = S.f("sans", 17)
    for line in S.wrap(E.get("entry_src", ""), f, W - 2 * M - 2 * pad):
        S.text(W / 2, S.y, line, f, anchor="ma")
        S.y += round(f.size * 1.3)
    S.y += S.s(16)
    d.rectangle([M, top, W - M, S.y], outline=0, width=S.s(6))
    d.rectangle([M + S.s(9), top + S.s(9), W - M - S.s(9), S.y - S.s(9)],
                outline=0, width=S.s(2))


def rider(S):
    d, W, M = S.d, S.W, S.M
    bar(S, E.get("rider_title", "THE RIDER"))
    f = S.f("sans", 23)
    lh = round(f.size * 1.28)
    bs = S.s(24)
    tx = M + bs + S.s(14)
    for group, items in E["rider"]:
        S.spaced(M, S.y, group, S.f("mono", 17), 4)
        S.y += S.s(30)
        for item in items:
            d.ellipse([M, S.y + S.s(4), M + bs, S.y + S.s(4) + bs],
                      outline=0, width=S.s(3))
            for line in S.wrap(item, f, W - M - tx):
                S.text(tx, S.y, line, f)
                S.y += lh
            S.y += S.s(10)
        S.y += S.s(8)
    for _ in range(E.get("blank", 3)):
        d.ellipse([M, S.y, M + bs, S.y + bs], outline=0, width=S.s(3))
        for xx in range(int(tx), W - M, S.s(8)):
            d.rectangle([xx, S.y + bs - 1, xx + S.s(3), S.y + bs], fill=0)
        S.y += bs + S.s(20)
    S.y -= S.s(14)


def inbox(S):
    d, W, M = S.d, S.W, S.M
    bar(S, E.get("inbox_title", "MERCH DESK  ·  YOUR INBOX"))
    fk, f = S.f("mono", 17), S.f("sans", 22)
    for key, text in E["inbox"]:
        kw = sum(fk.getlength(c) + S.s(3) for c in key) + S.s(14)
        d.rectangle([M, S.y, M + kw, S.y + S.s(28)], fill=0)
        S.spaced(M + S.s(8), S.y + S.s(3), key, fk, 3, fill=255)
        S.y += S.s(36)
        for line in S.wrap(text, f, W - 2 * M):
            S.text(M, S.y, line, f)
            S.y += round(f.size * 1.28)
        S.y += S.s(14)
    S.y -= S.s(14)


def encore(S):
    d, W, M = S.d, S.W, S.M
    bar(S, E.get("encore_title", "ENCORE"))
    for tm, what, where in E["encore"]:
        S.text(M, S.y + S.s(2), tm, S.f("mono", 21))
        S.text(M + S.s(86), S.y, what, S.f("bold", 24))
        S.text(W - M, S.y + S.s(2), where, S.f("sans", 21), anchor="ra")
        S.y += S.s(38)
    S.y -= S.s(8)


def liner(S):
    d, W, M = S.d, S.W, S.M
    S.y += S.s(36)
    # a record, half out of its sleeve
    R = S.s(150)
    cx, cy = W / 2, S.y + R
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=0)
    for rr in range(S.s(62), R - S.s(6), S.s(7)):
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=255, width=1)
    # shine wedges
    for a0 in (-60, 120):
        for rr in range(S.s(64), R - S.s(8), S.s(7)):
            d.arc([cx - rr - 2, cy - rr - 2, cx + rr + 2, cy + rr + 2],
                  a0, a0 + 22, fill=255, width=S.s(3))
    lr = S.s(54)
    d.ellipse([cx - lr, cy - lr, cx + lr, cy + lr], fill=255)
    S.spaced(cx, cy - S.s(36), "LINER", S.f("mono", 17), 3, anchor="m")
    S.spaced(cx, cy + S.s(14), "NOTES", S.f("mono", 17), 3, anchor="m")
    d.ellipse([cx - S.s(6), cy - S.s(6), cx + S.s(6), cy + S.s(6)], fill=0)
    S.y = cy + R + S.s(26)
    f = S.f("serif", 24)
    for side, text in E["sides"]:
        fk = S.f("mono", 18)
        kw = sum(fk.getlength(c) + S.s(4) for c in side) + S.s(16)
        d.rectangle([W / 2 - kw / 2, S.y, W / 2 + kw / 2, S.y + S.s(30)],
                    fill=0)
        S.spaced(W / 2, S.y + S.s(3), side, fk, 4, fill=255, anchor="m")
        S.y += S.s(42)
        for line in S.wrap(text, f, W - 2 * M - S.s(16)):
            S.text(W / 2, S.y, line, f, anchor="ma")
            S.y += round(f.size * 1.32)
        S.y += S.s(22)


def card(S, standalone=False):
    d, W, M = S.d, S.W, S.M
    c = E["card"]
    if standalone:
        S.y += S.s(12)
    else:
        S.y += S.s(14)
        for xx in range(0, W, S.s(14)):
            d.rectangle([xx, S.y, xx + S.s(8), S.y + S.s(2)], fill=0)
        S.y += S.s(10)
        S.spaced(W / 2, S.y, E.get("card_cut", "TEAR HERE  ·  POCKET CARD"),
                 S.f("mono", 15), 4, anchor="m")
        S.y += S.s(36)
    top = S.y
    H = S.s(372)
    d.rounded_rectangle([M, top, W - M, top + H], radius=S.s(20), fill=0)
    n = len(c["times"])
    cw = (W - 2 * M) / n
    for i, (k, v) in enumerate(c["times"]):
        cx = M + cw * i + cw / 2
        S.spaced(cx, top + S.s(22), k, S.f("mono", 17), 4, fill=255,
                 anchor="m")
        S.text(cx, top + S.s(42), v, S.f("black", 50), fill=255, anchor="ma")
    y = top + S.s(120)
    d.rectangle([M + S.s(20), y, W - M - S.s(20), y + S.s(2)], fill=255)
    S.text(W / 2, y + S.s(14), c["seats"], S.f("bold", 24), fill=255,
           anchor="ma")
    y += S.s(60)
    d.rounded_rectangle([M + S.s(20), y, W - M - S.s(20), y + S.s(122)],
                        radius=S.s(12), fill=255)
    S.spaced(W / 2, y + S.s(10), c["home_k"], S.f("mono", 17), 4, anchor="m")
    S.text(W / 2, y + S.s(26), c["home"], S.f("black", 46), anchor="ma")
    S.text(W / 2, y + S.s(88), c["home_d"], S.f("sans", 19), anchor="ma")
    S.spaced(W / 2, top + H - S.s(40), c["rules"], S.f("mono", 15), 2,
             fill=255, anchor="m")
    S.y = top + H + S.s(22)
    if not standalone:
        sign(S)


def sign(S):
    S.spaced(S.W / 2, S.y, E.get("sign", "PRINTED BY AN AGENT"), S.f("mono", 14), 2,
             anchor="m")
    S.y += S.s(30)


def card_alone(S):
    card(S, standalone=True)


def main_end(S):
    S.y += S.s(6)
    S.rule(2, 14)
    sign(S)


OPTIONAL = [("sky", sky), ("entry", entry), ("rider", rider),
            ("inbox", inbox), ("encore", encore), ("sides", liner)]


def body():
    """Sections in print order; optional ones appear only if their key does."""
    return ([header, lineup, set_times]
            + [fn for key, fn in OPTIONAL if E.get(key)])


def render(width, parts):
    S = Sheet(width)
    S.img = Image.new("L", (width, 12000), 255)
    S.d = ImageDraw.Draw(S.img)
    for part in parts:
        part(S)
    return S.finish()


if __name__ == "__main__":
    ap = cli()
    ap.add_argument("--split", action="store_true",
                    help="pocket card as its own print job, cut separately")
    a = ap.parse_args()
    E.update(load_edition(a.edition))
    has_card = bool(E.get("card"))
    if a.split and has_card:
        jobs = [render(a.width, body() + [main_end]),
                render(a.width, [card_alone])]
    else:
        jobs = [render(a.width, body() + ([card] if has_card else [main_end]))]
    run(jobs, a, "gig")
