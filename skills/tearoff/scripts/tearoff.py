#!/usr/bin/env python3
"""tearoff: things for AI agents (and people) to print on a thermal receipt printer.

  tearoff setup --printer 192.168.1.50 [--width 576] [--lat 51.51 --lon -0.13 --place LONDON]
  tearoff test                     print a small alignment strip
  tearoff status                   ask the printer how it is

  tearoff quick <command> ...      one-line prints: todo, shop, note, maze, banner ...
  tearoff strip --spec FILE        print a strip built from widgets
  tearoff widgets                  list every widget   (tearoff widgets --doc for JSON examples)
  tearoff sampler                  render or print one of everything
  tearoff newspaper --edition FILE daily briefing, newspaper layout
  tearoff gig --edition FILE       daily briefing, gig-poster layout
  tearoff facts --date 2026-03-12  weather and day facts as JSON
  tearoff week --start 2026-03-16 --out week.json     start a week-ahead strip
  tearoff receipt --title "..." --did "..."           job receipt (Claude Code; --hermes for Hermes)

Add --print to print; without it use --preview-dir DIR or --out FILE to look first.
"""
import json
import os
import sys

LIB = os.path.dirname(os.path.realpath(__file__))
MAP = {"quick": "quick.py", "strip": "widgets.py", "newspaper": "briefing.py",
       "gig": "briefing_gig.py", "facts": "facts.py", "week": "week_ahead.py",
       "receipt": "job_receipt.py"}


def run(script, args):
    os.execv(sys.executable, [sys.executable, os.path.join(LIB, script)] + args)


def setup(args):
    import argparse
    ap = argparse.ArgumentParser(prog="tearoff setup")
    ap.add_argument("--printer", help="printer IP address or hostname")
    ap.add_argument("--port", type=int)
    ap.add_argument("--width", type=int, help="576 for 80 mm paper, 384 for 58 mm")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--place", help="short place name for the weather heading")
    ap.add_argument("--masthead", help="name on the newspaper masthead")
    ap.add_argument("--schedule-cmd", help="command that prints your timetable as JSON")
    a = ap.parse_args(args)
    path = os.path.expanduser(os.environ.get("TEAROFF_CONFIG",
                                             "~/.config/tearoff/config.json"))
    cfg = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    for key, val in (("printer_host", a.printer), ("printer_port", a.port),
                     ("width", a.width), ("lat", a.lat), ("lon", a.lon),
                     ("place", a.place and a.place.upper()), ("masthead", a.masthead),
                     ("schedule_cmd", a.schedule_cmd)):
        if val is not None:
            cfg[key] = val
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    print(f"saved {path}")
    print(json.dumps(cfg, indent=2))


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "setup":
        setup(rest)
    elif cmd == "status":
        sys.path.insert(0, LIB)
        import briefing
        print(briefing.status())
    elif cmd == "test":
        import tempfile
        spec = {"widgets": [
            {"type": "title", "text": "TEAROFF TEST", "sub": "if you can read this, it works"},
            {"type": "text", "text": "The frame below should have equal margins left and "
                                     "right. If the right edge is cut off, lower the width: "
                                     "tearoff setup --width 512 (or 384 for 58 mm paper)."},
            {"type": "callout", "label": "EDGE TO EDGE", "text": "|<- left        right ->|"},
            {"type": "ruler", "length_mm": 50},
            {"type": "signoff", "text": "Ready when you are.", "stamp": "TEAROFF"}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(spec, tf)
        run("widgets.py", ["--spec", tf.name] + (rest or ["--print"]))
    elif cmd == "widgets":
        run("widgets.py", ["--doc"] if "--doc" in rest else ["--list"])
    elif cmd == "sampler":
        run("widgets.py", ["--sampler"] + rest)
    elif cmd in MAP:
        run(MAP[cmd], rest)
    else:
        print(f"unknown command {cmd!r}\n{__doc__}")
        sys.exit(2)


if __name__ == "__main__":
    main()
