#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# <xbar.title>ClaudeBar</xbar.title>
# <xbar.version>1.2.0</xbar.version>
# <xbar.desc>Real-time Claude Code token usage monitor</xbar.desc>
# <xbar.refreshOnOpen>true</xbar.refreshOnOpen>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

import json, os, re
from datetime import datetime, timezone, timedelta
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

# ── claude.ai usage fetch (via browser cookies) ───────────────────────────────
def _fetch_claude_ai_usage() -> float | None:
    """
    Try to fetch the actual usage percentage from claude.ai/settings/usage
    using the user's browser session cookies.
    Returns a float (0-100) or None if unavailable.
    """
    try:
        import browser_cookie3
        import urllib.request

        # Try Chrome first, then Safari, then Firefox
        cookies = None
        for loader in [
            lambda: browser_cookie3.chrome(domain_name=".claude.ai"),
            lambda: browser_cookie3.safari(domain_name=".claude.ai"),
            lambda: browser_cookie3.firefox(domain_name=".claude.ai"),
        ]:
            try:
                jar = loader()
                # Check if we got any cookies
                if jar:
                    cookies = jar
                    break
            except Exception:
                continue

        if not cookies:
            return None

        # Build a cookie header string
        import http.cookiejar
        cookie_header = "; ".join(
            f"{c.name}={c.value}"
            for c in cookies
            if "claude.ai" in (c.domain or "")
        )
        if not cookie_header:
            return None

        req = urllib.request.Request(
            "https://claude.ai/settings/usage",
            headers={
                "Cookie": cookie_header,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Extract __NEXT_DATA__ JSON embedded in the page
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            return None

        data = json.loads(m.group(1))

        # Navigate to usage info — path may vary; try common locations
        def _find_usage(obj, depth=0):
            if depth > 10: return None
            if isinstance(obj, dict):
                # Look for keys like "usagePercent", "percentUsed", "usage_percent"
                for key in obj:
                    lkey = key.lower()
                    if "percent" in lkey or "usage" in lkey:
                        val = obj[key]
                        if isinstance(val, (int, float)) and 0 <= val <= 100:
                            return float(val)
                        if isinstance(val, str):
                            try:
                                f = float(val.strip("%"))
                                if 0 <= f <= 100:
                                    return f
                            except ValueError:
                                pass
                for val in obj.values():
                    result = _find_usage(val, depth + 1)
                    if result is not None:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = _find_usage(item, depth + 1)
                    if result is not None:
                        return result
            return None

        return _find_usage(data)

    except ImportError:
        # browser_cookie3 not installed — silently skip
        return None
    except Exception:
        return None

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
def _parse_ts(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def _read_all_entries() -> list[tuple[datetime, dict]]:
    """Return all assistant entries as (timestamp, entry) sorted by time."""
    entries = []
    if not PROJECTS.is_dir():
        return entries
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
            ts = _parse_ts(e.get("timestamp", ""))
            if ts is None: continue
            msg   = e.get("message") or {}
            usage = msg.get("usage") or {}
            if usage.get("input_tokens", 0) == 0 and usage.get("output_tokens", 0) == 0:
                continue
            entries.append((ts, e))
    entries.sort(key=lambda x: x[0])
    return entries

def _aggregate(entries, cutoff: datetime) -> dict:
    inp = out = cw = cr = 0
    cost = 0.0
    by_model: dict = {}
    first_ts = None

    for ts, e in entries:
        if ts < cutoff: continue
        if first_ts is None: first_ts = ts
        msg   = e.get("message") or {}
        usage = msg.get("usage") or {}
        model = msg.get("model", "unknown")
        i  = usage.get("input_tokens", 0)
        o  = usage.get("output_tokens", 0)
        cc = usage.get("cache_creation_input_tokens", 0)
        rc = usage.get("cache_read_input_tokens", 0)
        p  = _price(model)
        c  = (i*p[0]+o*p[1]+cc*p[2]+rc*p[3]) / 1_000_000
        inp+=i; out+=o; cw+=cc; cr+=rc; cost+=c
        bm = by_model.setdefault(model, [0,0,0,0,0.0])
        bm[0]+=i; bm[1]+=o; bm[2]+=cc; bm[3]+=rc; bm[4]+=c

    return dict(inp=inp, out=out, cw=cw, cr=cr, cost=cost,
                by_model=by_model, first_ts=first_ts)

def _read_stats() -> dict:
    now     = datetime.now(timezone.utc)
    entries = _read_all_entries()

    # ① 오늘(자정 UTC 이후) 데이터 시도
    today_cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d = _aggregate(entries, today_cutoff)

    # ② 오늘 데이터 없으면 → 가장 최근 5시간 윈도우로 폴백
    session_label = "오늘"
    if d["inp"] + d["out"] == 0 and entries:
        last_ts      = entries[-1][0]
        window_start = last_ts - timedelta(hours=5)
        d            = _aggregate(entries, window_start)
        local_date   = last_ts.astimezone().strftime("%m/%d")
        session_label = f"마지막 세션 ({local_date})"

    # ③ 세션 잔여 시간 계산
    mins_remaining = 0
    if d["first_ts"]:
        elapsed        = (now - d["first_ts"]).total_seconds()
        mins_remaining = max(0, int((5*3600 - elapsed) / 60))

    first_ts_iso = d["first_ts"].isoformat() if d["first_ts"] else None
    return dict(inp=d["inp"], out=d["out"], cw=d["cw"], cr=d["cr"],
                cost=d["cost"], by_model=d["by_model"],
                mins=mins_remaining, session_label=session_label,
                first_ts=first_ts_iso)

# ── Main: use cache if files unchanged, else re-read ─────────────────────────
current_mtime = _fingerprint()
cache         = _load_cache()

if cache and cache.get("mtime") == current_mtime:
    d = cache["data"]                   # files unchanged → instant return
else:
    d = _read_stats()
    _save_cache(d, current_mtime)       # persist for next run

# ── Try claude.ai live usage (browser cookies) ────────────────────────────────
# Run at most once per minute to avoid hammering the server
_LIVE_CACHE   = Path.home() / ".claudebar_live.json"
_live_pct     = None
_live_synced  = False

try:
    now_ts = datetime.now().timestamp()
    live_data = json.loads(_LIVE_CACHE.read_text()) if _LIVE_CACHE.exists() else {}
    if now_ts - live_data.get("ts", 0) > 60:   # stale → refresh
        fetched = _fetch_claude_ai_usage()
        if fetched is not None:
            live_data = {"ts": now_ts, "pct": fetched}
            _LIVE_CACHE.write_text(json.dumps(live_data))
    if live_data.get("pct") is not None:
        _live_pct    = live_data["pct"]
        _live_synced = True
except Exception:
    pass

# ── Compute display values ────────────────────────────────────────────────────
inp, out, cw, cr   = d["inp"], d["out"], d["cw"], d["cr"]
cost               = d["cost"]
by_model           = d["by_model"]
mins               = d["mins"]
session_label      = d.get("session_label", "오늘")

limit   = 150_000
total   = inp + out

# Use claude.ai live pct if available, else compute from local JSONL
if _live_pct is not None:
    pct = _live_pct
else:
    pct = round(total / limit * 100, 1)

pct_col = "#32d74b" if pct < 60 else ("#ff9f0a" if pct < 85 else "#ff453a")

h, m   = divmod(mins, 60)
time_s = f"{h}h {m}m" if h > 0 else (f"{m}m" if m > 0 else "—")

filled  = round(pct / 100 * 20)
bar_str = "█" * filled + "░" * (20 - filled)

# ── SwiftBar / xbar output ────────────────────────────────────────────────────
sep        = " · " if mins > 0 else ""
mins_label = f"{mins}m" if mins > 0 else ""
sync_tag   = " ✓" if _live_synced else ""
print(f"☁ {pct:.1f}%{sep}{mins_label} | color={pct_col} size=13")
print("---")
print(f"☁  Claude Code | size=15 color=white bold=true sfimage=cloud.fill")
print("---")

if _live_synced:
    print(f"Token Usage  (claude.ai 동기화{sync_tag}) | size=12 color=white bold=true")
else:
    print(f"Token Usage  ({session_label}) | size=12 color=white bold=true")

print(f"{bar_str}  {pct:.1f}% | size=12 font=Menlo color={pct_col}")

if _live_synced:
    print(f"claude.ai 기준 실시간 사용량 | size=11 color=#aaaaaa")
else:
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

if _live_synced:
    print("🔗 claude.ai에서 동기화됨 | size=11 color=#32d74b")
    print("---")
else:
    print("⚠️ 로컬 데이터 (browser-cookie3 설치 시 동기화) | size=11 color=#ff9f0a")
    print("browser-cookie3 설치: pip3 install browser-cookie3 | size=11 color=#4a9eff bash=/bin/sh param1=-c param2=\"pip3 install browser-cookie3\" terminal=true refresh=true")
    print("---")
print("새로고침 | refresh=true color=#4a9eff")
