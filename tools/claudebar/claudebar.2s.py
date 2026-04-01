#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# <xbar.title>ClaudeBar</xbar.title>
# <xbar.version>1.1.0</xbar.version>
# <xbar.desc>Real-time Claude Code token usage monitor</xbar.desc>
# <xbar.refreshOnOpen>true</xbar.refreshOnOpen>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

import json, os
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECTS   = Path.home() / ".claude" / "projects"
CACHE_FILE = Path.home() / ".claudebar_cache.json"

# ── Pricing (per 1M tokens, USD) ──────────────────────────────────────────────
_P = {
    "claude-opus-4-6":            (15.00, 75.00, 18.75, 1.50),
    "claude-sonnet-4-6":          ( 3.00, 15.00,  3.75, 0.30),
    "claude-3-7-sonnet-20250219": ( 3.00, 15.00,  3.75, 0.30),
    "claude-3-5-sonnet-20241022": ( 3.00, 15.00,  3.75, 0.30),
    "claude-haiku-4-5":           ( 0.80,  4.00,  1.00, 0.08),
    "claude-haiku-4-5-20251001":  ( 0.80,  4.00,  1.00, 0.08),
    "claude-3-5-haiku-20241022":  ( 0.80,  4.00,  1.00, 0.08),
    "claude-3-opus-20240229":     (15.00, 75.00, 18.75, 1.50),
    "claude-3-haiku-20240307":    ( 0.25,  1.25,  0.30, 0.03),
}
_DP = (3.00, 15.00, 3.75, 0.30)

def _price(m):
    if m in _P: return _P[m]
    for k, p in _P.items():
        if k in m: return p
    return _DP

def _fmt(n):
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}k"
    return str(n)

# ── File-change detection (mtime fingerprint) ─────────────────────────────────
def _fingerprint() -> float:
    """Return the latest mtime among all JSONL files."""
    latest = 0.0
    if PROJECTS.is_dir():
        for f in PROJECTS.rglob("*.jsonl"):
            try:
                t = f.stat().st_mtime
                if t > latest:
                    latest = t
            except OSError:
                pass
    return latest

def _load_cache() -> dict | None:
    try:
        raw = CACHE_FILE.read_text()
        c   = json.loads(raw)
        # Invalidate at midnight (new day)
        if c.get("date") != datetime.now().strftime("%Y-%m-%d"):
            return None
        return c
    except Exception:
        return None

def _save_cache(data: dict, mtime: float) -> None:
    payload = {
        "mtime": mtime,
        "date":  datetime.now().strftime("%Y-%m-%d"),
        "data":  data,
    }
    try:
        CACHE_FILE.write_text(json.dumps(payload))
    except Exception:
        pass

# ── JSONL reader ──────────────────────────────────────────────────────────────
def _read_stats() -> dict:
    today_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    inp = out = cw = cr = 0
    cost = 0.0
    by_model: dict = {}
    first_ts = None

    if PROJECTS.is_dir():
        for f in PROJECTS.rglob("*.jsonl"):
            try:
                lines = f.read_text(errors="ignore").splitlines()
            except OSError:
                continue
            for line in lines:
                if not line.strip(): continue
                try: e = json.loads(line)
                except: continue
                if e.get("type") != "assistant": continue
                ts = None
                try:
                    ts = datetime.fromisoformat(
                        e.get("timestamp","").replace("Z","+00:00")
                    )
                except Exception:
                    pass
                if ts is None or ts < today_utc: continue
                if first_ts is None or ts < first_ts: first_ts = ts
                msg   = e.get("message") or {}
                usage = msg.get("usage") or {}
                model = msg.get("model","unknown")
                i  = usage.get("input_tokens",0)
                o  = usage.get("output_tokens",0)
                cc = usage.get("cache_creation_input_tokens",0)
                rc = usage.get("cache_read_input_tokens",0)
                if i == 0 and o == 0: continue
                p = _price(model)
                c = (i*p[0]+o*p[1]+cc*p[2]+rc*p[3]) / 1_000_000
                inp+=i; out+=o; cw+=cc; cr+=rc; cost+=c
                bm = by_model.setdefault(model, [0,0,0,0,0.0])
                bm[0]+=i; bm[1]+=o; bm[2]+=cc; bm[3]+=rc; bm[4]+=c

    mins_remaining = 0
    if first_ts:
        elapsed        = (datetime.now(timezone.utc) - first_ts).total_seconds()
        mins_remaining = max(0, int((5*3600 - elapsed) / 60))

    return dict(
        inp=inp, out=out, cw=cw, cr=cr, cost=cost,
        by_model=by_model,
        mins=mins_remaining,
        first_ts=first_ts.isoformat() if first_ts else None,
    )

# ── Main: use cache if files unchanged, else re-read ─────────────────────────
current_mtime = _fingerprint()
cache         = _load_cache()

if cache and cache.get("mtime") == current_mtime:
    d = cache["data"]                   # files unchanged → instant return
else:
    d = _read_stats()
    _save_cache(d, current_mtime)       # persist for next run

# ── Compute display values ────────────────────────────────────────────────────
inp, out, cw, cr = d["inp"], d["out"], d["cw"], d["cr"]
cost      = d["cost"]
by_model  = d["by_model"]
mins      = d["mins"]

limit   = 150_000
total   = inp + out
pct     = round(total / limit * 100, 1)
pct_col = "#32d74b" if pct < 60 else ("#ff9f0a" if pct < 85 else "#ff453a")

h, m   = divmod(mins, 60)
time_s = f"{h}h {m}m" if h > 0 else (f"{m}m" if m > 0 else "—")

filled  = round(pct / 100 * 20)
bar_str = "█" * filled + "░" * (20 - filled)

# ── SwiftBar / xbar output ────────────────────────────────────────────────────
sep        = " · " if mins > 0 else ""
mins_label = f"{mins}m" if mins > 0 else ""
print(f"☁ {pct}%{sep}{mins_label} | color={pct_col} size=13")
print("---")
print(f"☁  Claude Code | size=15 color=white bold=true sfimage=cloud.fill")
print("---")
print(f"Token Usage | size=12 color=white bold=true")
print(f"{bar_str}  {pct}% | size=12 font=Menlo color={pct_col}")
print(f"{_fmt(total)} / {_fmt(limit)} | size=11 color=#aaaaaa")
print("---")
print(f"Session Time Remaining | size=12 color=white bold=true")
print(f"{time_s}  of 5h window | size=18 color=white bold=true")
print("---")
print(f"{'Input':<12}{'Output':<12}Cache | size=12 color=white bold=true font=Menlo")
print(f"{_fmt(inp):<12}{_fmt(out):<12}{_fmt(cw+cr)} | size=14 font=Menlo color=white")
print("---")
print(f"예상 비용  ${cost:.3f} | size=13 color=#32d74b bold=true")
print("---")
if by_model:
    print("모델별 사용량 | size=11 color=#aaaaaa bold=true")
    for mdl, v in sorted(by_model.items(), key=lambda x:-(x[1][0]+x[1][1])):
        short = (mdl.replace("claude-","")
                    .replace("-20251001","").replace("-20241022","")
                    .replace("-20250219","").replace("-20240229","")
                    .replace("-20240307",""))
        print(f"  {short:<26} {_fmt(v[0]+v[1]):>7}   ${v[4]:.3f} | size=12 font=Menlo color=white")
    print("---")
print("새로고침 | refresh=true color=#4a9eff")
