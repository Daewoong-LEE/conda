#!/usr/bin/env python3
"""
ClaudeBar — macOS status bar app (NSPopover + WKWebView)

Install:  pip install pyobjc
Run:      python3 claudebar_app.py
"""
import sys, json, re, threading, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import AppKit, WebKit, objc
    from Foundation import (NSObject, NSMakeRect, NSMakeSize,
                             NSOperationQueue)
except ImportError:
    print("PyObjC 필요:  pip install pyobjc")
    sys.exit(1)

# ── Pricing (per 1M tokens) ───────────────────────────────────────────────────
_PRICING = {
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
    if m in _PRICING: return _PRICING[m]
    for k, p in _PRICING.items():
        if k in m: return p
    return _DP

def _fmt(n):        # compact  2.4k / 23.2M
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}k"
    return str(n)

def _fmt_exact(n):  # 51,881
    return f"{n:,}"

# ── claude.ai live usage (browser cookies) ────────────────────────────────────
_LIVE_CACHE = Path.home() / ".claudebar_live.json"

def _fetch_claude_ai_usage():
    try:
        import browser_cookie3
        cookies = None
        for loader in [
            lambda: browser_cookie3.chrome(domain_name=".claude.ai"),
            lambda: browser_cookie3.safari(domain_name=".claude.ai"),
            lambda: browser_cookie3.firefox(domain_name=".claude.ai"),
        ]:
            try:
                jar = loader()
                if jar:
                    cookies = jar
                    break
            except Exception:
                continue
        if not cookies:
            return None
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
                              "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(1))

        def _find(obj, depth=0):
            if depth > 10: return None
            if isinstance(obj, dict):
                for key in obj:
                    lkey = key.lower()
                    if "percent" in lkey or "usage" in lkey:
                        val = obj[key]
                        if isinstance(val, (int, float)) and 0 <= val <= 100:
                            return float(val)
                        if isinstance(val, str):
                            try:
                                f = float(val.strip("%"))
                                if 0 <= f <= 100: return f
                            except ValueError:
                                pass
                for val in obj.values():
                    r = _find(val, depth + 1)
                    if r is not None: return r
            elif isinstance(obj, list):
                for item in obj:
                    r = _find(item, depth + 1)
                    if r is not None: return r
            return None

        return _find(data)
    except ImportError:
        return None
    except Exception:
        return None

def _get_live_pct():
    """Return (pct, synced). Caches result for 60s."""
    try:
        now_ts = datetime.now().timestamp()
        live = json.loads(_LIVE_CACHE.read_text()) if _LIVE_CACHE.exists() else {}
        if now_ts - live.get("ts", 0) > 60:
            fetched = _fetch_claude_ai_usage()
            if fetched is not None:
                live = {"ts": now_ts, "pct": fetched}
                _LIVE_CACHE.write_text(json.dumps(live))
        if live.get("pct") is not None:
            return live["pct"], True
    except Exception:
        pass
    return None, False

# ── JSONL reader ──────────────────────────────────────────────────────────────
_PROJECTS = Path.home() / ".claude" / "projects"

def _parse_ts(s):
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except: return None

def _all_entries():
    entries = []
    if not _PROJECTS.is_dir(): return entries
    for f in _PROJECTS.rglob("*.jsonl"):
        try: lines = f.read_text(errors="ignore").splitlines()
        except: continue
        for line in lines:
            if not line.strip(): continue
            try: e = json.loads(line)
            except: continue
            if e.get("type") != "assistant": continue
            ts = _parse_ts(e.get("timestamp", ""))
            if not ts: continue
            msg = e.get("message") or {}
            u   = msg.get("usage") or {}
            if u.get("input_tokens",0) == 0 and u.get("output_tokens",0) == 0: continue
            entries.append((ts, e))
    entries.sort(key=lambda x: x[0])
    return entries

def _aggregate(entries, cutoff):
    inp = out = cw = cr = 0; cost = 0.0
    by_model = {}; first_ts = None
    for ts, e in entries:
        if ts < cutoff: continue
        if first_ts is None: first_ts = ts
        msg = e.get("message") or {}
        u   = msg.get("usage") or {}
        mdl = msg.get("model", "unknown")
        i, o, cc, rc = (u.get("input_tokens",0), u.get("output_tokens",0),
                        u.get("cache_creation_input_tokens",0),
                        u.get("cache_read_input_tokens",0))
        p = _price(mdl)
        c = (i*p[0]+o*p[1]+cc*p[2]+rc*p[3]) / 1_000_000
        inp+=i; out+=o; cw+=cc; cr+=rc; cost+=c
        bm = by_model.setdefault(mdl, [0,0,0,0,0.0])
        bm[0]+=i; bm[1]+=o; bm[2]+=cc; bm[3]+=rc; bm[4]+=c
    return dict(inp=inp, out=out, cw=cw, cr=cr, cost=cost,
                by_model=by_model, first_ts=first_ts)

def read_stats():
    now     = datetime.now(timezone.utc)
    entries = _all_entries()

    # 1) 오늘 데이터 우선
    today_cut = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d = _aggregate(entries, today_cut)

    # 2) 오늘 데이터 없으면 → 가장 최근 5h 윈도우
    if d["inp"] + d["out"] == 0 and entries:
        last_ts = entries[-1][0]
        d = _aggregate(entries, last_ts - timedelta(hours=5))

    # 세션 잔여 시간
    mins = 0
    if d["first_ts"]:
        mins = max(0, int((5*3600 - (now - d["first_ts"]).total_seconds()) / 60))

    limit = 150_000
    total = d["inp"] + d["out"]

    # claude.ai 실시간 동기화 시도
    live_pct, synced = _get_live_pct()
    pct = live_pct if live_pct is not None else round(total / limit * 100, 1)

    h, m  = divmod(mins, 60)
    time_str = f"{h}h {m}m" if h > 0 else (f"{m}m" if m > 0 else "—")

    models_rows = ""
    for mdl, v in sorted(d["by_model"].items(), key=lambda x: -(x[1][0]+x[1][1])):
        short = (mdl.replace("claude-","")
                    .replace("-20251001","").replace("-20241022","")
                    .replace("-20250219","").replace("-20240229",""))
        models_rows += (
            f'<div class="model-row">'
            f'<span class="model-name">{short}</span>'
            f'<span class="model-tok">{_fmt(v[0]+v[1])}</span>'
            f'<span class="model-cost">${v[4]:.3f}</span>'
            f'</div>'
        )

    return dict(
        pct=pct,
        synced=synced,
        total_exact=_fmt_exact(total),
        limit_exact=_fmt_exact(limit),
        inp=_fmt(d["inp"]), out=_fmt(d["out"]), cache=_fmt(d["cw"]+d["cr"]),
        cost=f"${d['cost']:.3f}",
        time=time_str, mins=mins,
        models_rows=models_rows,
    )

# ── HTML ──────────────────────────────────────────────────────────────────────
def _build_html(d):
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{
  width:340px;
  font-family:-apple-system,"SF Pro Display","Helvetica Neue",sans-serif;
  background:linear-gradient(170deg,#3d90d8 0%,#2f7dc4 40%,#2570b5 100%);
  color:#fff;user-select:none;-webkit-user-select:none;overflow:hidden;
}}
.divider{{height:1px;background:rgba(255,255,255,.2)}}

/* Header */
.header{{display:flex;align-items:center;gap:10px;padding:15px 16px}}
.hdr-icon{{font-size:22px}}
.hdr-title{{font-size:18px;font-weight:700;flex:1}}
.badge{{
  font-size:13px;font-weight:500;color:rgba(255,255,255,.9);
  background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);
  padding:4px 12px;border-radius:9px
}}

/* Main */
.main{{padding:18px 16px;display:flex;flex-direction:column;gap:16px}}
.row{{display:flex;justify-content:space-between;align-items:baseline}}
.label{{font-size:14px;font-weight:600;color:rgba(255,255,255,.9)}}
.nums{{font-size:14px;color:rgba(255,255,255,.75)}}

/* Progress bar */
.track{{height:10px;background:rgba(255,255,255,.2);border-radius:999px;overflow:hidden;margin-top:10px}}
.fill{{height:100%;border-radius:999px;background:#32d74b;transition:width .5s cubic-bezier(.4,0,.2,1)}}

/* Big % */
.big-pct{{font-size:38px;font-weight:800;letter-spacing:-1.5px;line-height:1;margin-top:10px;color:#32d74b}}

/* Session time */
.time-row{{display:flex;align-items:baseline;gap:8px}}
.big-time{{font-size:28px;font-weight:700;letter-spacing:-.5px}}
.window{{font-size:15px;color:rgba(255,255,255,.6)}}

/* Three columns */
.cols{{display:flex}}
.col{{flex:1}}
.col-title{{font-size:14px;font-weight:600;margin-bottom:6px}}
.col-val{{font-size:18px;font-weight:600;font-family:"SF Mono",Menlo,monospace;font-variant-numeric:tabular-nums}}
.cyan{{color:#5ac8fa}}.pink{{color:#ff6ec7}}.green{{color:#32d74b}}

/* Models */
.models-hdr{{font-size:11px;font-weight:600;opacity:.55;letter-spacing:.5px;text-transform:uppercase;margin-bottom:5px}}
.model-row{{display:flex;gap:6px;margin-bottom:3px}}
.model-name{{flex:1;color:rgba(255,255,255,.8);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.model-tok{{color:rgba(255,255,255,.55);font-family:"SF Mono",monospace;font-size:11px}}
.model-cost{{color:#32d74b;font-family:"SF Mono",monospace;font-size:11px}}

/* Footer */
.footer{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px}}
button{{background:none;border:none;cursor:pointer;font-family:inherit;font-size:15px;font-weight:500;padding:4px 8px;border-radius:7px;transition:background .12s}}
.btn-r{{color:#4a9eff}}.btn-r:hover{{background:rgba(74,158,255,.15)}}
.btn-q{{color:rgba(255,255,255,.85)}}.btn-q:hover{{background:rgba(255,255,255,.1)}}
.spin{{display:inline-block;animation:spin 1s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body>

<div class="header">
  <span class="hdr-icon">☁️</span>
  <span class="hdr-title">Claude Code</span>
  <span class="badge" id="badge">{'claude.ai ✓' if d['synced'] else 'Local'}</span>
</div>
<div class="divider"></div>
<div class="main">

  <div>
    <div class="row">
      <span class="label">Token Usage</span>
      <span class="nums" id="nums">{d['total_exact']} / {d['limit_exact']}</span>
    </div>
    <div class="track"><div class="fill" id="fill" style="width:{d['pct']}%"></div></div>
    <div class="big-pct" id="bigPct" style="color:{('#32d74b' if d['pct']<60 else '#ff9f0a' if d['pct']<85 else '#ff453a')}">{d['pct']}% used</div>
  </div>

  <div>
    <div class="label" style="margin-bottom:8px">Session Time Remaining</div>
    <div class="time-row">
      <span class="big-time" id="bigTime">{d['time']}</span>
      <span class="window">of 5h window</span>
    </div>
  </div>

  <div class="cols">
    <div class="col"><div class="col-title">Input</div><div class="col-val cyan"  id="colI">{d['inp']}</div></div>
    <div class="col"><div class="col-title">Output</div><div class="col-val pink" id="colO">{d['out']}</div></div>
    <div class="col"><div class="col-title">Cache</div><div class="col-val green" id="colC">{d['cache']}</div></div>
  </div>

  {'<div><div class="models-hdr">모델별</div>' + d['models_rows'] + '</div>' if d['models_rows'] else ''}

</div>
<div class="divider"></div>
<div class="footer">
  <button class="btn-r" id="btnR" onclick="onRefresh()">Refresh</button>
  <button class="btn-q" onclick="onQuit()">Quit</button>
</div>

<script>
function _col(p){{return p<60?'#32d74b':p<85?'#ff9f0a':'#ff453a'}}
function updateData(d){{
  const c=_col(d.pct);
  document.getElementById('fill').style.width=d.pct+'%';
  document.getElementById('fill').style.background=c;
  document.getElementById('bigPct').textContent=d.pct+'% used';
  document.getElementById('bigPct').style.color=c;
  document.getElementById('nums').textContent=d.total+' / '+d.limit;
  document.getElementById('bigTime').textContent=d.time;
  document.getElementById('colI').textContent=d.inp;
  document.getElementById('colO').textContent=d.out;
  document.getElementById('colC').textContent=d.cache;
  document.getElementById('badge').textContent=d.synced?'claude.ai ✓':'Local';
  document.getElementById('btnR').disabled=false;
  document.getElementById('btnR').innerHTML='Refresh';
}}
function onRefresh(){{
  document.getElementById('btnR').disabled=true;
  document.getElementById('btnR').innerHTML='<span class=spin>↻</span>';
  window.webkit.messageHandlers.cb.postMessage('refresh');
}}
function onQuit(){{window.webkit.messageHandlers.cb.postMessage('quit')}}
let _m={d['mins']};
setInterval(()=>{{
  if(_m<=0)return;_m--;
  const h=Math.floor(_m/60),m=_m%60;
  document.getElementById('bigTime').textContent=h>0?h+'h '+m+'m':(_m>0?_m+'m':'—');
}},60000);
</script></body></html>"""

# ── AppDelegate ───────────────────────────────────────────────────────────────
class AppDelegate(NSObject):
    statusItem = objc.ivar()
    popover    = objc.ivar()
    webView    = objc.ivar()

    def applicationDidFinishLaunching_(self, _):
        AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        self._setup_bar()
        self._setup_popover()
        threading.Thread(target=self._poll, daemon=True).start()
        self._refresh()

    @objc.python_method
    def _setup_bar(self):
        self.statusItem = (AppKit.NSStatusBar.systemStatusBar()
                           .statusItemWithLength_(AppKit.NSVariableStatusItemLength))
        btn = self.statusItem.button()
        btn.setTitle_("☁ …")
        btn.setTarget_(self)
        btn.setAction_(objc.selector(self.click_, selector=b"click:",
                                     signature=b"v@:@"))

    @objc.python_method
    def _setup_popover(self):
        d   = read_stats()
        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        cfg.userContentController().addScriptMessageHandler_name_(self, "cb")
        self.webView = (WebKit.WKWebView.alloc()
                        .initWithFrame_configuration_(NSMakeRect(0,0,340,490), cfg))
        self.webView.loadHTMLString_baseURL_(_build_html(d), None)
        vc = AppKit.NSViewController.alloc().init()
        vc.setView_(self.webView)
        self.popover = AppKit.NSPopover.alloc().init()
        self.popover.setContentSize_(NSMakeSize(340, 490))
        self.popover.setContentViewController_(vc)
        self.popover.setBehavior_(AppKit.NSPopoverBehaviorTransient)

    def click_(self, sender):
        if self.popover.isShown():
            self.popover.performClose_(sender)
        else:
            btn = self.statusItem.button()
            self.popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn, AppKit.NSRectEdgeMinY)
            AppKit.NSApp.activateIgnoringOtherApps_(True)

    def userContentController_didReceiveScriptMessage_(self, _, msg):
        if msg.body() == "refresh":
            threading.Thread(target=self._refresh, daemon=True).start()
        elif msg.body() == "quit":
            AppKit.NSApp.terminate_(None)

    @objc.python_method
    def _poll(self):
        while True:
            time.sleep(2)
            self._refresh()

    @objc.python_method
    def _refresh(self):
        d = read_stats()

        # Inline closure — avoids method-with-argument ObjC registration issue
        def _update():
            pct  = d["pct"]
            mins = d["mins"]
            col  = (AppKit.NSColor.systemGreenColor()  if pct < 60 else
                    AppKit.NSColor.systemOrangeColor() if pct < 85 else
                    AppKit.NSColor.systemRedColor())
            lbl  = f"☁ {pct}%{'  ·  '+str(mins)+'m' if mins else ''}"
            astr = AppKit.NSMutableAttributedString.alloc().initWithString_(lbl)
            fn   = AppKit.NSFont.menuBarFontOfSize_(13)
            astr.addAttribute_value_range_(
                AppKit.NSForegroundColorAttributeName,
                AppKit.NSColor.labelColor(),
                AppKit.NSMakeRange(0, len(lbl)))
            astr.addAttribute_value_range_(
                AppKit.NSFontAttributeName, fn,
                AppKit.NSMakeRange(0, len(lbl)))
            pct_s = f"{pct}%"
            idx   = lbl.find(pct_s)
            if idx >= 0:
                astr.addAttribute_value_range_(
                    AppKit.NSForegroundColorAttributeName, col,
                    AppKit.NSMakeRange(idx, len(pct_s)))
            self.statusItem.button().setAttributedTitle_(astr)

            synced_js = "true" if d["synced"] else "false"
            js = (f"updateData({{"
                  f"pct:{pct},total:'{d['total_exact']}',limit:'{d['limit_exact']}',"
                  f"inp:'{d['inp']}',out:'{d['out']}',cache:'{d['cache']}',"
                  f"time:'{d['time']}',mins:{mins},synced:{synced_js}}});")
            self.webView.evaluateJavaScript_completionHandler_(js, None)

        NSOperationQueue.mainQueue().addOperationWithBlock_(_update)

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(
        AppKit.NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    AppKit.NSApplication.sharedApplication().setDelegate_(delegate)
    AppKit.NSApplication.sharedApplication().run()
