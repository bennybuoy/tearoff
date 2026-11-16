#!/usr/bin/env python3
"""Quick prints: one command, one piece of paper. Add --print to print.

  quick.py todo "Saturday jobs" "Mow the lawn" "Bins out" --blank 2
  quick.py shop Milk Bananas "2 avocados" Sourdough --store Woolworths
  quick.py shop "Fruit: apples, pears" "Bakery: sourdough" Milk
  quick.py meals "Mon: Tacos" "Tue: Fried rice (20 min)" "Wed: Pasta"
  quick.py note "Back in 10 minutes" [--invert] [--from Sam]
  quick.py countdown "the summer holidays" 2026-12-18
  quick.py calendar 2026-12 [--ring 25 --mark 4 11]
  quick.py week 2026-03-16 --habits Water Walk Marking
  quick.py maze [--size 16] [--seed 7]
  quick.py wordsearch "Cell division" MEIOSIS MITOSIS GAMETE ...
  quick.py art phyllotaxis|flow|contours|ridges [--seed 3]
  quick.py exit-ticket 12PHY "Why does a satellite in orbit not fall?" --copies 5
  quick.py tickets MERIT --count 10 [--start 1] [--sub "Ms Rivera"]
  quick.py coupon "ONE SLEEP-IN" --to Sam --from "The kids"
  quick.py qr "https://example.com" --caption "Open me"
  quick.py games noughts|dots
  quick.py photo ~/Pictures/kids.jpg --caption "Beach day" [--rotate]
  quick.py banner "HAPPY BIRTHDAY"
  quick.py ruler 150                       (length in mm; 1500 = height chart)
  quick.py labels Flour Sugar "Lab coats"  (one cut piece each)
  quick.py chain --count 4                 (3 paper-chain links per piece)
  quick.py sudoku --level medium [--solution]
  quick.py bingo "Cell bingo" word1 ... word24+ --cards 6
  quick.py punnett Aa Aa [--blank]
  quick.py cryptogram "The sentence to hide" [--hints 2]
  quick.py scorepad Sam Ana Tom [--title UNO]
  quick.py wifi "NetworkName" "password"
  quick.py grid                            (5 mm graph paper)

Every command also takes --preview-dir DIR and --out FILE.
"""
import argparse
import datetime as dt

import briefing as N
from widgets import render_spec

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
# The shared flags work before or after the command name.
common = argparse.ArgumentParser(add_help=False)
common.add_argument("--width", type=int, default=argparse.SUPPRESS)
common.add_argument("--out", default=argparse.SUPPRESS)
common.add_argument("--preview-dir", default=argparse.SUPPRESS)
common.add_argument("--print", action="store_true", default=argparse.SUPPRESS)
ap.set_defaults(width=N.CONFIG["width"], out=None, preview_dir=None, print=False)
for act in common._actions:
    ap._add_action(act)
_sub = ap.add_subparsers(dest="cmd", required=True)


class sub:                                   # every command inherits the flags
    @staticmethod
    def add_parser(name):
        return _sub.add_parser(name, parents=[common])

p = sub.add_parser("todo"); p.add_argument("title"); p.add_argument("items", nargs="*")
p.add_argument("--blank", type=int, default=2); p.add_argument("--small", action="store_true")
p = sub.add_parser("shop"); p.add_argument("items", nargs="+"); p.add_argument("--store")
p.add_argument("--title", default="SHOPPING"); p.add_argument("--blank", type=int, default=2)
p = sub.add_parser("meals"); p.add_argument("rows", nargs="+"); p.add_argument("--title", default="DINNERS")
p = sub.add_parser("note"); p.add_argument("text"); p.add_argument("--invert", action="store_true")
p.add_argument("--from", dest="sender")
p = sub.add_parser("countdown"); p.add_argument("label"); p.add_argument("date")
p = sub.add_parser("calendar"); p.add_argument("month")
p.add_argument("--ring", type=int, nargs="*", default=[]); p.add_argument("--mark", type=int, nargs="*", default=[])
p = sub.add_parser("week"); p.add_argument("start"); p.add_argument("--habits", nargs="+", required=True)
p = sub.add_parser("maze"); p.add_argument("--size", type=int, default=16); p.add_argument("--seed", type=int)
p = sub.add_parser("wordsearch"); p.add_argument("title"); p.add_argument("words", nargs="+")
p.add_argument("--size", type=int, default=13); p.add_argument("--seed", type=int); p.add_argument("--backwards", action="store_true")
p = sub.add_parser("art"); p.add_argument("style", choices=["phyllotaxis", "flow", "contours", "ridges", "mandala"])
p.add_argument("--seed", type=int); p.add_argument("--caption")
p = sub.add_parser("exit-ticket"); p.add_argument("klass"); p.add_argument("question")
p.add_argument("--copies", type=int, default=1); p.add_argument("--lines", type=int, default=4)
p = sub.add_parser("tickets"); p.add_argument("title"); p.add_argument("--count", type=int, default=5)
p.add_argument("--start", type=int, default=1); p.add_argument("--sub", default="")
p = sub.add_parser("coupon"); p.add_argument("text"); p.add_argument("--to"); p.add_argument("--from", dest="sender")
p.add_argument("--expires")
p = sub.add_parser("qr"); p.add_argument("data"); p.add_argument("--caption")
p = sub.add_parser("games"); p.add_argument("kind", choices=["noughts", "dots"])
p = sub.add_parser("photo"); p.add_argument("path"); p.add_argument("--caption", default="")
p.add_argument("--rotate", action="store_true"); p.add_argument("--contrast", type=float, default=1.2)
p = sub.add_parser("banner"); p.add_argument("text")
p = sub.add_parser("ruler"); p.add_argument("mm", type=int, nargs="?", default=150)
p = sub.add_parser("labels"); p.add_argument("texts", nargs="+"); p.add_argument("--sub", default="")
p = sub.add_parser("chain"); p.add_argument("--count", type=int, default=3); p.add_argument("--mm", type=int, default=180)
p = sub.add_parser("sudoku"); p.add_argument("--level", default="easy", choices=["easy", "medium", "hard"])
p.add_argument("--seed", type=int); p.add_argument("--solution", action="store_true")
p = sub.add_parser("bingo"); p.add_argument("title"); p.add_argument("words", nargs="+")
p.add_argument("--cards", type=int, default=1)
p = sub.add_parser("punnett"); p.add_argument("p1"); p.add_argument("p2"); p.add_argument("--blank", action="store_true")
p = sub.add_parser("cryptogram"); p.add_argument("text"); p.add_argument("--hints", type=int, default=2)
p.add_argument("--seed", type=int)
p = sub.add_parser("scorepad"); p.add_argument("players", nargs="+"); p.add_argument("--title", default="SCORES")
p.add_argument("--rows", type=int, default=10)
p = sub.add_parser("wifi"); p.add_argument("ssid"); p.add_argument("password")
p = sub.add_parser("grid"); p.add_argument("--rows", type=int, default=12)
a = ap.parse_args()

today = dt.date.today()
stamp = today.strftime("%a %-d %b %Y")
W = []
if a.cmd == "todo":
    W = [{"type": "title", "text": a.title.upper(), "sub": stamp},
         {"type": "checklist", "items": a.items, "blank": a.blank,
          "size": 23 if a.small else 28}]
elif a.cmd == "shop":
    from widgets import sort_into_aisles
    loose, named = [], []
    for it in a.items:                      # "Aisle: a, b, c" keeps your own grouping
        if ":" in it:
            head, rest = it.split(":", 1)
            named.append([head.strip().upper(),
                          [x.strip() for x in rest.split(",") if x.strip()]])
        else:
            loose += [x.strip() for x in it.split(",") if x.strip()]
    W = [{"type": "shopping_list", "title": a.title.upper(), "store": a.store,
          "when": stamp, "groups": named + sort_into_aisles(loose), "blank": a.blank}]
elif a.cmd == "meals":
    rows = []
    for r in a.rows:                         # "Mon: Tacos (note)"
        day, _, rest = r.partition(":")
        meal, _, note = rest.strip().partition("(")
        rows.append([day.strip(), meal.strip(), note.rstrip(") ").strip()])
    W = [{"type": "meal_plan", "title": a.title.upper(), "rows": rows}]
elif a.cmd == "note":
    W = [{"type": "big_note", "text": a.text.upper(), "invert": a.invert, "max_lines": 4}]
    if a.sender:
        W.append({"type": "text", "align": "center", "font": "serifi", "size": 24,
                  "text": f"{a.sender}, {stamp}"})
elif a.cmd == "countdown":
    W = [{"type": "countdown", "label": a.label, "date": a.date}]
elif a.cmd == "calendar":
    W = [{"type": "month", "month": a.month, "ring": a.ring, "marks": a.mark,
          "today": today.day if today.strftime("%Y-%m") == a.month else 0}]
elif a.cmd == "week":
    d0 = dt.date.fromisoformat(a.start)
    W = [{"type": "title", "text": "THIS WEEK", "sub": "from " + d0.strftime("%a %-d %b")},
         {"type": "habit_grid", "habits": a.habits, "start": a.start, "days": 7}]
elif a.cmd == "maze":
    W = [{"type": "maze", "cols": a.size, "rows": round(a.size * 1.25), "seed": a.seed,
          "title": "FIND THE WAY OUT"}]
elif a.cmd == "wordsearch":
    W = [{"type": "wordsearch", "title": a.title.upper(), "words": a.words, "size": a.size,
          "seed": a.seed, "backwards": a.backwards}]
elif a.cmd == "art":
    W = [{"type": "art", "style": a.style, "seed": a.seed, "caption": a.caption}]
elif a.cmd == "exit-ticket":
    for i in range(a.copies):
        W += [{"type": "exit_ticket", "class": a.klass, "question": a.question,
               "lines": a.lines}, {"type": "cut"}]
elif a.cmd == "tickets":
    for i in range(a.count):
        W += [{"type": "raffle_ticket", "title": a.title.upper(), "number": a.start + i,
               "sub": a.sub}, {"type": "cut"}]
elif a.cmd == "coupon":
    W = [{"type": "coupon", "text": a.text.upper(), "to": a.to, "from": a.sender,
          "expires": a.expires}]
elif a.cmd == "qr":
    W = [{"type": "qr", "data": a.data, "caption": a.caption}]
elif a.cmd == "games":
    W = [{"type": "games", "kind": a.kind}]
elif a.cmd == "photo":
    W = [{"type": "photo", "path": a.path, "caption": a.caption, "rotate": a.rotate,
          "contrast": a.contrast}]
elif a.cmd == "banner":
    W = [{"type": "banner", "text": a.text.upper()}]
elif a.cmd == "ruler":
    W = [{"type": "ruler", "length_mm": a.mm}]
elif a.cmd == "labels":
    for t in a.texts:
        W += [{"type": "label", "text": t.upper(), "sub": a.sub}, {"type": "cut"}]
elif a.cmd == "chain":
    for i in range(a.count):
        W += [{"type": "paper_chain", "length_mm": a.mm, "seed": i + 1, "gap": 0},
              {"type": "cut"}]
elif a.cmd == "sudoku":
    W = [{"type": "sudoku", "level": a.level, "seed": a.seed, "solution": a.solution}]
elif a.cmd == "bingo":
    import random as _r
    base = _r.randrange(10 ** 6)
    for i in range(a.cards):
        W += [{"type": "bingo", "title": a.title.upper(), "words": a.words,
               "seed": base + i}, {"type": "cut"}]
elif a.cmd == "punnett":
    W = [{"type": "punnett", "p1": a.p1, "p2": a.p2, "solved": not a.blank,
          "title": "PUNNETT SQUARE"}]
elif a.cmd == "cryptogram":
    W = [{"type": "cryptogram", "text": a.text, "hints": a.hints, "seed": a.seed,
          "title": "CRACK THE CODE"}]
elif a.cmd == "scorepad":
    W = [{"type": "scorepad", "title": a.title.upper(), "players": a.players,
          "rows": a.rows}]
elif a.cmd == "wifi":
    esc = lambda s: "".join("\\" + c if c in '\\;,:"' else c for c in s)
    W = [{"type": "title", "text": "WIFI", "sub": "point your camera at the code"},
         {"type": "qr", "data": f"WIFI:T:WPA;S:{esc(a.ssid)};P:{esc(a.password)};;",
          "size": 380},
         {"type": "keyvalue", "rows": [["Network", a.ssid], ["Password", a.password]]}]
elif a.cmd == "grid":
    W = [{"type": "lines", "style": "grid", "count": a.rows}]

N.run(render_spec({"date": today.isoformat(), "widgets": W}, a.width), a, a.cmd)
