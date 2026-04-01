#!/usr/bin/env python3
"""
ClaudeBar — macOS status bar app for real-time Claude token monitoring.

Install deps (macOS only):
    pip install pyobjc

Run:
    python3 claudebar_app.py
"""
import sys, json, threading, time
from datetime import datetime, timezone, date
from pathlib import Path

# ── PyObjC check ─────────────────────────────────────────────────────────────
try:
    import AppKit
    import WebKit
    import objc
    from Foundation import (
        NSObject, NSMakeRect, NSMakeSize, NSBundle,
        NSOperationQueue, NSTimer, NSRunLoop, NSDefaultRunLoopMode,
    )
except ImportError:
    print("PyObjC가 필요합니다:\n  pip install pyobjc\n  python3 claudebar_app.py")
    sys.exit(1)

# ── Pricing (per 1M tokens, USD) ─────────────────────────────────────────────
_PRICING = {
    "claude-opus-4-6":            dict(inp=15.00, out=75.00, cw=18.75, cr=1.50),
    "claude-sonnet-4-6":          dict(inp= 3.00, out=15.00, cw= 3.75, cr=0.30),
    "claude-3-7-sonnet-20250219": dict(inp= 3.00, out=15.00, cw= 3.75, cr=0.30),
    "claude-3-5-sonnet-20241022": dict(inp= 3.00, out=15.00, cw= 3.75, cr=0.30),
    "claude-haiku-4-5":           dict(inp= 0.80, out= 4.00, cw= 1.00, cr=0.08),
    "claude-haiku-4-5-20251001":  dict(inp= 0.80, out= 4.00, cw= 1.00, cr=0.08),
    "claude-3-5-haiku-20241022":  dict(inp= 0.80, out= 4.00, cw= 1.00, cr=0.08),
    "claude-3-opus-20240229":     dict(inp=15.00, out=75.00, cw=18.75, cr=1.50),
    "claude-3-haiku-20240307":    dict(inp= 0.25, out= 1.25, cw= 0.30, cr=0.03),
}
_DEFAULT_PRICE = dict(inp=3.00, out=15.00, cw=3.75, cr=0.30)

def _price(model):
    if model in _PRICING: return _PRICING[model]
    for k, p in _PRICING.items():
        if k in model: return p
    return _DEFAULT_PRICE

def _fmt(n):
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}k"
    return str(n)

# ── JSONL reader ──────────────────────────────────────────────────────────────
def read_stats() -> dict:
    projects = Path.home() / ".claude" / "projects"
    today_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    inp = out = cw = cr = 0
    cost = 0.0
    by_model: dict = {}
    first_ts = None

    if projects.is_dir():
        iso = [
            datetime.fromisoformat,
            lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
        ]
        for f in projects.rglob("*.jsonl"):
            try:
                lines = f.read_text(errors="ignore").splitlines()
            except OSError:
                continue
            for line in lines:
                if not line.strip(): continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("type") != "assistant": continue
                ts_str = e.get("timestamp", "")
                ts = None
                for parser in iso:
                    try: ts = parser(ts_str); break
                    except Exception: pass
                if ts is None or ts < today_utc:
                    continue
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                msg   = e.get("message") or {}
                usage = msg.get("usage") or {}
                model = msg.get("model", "unknown")
                i  = usage.get("input_tokens", 0)
                o  = usage.get("output_tokens", 0)
                cc = usage.get("cache_creation_input_tokens", 0)
                rc = usage.get("cache_read_input_tokens", 0)
                if i == 0 and o == 0: continue
                p = _price(model)
                c = (i*p["inp"] + o*p["out"] + cc*p["cw"] + rc*p["cr"]) / 1_000_000
                inp += i; out += o; cw += cc; cr += rc; cost += c
                bm = by_model.setdefault(model, dict(i=0,o=0,cw=0,cr=0,cost=0.0))
                bm["i"]+=i; bm["o"]+=o; bm["cw"]+=cc; bm["cr"]+=rc; bm["cost"]+=c

    limit = 150_000
    total = inp + out
    pct   = round(total / limit * 100, 1)

    mins_remaining = 0
    if first_ts:
        elapsed   = (datetime.now(timezone.utc) - first_ts).total_seconds()
        remaining = max(0.0, 5 * 3600 - elapsed)
        mins_remaining = int(remaining / 60)

    h, m = divmod(mins_remaining, 60)
    time_str = f"{h}h {m}m" if h > 0 else (f"{m}m" if m > 0 else "—")

    models_rows = ""
    for mdl, v in sorted(by_model.items(), key=lambda x: -(x[1]["i"]+x[1]["o"])):
        short = mdl.replace("claude-","").replace("-20251001","").replace("-20241022","").replace("-20250219","")
        tot = v["i"] + v["o"]
        models_rows += (
            f'<div class="model-row">'
            f'<span class="model-name">{short}</span>'
            f'<span class="model-tok">{_fmt(tot)}</span>'
            f'<span class="model-cost">${v["cost"]:.3f}</span>'
            f'</div>'
        )

    return dict(
        pct=pct, total=_fmt(total), limit=_fmt(limit),
        inp=_fmt(inp), out=_fmt(out), cache=_fmt(cw+cr),
        cost=f"${cost:.3f}", time=time_str, mins=mins_remaining,
        models_rows=models_rows,
    )

# ── Embedded HTML/CSS ─────────────────────────────────────────────────────────
def _build_html(d: dict) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: 340px;
    font-family: -apple-system, "SF Pro Display", "Helvetica Neue", sans-serif;
    background: linear-gradient(160deg, #3a8fd4 0%, #2d7bbf 45%, #2670b0 100%);
    color: #fff;
    user-select: none;
    -webkit-user-select: none;
    overflow: hidden;
  }}
  .divider {{ height: 1px; background: rgba(255,255,255,0.22); }}

  /* Header */
  .header {{
    display: flex; align-items: center; gap: 10px;
    padding: 14px 16px;
  }}
  .hdr-icon  {{ font-size: 20px; }}
  .hdr-title {{ font-size: 17px; font-weight: 700; flex: 1; }}
  .badge {{
    font-size: 12px; font-weight: 500;
    background: rgba(255,255,255,0.16);
    border: 1px solid rgba(255,255,255,0.22);
    padding: 3px 10px; border-radius: 8px;
  }}

  /* Main */
  .main {{ padding: 16px; display: flex; flex-direction: column; gap: 14px; }}
  .row   {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .label {{ font-size: 13px; font-weight: 600; }}
  .nums  {{ font-size: 13px; color: rgba(255,255,255,0.72); }}

  /* Progress */
  .track {{
    height: 8px; background: rgba(255,255,255,0.20);
    border-radius: 999px; overflow: hidden; margin-top: 8px;
  }}
  .fill {{
    height: 100%; border-radius: 999px;
    background: #32d74b;
    transition: width .5s cubic-bezier(.4,0,.2,1);
  }}

  /* Big text */
  .big-pct  {{ font-size: 33px; font-weight: 800; letter-spacing: -1px; line-height: 1; margin-top: 8px; }}
  .big-time {{ font-size: 24px; font-weight: 700; letter-spacing: -.5px; }}
  .window   {{ font-size: 13px; color: rgba(255,255,255,.65); margin-left: 6px; }}

  /* Columns */
  .cols {{ display: flex; }}
  .col  {{ flex: 1; }}
  .col-title {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
  .col-val   {{
    font-size: 16px; font-weight: 600;
    font-family: "SF Mono", Menlo, monospace;
    font-variant-numeric: tabular-nums;
  }}
  .cyan  {{ color: #5ac8fa; }}
  .pink  {{ color: #ff6ec7; }}
  .green {{ color: #32d74b; }}

  /* Models */
  .models-section {{ font-size: 12px; }}
  .models-hdr {{ font-size: 11px; font-weight: 600; opacity: .6; margin-bottom: 5px; letter-spacing: .5px; text-transform: uppercase; }}
  .model-row  {{ display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }}
  .model-name {{ flex: 1; color: rgba(255,255,255,.8); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .model-tok  {{ color: rgba(255,255,255,.6); font-family: "SF Mono", monospace; font-size: 11px; }}
  .model-cost {{ color: #32d74b; font-family: "SF Mono", monospace; font-size: 11px; }}

  /* Footer */
  .footer {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 11px 16px;
  }}
  button {{
    background: none; border: none; cursor: pointer;
    font-family: inherit; font-size: 14px; font-weight: 500;
    padding: 4px 8px; border-radius: 6px;
    transition: background .12s;
  }}
  .btn-refresh {{ color: #4a9eff; }}
  .btn-refresh:hover {{ background: rgba(74,158,255,.15); }}
  .btn-quit    {{ color: rgba(255,255,255,.85); }}
  .btn-quit:hover {{ background: rgba(255,255,255,.1); }}
  .spin {{ display: inline-block; animation: spin 1s linear infinite; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <span class="hdr-icon">☁️</span>
  <span class="hdr-title">Claude Code</span>
  <span class="badge">Max 5x</span>
</div>

<div class="divider"></div>

<!-- Main -->
<div class="main">

  <!-- Token usage -->
  <div>
    <div class="row">
      <span class="label">Token Usage</span>
      <span class="nums" id="usageNums">{d['total']} / {d['limit']}</span>
    </div>
    <div class="track"><div class="fill" id="fill" style="width:{d['pct']}%"></div></div>
    <div class="big-pct green" id="bigPct">{d['pct']}% used</div>
  </div>

  <!-- Session time -->
  <div>
    <div class="label" style="margin-bottom:5px">Session Time Remaining</div>
    <span class="big-time" id="bigTime">{d['time']}</span>
    <span class="window">of 5h window</span>
  </div>

  <!-- Three columns -->
  <div class="cols">
    <div class="col">
      <div class="col-title">Input</div>
      <div class="col-val cyan"  id="colInp">{d['inp']}</div>
    </div>
    <div class="col">
      <div class="col-title">Output</div>
      <div class="col-val pink"  id="colOut">{d['out']}</div>
    </div>
    <div class="col">
      <div class="col-title">Cache</div>
      <div class="col-val green" id="colCache">{d['cache']}</div>
    </div>
  </div>

  <!-- Model breakdown -->
  {'<div class="models-section"><div class="models-hdr">모델별</div>' + d['models_rows'] + '</div>' if d['models_rows'] else ''}

</div><!-- /main -->

<div class="divider"></div>

<!-- Footer -->
<div class="footer">
  <button class="btn-refresh" id="refreshBtn" onclick="onRefresh()">Refresh</button>
  <button class="btn-quit" onclick="onQuit()">Quit</button>
</div>

<script>
function _pctColor(p) {{
  return p < 60 ? '#32d74b' : p < 85 ? '#ff9f0a' : '#ff453a';
}}

// Called from Python after each refresh
function updateData(d) {{
  const col = _pctColor(d.pct);
  document.getElementById('fill').style.width      = d.pct + '%';
  document.getElementById('fill').style.background = col;
  document.getElementById('bigPct').textContent    = d.pct + '% used';
  document.getElementById('bigPct').style.color    = col;
  document.getElementById('usageNums').textContent = d.total + ' / ' + d.limit;
  document.getElementById('bigTime').textContent   = d.time;
  document.getElementById('colInp').textContent    = d.inp;
  document.getElementById('colOut').textContent    = d.out;
  document.getElementById('colCache').textContent  = d.cache;
  document.getElementById('refreshBtn').disabled   = false;
  document.getElementById('refreshBtn').innerHTML  = 'Refresh';
}}

function onRefresh() {{
  document.getElementById('refreshBtn').disabled  = true;
  document.getElementById('refreshBtn').innerHTML = '<span class=spin>↻</span>';
  window.webkit.messageHandlers.claudebar.postMessage('refresh');
}}

function onQuit() {{
  window.webkit.messageHandlers.claudebar.postMessage('quit');
}}

// Countdown (visual only)
let _mins = {d['mins']};
setInterval(() => {{
  if (_mins <= 0) return;
  _mins--;
  const h = Math.floor(_mins/60), m = _mins%60;
  document.getElementById('bigTime').textContent = h > 0 ? h+'h '+m+'m' : (_mins > 0 ? _mins+'m' : '—');
}}, 60000);
</script>
</body>
</html>"""

# ── AppDelegate ───────────────────────────────────────────────────────────────
class ClaudeBarDelegate(NSObject):

    # PyObjC instance variables
    statusItem = objc.ivar()
    popover    = objc.ivar()
    webView    = objc.ivar()

    def applicationDidFinishLaunching_(self, _notif):
        AppKit.NSApp.setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory   # hide Dock icon
        )
        self._setup_status_item()
        self._setup_popover()
        self._start_polling()
        self._refresh()   # initial data load

    # ── Status bar ────────────────────────────────────────────────────────────
    def _setup_status_item(self):
        self.statusItem = (
            AppKit.NSStatusBar.systemStatusBar()
                .statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        )
        btn = self.statusItem.button()
        btn.setTitle_("☁ …")
        btn.setTarget_(self)
        btn.setAction_(objc.selector(
            self.handleClick_,
            selector=b"handleClick:",
            signature=b"v@:@",
        ))

    def _sync_button(self, d: dict):
        pct  = d["pct"]
        mins = d["mins"]
        lbl  = f"☁ {pct}%·{mins}m" if mins > 0 else f"☁ {pct}%"

        # Colour the percentage
        pct_color: AppKit.NSColor = (
            AppKit.NSColor.systemGreenColor()  if pct < 60 else
            AppKit.NSColor.systemOrangeColor() if pct < 85 else
            AppKit.NSColor.systemRedColor()
        )
        attrs_pct  = {AppKit.NSForegroundColorAttributeName: pct_color,
                      AppKit.NSFontAttributeName: AppKit.NSFont.menuBarFontOfSize_(13)}
        attrs_rest = {AppKit.NSForegroundColorAttributeName: AppKit.NSColor.labelColor(),
                      AppKit.NSFontAttributeName: AppKit.NSFont.menuBarFontOfSize_(13)}

        astr = AppKit.NSMutableAttributedString.alloc().initWithString_(lbl)
        full = AppKit.NSMakeRange(0, len(lbl))
        astr.addAttributes_range_(attrs_rest, full)
        pct_str = f"{pct}%"
        idx = lbl.find(pct_str)
        if idx >= 0:
            astr.addAttributes_range_(attrs_pct,
                                      AppKit.NSMakeRange(idx, len(pct_str)))
        self.statusItem.button().setAttributedTitle_(astr)

    # ── Popover ───────────────────────────────────────────────────────────────
    def _setup_popover(self):
        d = read_stats()
        html = _build_html(d)

        cfg = WebKit.WKWebViewConfiguration.alloc().init()
        # Register message handler for JS → Python bridge
        cfg.userContentController().addScriptMessageHandler_name_(self, "claudebar")

        frame = NSMakeRect(0, 0, 340, 0)   # height auto
        self.webView = (
            WebKit.WKWebView.alloc()
                .initWithFrame_configuration_(frame, cfg)
        )
        self.webView.setFrame_(NSMakeRect(0, 0, 340, 430))
        self.webView.loadHTMLString_baseURL_(html, None)

        vc = AppKit.NSViewController.alloc().init()
        vc.setView_(self.webView)

        self.popover = AppKit.NSPopover.alloc().init()
        self.popover.setContentSize_(NSMakeSize(340, 430))
        self.popover.setContentViewController_(vc)
        self.popover.setBehavior_(AppKit.NSPopoverBehaviorTransient)

    # WKScriptMessageHandler protocol
    def userContentController_didReceiveScriptMessage_(self, _ctrl, msg):
        body = msg.body()
        if body == "refresh":
            threading.Thread(target=self._refresh, daemon=True).start()
        elif body == "quit":
            AppKit.NSApp.terminate_(None)

    # ── Click handler ─────────────────────────────────────────────────────────
    def handleClick_(self, sender):
        if self.popover.isShown():
            self.popover.performClose_(sender)
        else:
            btn = self.statusItem.button()
            self.popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn,
                AppKit.NSRectEdgeMinY,   # arrow points up → popover drops down
            )
            AppKit.NSApp.activateIgnoringOtherApps_(True)

    # ── Polling ───────────────────────────────────────────────────────────────
    def _start_polling(self):
        def _loop():
            while True:
                time.sleep(10)
                self._refresh()
        threading.Thread(target=_loop, daemon=True).start()

    def _refresh(self):
        d = read_stats()
        NSOperationQueue.mainQueue().addOperationWithBlock_(
            lambda: self._apply(d)
        )

    def _apply(self, d: dict):
        self._sync_button(d)
        js = (
            f"updateData({{"
            f"pct:{d['pct']},total:'{d['total']}',limit:'{d['limit']}',"
            f"inp:'{d['inp']}',out:'{d['out']}',cache:'{d['cache']}',"
            f"time:'{d['time']}',mins:{d['mins']}"
            f"}});"
        )
        self.webView.evaluateJavaScript_completionHandler_(js, None)

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app      = AppKit.NSApplication.sharedApplication()
    delegate = ClaudeBarDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
