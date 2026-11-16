#!/usr/bin/env python3
"""Print a receipt for a finished Claude Code job: what was done, how long it
took, tokens used and the approximate API cost.

  job_receipt.py --title "Widget library" --did "Built 57 widgets" --did "Printed samples"
  job_receipt.py --session 74f0748d-... --attention "Check the ruler against a real one"
  job_receipt.py --since 2026-03-13T14:00 ...      only count work after this time
  job_receipt.py --json                            numbers only, no print

  job_receipt.py --hermes SESSION_ID ...           a Hermes Agent session instead
                                                   (bare --hermes = most recent)

With no --session it uses the session it is run from (CLAUDE_CODE_SESSION_ID),
else the most recently active one. Token counts come from the session
transcript; cost is tokens x the list prices in prices.json, so it is an
API-equivalent estimate, not a bill. For Hermes, counts and cost come from
Hermes's own session records (~/.hermes/state.db), read-only.
Add --print to print; --preview-dir to look.
"""
import argparse
import datetime as dt
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def find_transcript(session):
    root = os.path.expanduser("~/.claude/projects")
    if session and os.path.isfile(session):
        return session
    sid = session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if sid:
        hits = glob.glob(os.path.join(root, "*", sid + ".jsonl"))
        if hits:
            return hits[0]
        if session:
            raise SystemExit(f"No transcript found for session {session}")
    files = glob.glob(os.path.join(root, "*", "*.jsonl"))
    if not files:
        raise SystemExit("No Claude Code transcripts found under ~/.claude/projects")
    return max(files, key=os.path.getmtime)


def read(path, since=None):
    """Yield (timestamp, entry) for one transcript file."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            ts = o.get("timestamp")
            t = None
            if isinstance(ts, str):
                try:
                    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    t = None
            if since and (t is None or t < since):
                continue
            yield t, o


def tally(path, since=None):
    files = [path] + sorted(glob.glob(os.path.join(path[:-6], "subagents", "*.jsonl")))
    usage, tools, seen = {}, {}, {}
    first = last = None
    prompts = 0
    for i, f in enumerate(files):
        for t, o in read(f, since):
            if t:
                first = t if first is None or t < first else first
                last = t if last is None or t > last else last
            m = o.get("message") if isinstance(o.get("message"), dict) else None
            if not m:
                continue
            if o.get("type") == "user" and i == 0 and not o.get("isSidechain"):
                c = m.get("content")
                if isinstance(c, str) or (isinstance(c, list) and any(
                        isinstance(b, dict) and b.get("type") == "text" for b in c)):
                    prompts += 1
            if o.get("type") != "assistant":
                continue
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    key = (m.get("id"), b.get("id"))
                    if key not in seen:
                        seen[key] = 1
                        tools[b.get("name", "?")] = tools.get(b.get("name", "?"), 0) + 1
            u = m.get("usage")
            if u and m.get("id"):
                usage[m["id"]] = (m.get("model", "unknown"), u, i > 0)   # last write wins
    per = {}
    for model, u, sub in usage.values():
        p = per.setdefault(model, dict(input=0, output=0, cache_read=0, w5=0, w1=0,
                                       calls=0, sub_calls=0))
        cc = u.get("cache_creation") or {}
        w5 = cc.get("ephemeral_5m_input_tokens")
        w1 = cc.get("ephemeral_1h_input_tokens")
        if w5 is None and w1 is None:
            w5, w1 = u.get("cache_creation_input_tokens", 0) or 0, 0
        p["input"] += u.get("input_tokens", 0) or 0
        p["output"] += u.get("output_tokens", 0) or 0
        p["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        p["w5"] += w5 or 0
        p["w1"] += w1 or 0
        p["calls"] += 1
        p["sub_calls"] += 1 if sub else 0
    return dict(per=per, tools=tools, first=first, last=last, prompts=prompts,
                subagents=len(files) - 1)


def cost(per):
    with open(os.path.join(HERE, "prices.json"), encoding="utf-8") as fh:
        table = json.load(fh)
    total, rows, unknown = 0.0, [], []
    for model, p in sorted(per.items(), key=lambda kv: -kv[1]["output"]):
        pr = table["models"].get(model)
        if not pr:
            for key, val in table["models"].items():       # tolerate dated ids
                if model.startswith(key):
                    pr = val
        tok = p["input"] + p["output"] + p["cache_read"] + p["w5"] + p["w1"]
        if not pr:
            unknown.append(model)
            rows.append((model, tok, None))
            continue
        c = (p["input"] * pr["input"] + p["output"] * pr["output"]
             + p["cache_read"] * pr.get("cache_read", pr["input"] * 0.1)
             + p["w5"] * pr["input"] * 1.25 + p["w1"] * pr["input"] * 2.0) / 1e6
        total += c
        rows.append((pr["name"], tok, c))
    return total, rows, unknown, table["as_of"]


def hermes_session(sid):
    """Usage for one Hermes Agent session, from its state database (read-only)."""
    import sqlite3
    home = os.path.expanduser(os.environ.get("HERMES_HOME", "~/.hermes"))
    db = os.path.join(home, "state.db")
    if not os.path.exists(db):
        raise SystemExit(f"No Hermes state database at {db}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    if sid and sid != "latest":
        row = con.execute("select * from sessions where id = ?", (sid,)).fetchone()
        if not row:
            raise SystemExit(f"No Hermes session with id {sid}")
    else:
        row = con.execute("select * from sessions order by "
                          "coalesce(last_activity_at, started_at) desc limit 1").fetchone()
        if not row:
            raise SystemExit("Hermes has no sessions yet")
    row = dict(row)
    try:
        models = [dict(r) for r in con.execute(
            "select model, sum(api_call_count) calls, sum(input_tokens) i, "
            "sum(output_tokens) o, sum(cache_read_tokens) cr, sum(cache_write_tokens) cw, "
            "sum(estimated_cost_usd) est, sum(actual_cost_usd) act, max(cost_status) st "
            "from session_model_usage where session_id = ? group by model "
            "order by o desc", (row["id"],))]
    except sqlite3.Error:
        models = []
    return row, models


def hermes_receipt(a):
    row, models = hermes_session(a.hermes)
    end = row.get("ended_at") or row.get("last_activity_at") or row["started_at"]
    secs = max(0, end - row["started_at"])
    dur = f"{int(secs // 3600)} h {int(secs % 3600 // 60):02d} min" if secs >= 3600 \
        else f"{int(secs // 60)} min"
    cost = row.get("actual_cost_usd") or row.get("estimated_cost_usd") or 0
    status = (row.get("cost_status") or "").replace("_", " ")
    lines = [["Wall-clock time", dur], ["Messages", str(row.get("message_count") or 0)],
             ["Model calls", str(row.get("api_call_count") or 0)],
             ["Tool calls", str(row.get("tool_call_count") or 0)], ["---", ""],
             ["Input tokens", short(row.get("input_tokens") or 0)],
             ["Cache writes", short(row.get("cache_write_tokens") or 0)],
             ["Cache reads", short(row.get("cache_read_tokens") or 0)],
             ["Output tokens", short(row.get("output_tokens") or 0)]]
    if row.get("reasoning_tokens"):
        lines.append(["Reasoning tokens", short(row["reasoning_tokens"])])
    lines.append(["---", ""])
    for m in models or [{"model": row.get("model") or "model", "act": None, "est": cost,
                         "st": row.get("cost_status")}]:
        c = m.get("act") or m.get("est") or 0
        lines.append([str(m["model"])[:26],
                      f"${c:,.2f}" if c else (m.get("st") or "no price").replace("_", " ")])
    total = f"US${cost:,.2f}" if cost else (status or "not priced")
    foot = ("Cost as recorded by Hermes for this session." if cost else
            "Hermes recorded no charge for this session"
            + (f" ({status})." if status else "."))
    if a.json:
        print(json.dumps({"session": row["id"], "duration_seconds": round(secs),
                          "messages": row.get("message_count"),
                          "model_calls": row.get("api_call_count"),
                          "tool_calls": row.get("tool_call_count"),
                          "tokens": {k: row.get(k) for k in (
                              "input_tokens", "output_tokens", "cache_read_tokens",
                              "cache_write_tokens", "reasoning_tokens")},
                          "usd": cost or None, "cost_status": row.get("cost_status"),
                          "by_model": models}, indent=2))
        raise SystemExit
    when = dt.datetime.fromtimestamp(end).strftime("%a %-d %b %Y  %-I:%M %p")
    return lines, total, foot, when.replace("AM", "am").replace("PM", "pm")


def short(n):
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}k" if n >= 1e3 else str(n)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session")
    ap.add_argument("--hermes", nargs="?", const="latest", metavar="SESSION_ID",
                    help="receipt for a Hermes Agent session (default: most recent)")
    ap.add_argument("--since", help="ISO time; only count entries after it")
    ap.add_argument("--title", default="Job complete")
    ap.add_argument("--did", action="append", default=[], help="one thing done (repeat)")
    ap.add_argument("--attention", action="append", default=[],
                    help="something the human must look at (repeat)")
    ap.add_argument("--store", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--out")
    ap.add_argument("--preview-dir")
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()

    if a.hermes:
        import briefing as N
        from widgets import render_spec
        lines, total_txt, foot, when = hermes_receipt(a)
        W = [{"type": "receipt", "store": a.store or "HERMES AGENT",
              "header": [a.title, when], "lines": lines,
              "total": ["COST", total_txt], "footer": foot}]
        if a.did:
            W += [{"type": "heading", "text": "WHAT GOT DONE"},
                  {"type": "checklist", "items": a.did, "style": "circle", "size": 22}]
        for note in a.attention:
            W.append({"type": "callout", "label": "NEEDS YOU", "text": note, "size": 23})
        N.run(render_spec({"widgets": W}, a.width), a, "receipt")
        raise SystemExit

    since = None
    if a.since:
        since = dt.datetime.fromisoformat(a.since)
        if since.tzinfo is None:
            since = since.astimezone()
    path = find_transcript(a.session)
    T = tally(path, since)
    total, rows, unknown, as_of = cost(T["per"])
    P = T["per"].values()
    sums = {k: sum(p[k] for p in P) for k in ("input", "output", "cache_read", "w5", "w1", "calls")}
    secs = (T["last"] - T["first"]).total_seconds() if T["first"] and T["last"] else 0
    dur = f"{int(secs // 3600)} h {int(secs % 3600 // 60):02d} min" if secs >= 3600 \
        else f"{int(secs // 60)} min"
    ntools = sum(T["tools"].values())

    if a.json:
        print(json.dumps({"transcript": path, "duration_seconds": round(secs),
                          "prompts": T["prompts"], "model_calls": sums["calls"],
                          "tool_calls": ntools, "subagents": T["subagents"],
                          "tokens": sums, "by_model": [
                              {"model": n, "tokens": t, "usd": c} for n, t, c in rows],
                          "approx_usd": round(total, 2), "prices_as_of": as_of,
                          "unpriced_models": unknown}, indent=2))
        raise SystemExit

    import briefing as N
    from widgets import render_spec
    local = (T["last"] or dt.datetime.now(dt.timezone.utc)).astimezone()
    lines = [["Wall-clock time", dur], ["Your prompts", str(T["prompts"])],
             ["Model calls", str(sums["calls"])], ["Tool calls", str(ntools)]]
    if T["subagents"]:
        lines.append(["Subagents", str(T["subagents"])])
    lines += [["---", ""],
              ["Input tokens", short(sums["input"])],
              ["Cache writes", short(sums["w5"] + sums["w1"])],
              ["Cache reads", short(sums["cache_read"])],
              ["Output tokens", short(sums["output"])],
              ["---", ""]]
    for name, tok, c in rows:
        lines.append([name, f"${c:,.2f}" if c is not None else "no price"])
    W = [{"type": "receipt", "store": a.store or "CLAUDE CODE",
          "header": [a.title, local.strftime("%a %-d %b %Y  %-I:%M %p").replace("AM", "am").replace("PM", "pm")],
          "lines": lines, "total": ["APPROX COST", f"US${total:,.2f}"],
          "footer": f"API-equivalent estimate at list prices ({as_of}). Not a bill."}]
    if a.did:
        W += [{"type": "heading", "text": "WHAT GOT DONE"},
              {"type": "checklist", "items": a.did, "style": "circle", "size": 22}]
    for note in a.attention:
        W.append({"type": "callout", "label": "NEEDS YOU", "text": note, "size": 23})
    top = sorted(T["tools"].items(), key=lambda kv: -kv[1])[:5]
    if top:
        W.append({"type": "text", "font": "mono", "size": 15, "align": "center",
                  "text": "  ".join(f"{k.split('__')[-1]}:{v}" for k, v in top)})
    N.run(render_spec({"widgets": W}, a.width), a, "receipt")
