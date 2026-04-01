"""ClaudeBar — macOS status-bar app for real-time Claude token monitoring."""
import threading
from datetime import date
from pathlib import Path

import rumps

from .config import DISPLAY_BOTH, DISPLAY_COST, DISPLAY_TOKENS, Config
from .models import UsageStats, format_cost, format_tokens, shorten_model_name
from .reader import ClaudeReader

# ── watchdog is optional; without it we fall back to timer-only polling ──────
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer as WatchdogObserver

    _WATCHDOG = True
except ImportError:
    _WATCHDOG = False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _title_for_stats(stats: UsageStats, mode: str) -> str:
    tok = format_tokens(stats.total_tokens)
    cost = format_cost(stats.total_cost)
    if mode == DISPLAY_COST:
        return f"⚡ {cost}"
    if mode == DISPLAY_BOTH:
        return f"⚡ {tok}  {cost}"
    return f"⚡ {tok}"


# ─────────────────────────────────────────────────────────────────────────────
# Watchdog handler (real-time JSONL monitoring)
# ─────────────────────────────────────────────────────────────────────────────

if _WATCHDOG:
    class _ClaudeFileHandler(FileSystemEventHandler):
        def __init__(self, refresh_cb):
            self._refresh = refresh_cb
            self._timer: threading.Timer | None = None
            self._lock = threading.Lock()

        def on_modified(self, event):
            if not event.is_directory and event.src_path.endswith(".jsonl"):
                self._debounce()

        def on_created(self, event):
            if not event.is_directory and event.src_path.endswith(".jsonl"):
                self._debounce()

        def _debounce(self):
            """Coalesce rapid filesystem events into one refresh."""
            with self._lock:
                if self._timer:
                    self._timer.cancel()
                self._timer = threading.Timer(0.8, self._refresh)
                self._timer.daemon = True
                self._timer.start()


# ─────────────────────────────────────────────────────────────────────────────
# Main app
# ─────────────────────────────────────────────────────────────────────────────

class ClaudeBarApp(rumps.App):
    def __init__(self):
        super().__init__("⚡ …", quit_button=None)
        self.config = Config.load()
        self.reader = ClaudeReader()
        self._lock = threading.Lock()
        self._observer = None

        self._build_menu()
        self._start_watcher()

        # Fallback / backup timer so display stays fresh regardless of watchdog
        self._timer = rumps.Timer(self._on_timer, self.config.refresh_interval)
        self._timer.start()

        # Initial data load
        threading.Thread(target=self._do_refresh, daemon=True).start()

    # ── Menu construction ─────────────────────────────────────────────────────

    def _build_menu(self):
        # ── Today ──
        self._today_hdr   = rumps.MenuItem("— 오늘 사용량 —",   enabled=False)
        self._today_in    = rumps.MenuItem("  입력 토큰:  —",    enabled=False)
        self._today_out   = rumps.MenuItem("  출력 토큰:  —",    enabled=False)
        self._today_cw    = rumps.MenuItem("  캐시 생성:  —",    enabled=False)
        self._today_cr    = rumps.MenuItem("  캐시 읽기:  —",    enabled=False)
        self._today_cost  = rumps.MenuItem("  예상 비용:  —",    enabled=False)

        # ── Month ──
        self._month_hdr   = rumps.MenuItem("— 이번 달 사용량 —", enabled=False)
        self._month_total = rumps.MenuItem("  총 토큰:    —",    enabled=False)
        self._month_cost  = rumps.MenuItem("  총 비용:    —",    enabled=False)

        # ── Model breakdown submenu ──
        self._models_menu = rumps.MenuItem("모델별 사용량 (오늘)")

        # ── Display-mode submenu ──
        self._disp_tokens = rumps.MenuItem(
            "✓ 토큰 수" if self.config.display_mode == DISPLAY_TOKENS else "  토큰 수",
            callback=self._set_tokens,
        )
        self._disp_cost = rumps.MenuItem(
            "✓ 비용" if self.config.display_mode == DISPLAY_COST else "  비용",
            callback=self._set_cost,
        )
        self._disp_both = rumps.MenuItem(
            "✓ 토큰+비용" if self.config.display_mode == DISPLAY_BOTH else "  토큰+비용",
            callback=self._set_both,
        )
        settings_menu = rumps.MenuItem("표시 방식")
        settings_menu.update([self._disp_tokens, self._disp_cost, self._disp_both])

        self._last_updated = rumps.MenuItem("  —", enabled=False)

        self.menu = [
            self._today_hdr,
            self._today_in,
            self._today_out,
            self._today_cw,
            self._today_cr,
            self._today_cost,
            rumps.separator,
            self._month_hdr,
            self._month_total,
            self._month_cost,
            rumps.separator,
            self._models_menu,
            rumps.separator,
            settings_menu,
            rumps.separator,
            rumps.MenuItem("새로고침", callback=self._manual_refresh),
            self._last_updated,
            rumps.separator,
            rumps.MenuItem("종료", callback=rumps.quit_application),
        ]

    # ── File watcher ──────────────────────────────────────────────────────────

    def _start_watcher(self):
        if not _WATCHDOG:
            return
        projects_dir = self.reader.projects_dir
        if not projects_dir.is_dir():
            return
        handler = _ClaudeFileHandler(self._do_refresh)
        self._observer = WatchdogObserver()
        self._observer.schedule(handler, str(projects_dir), recursive=True)
        self._observer.start()

    # ── Refresh logic ─────────────────────────────────────────────────────────

    def _on_timer(self, _sender):
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _manual_refresh(self, _sender):
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        today = date.today()
        today_stats = self.reader.get_stats_for_date(today)
        month_stats = self.reader.get_stats_for_month(today.year, today.month)
        # rumps requires UI updates on the main thread — use a timer with 0 delay
        rumps.Timer(lambda _: self._apply_update(today_stats, month_stats), 0).start()

    def _apply_update(self, today: UsageStats, month: UsageStats):
        with self._lock:
            self.title = _title_for_stats(today, self.config.display_mode)

            # Today
            self._today_in.title   = f"  입력 토큰:  {today.input_tokens:,}"
            self._today_out.title  = f"  출력 토큰:  {today.output_tokens:,}"
            self._today_cw.title   = f"  캐시 생성:  {today.cache_creation_tokens:,}"
            self._today_cr.title   = f"  캐시 읽기:  {today.cache_read_tokens:,}"
            self._today_cost.title = f"  예상 비용:  {format_cost(today.total_cost)}"

            # Month
            self._month_total.title = f"  총 토큰:    {format_tokens(month.total_tokens)}"
            self._month_cost.title  = f"  총 비용:    {format_cost(month.total_cost)}"

            # Model breakdown — rebuild submenu
            for key in list(self._models_menu):
                del self._models_menu[key]

            if today.by_model:
                sorted_models = sorted(
                    today.by_model.items(),
                    key=lambda kv: kv[1].total_tokens,
                    reverse=True,
                )
                for model_id, usage in sorted_models:
                    label = (
                        f"  {shorten_model_name(model_id):<28} "
                        f"{format_tokens(usage.total_tokens):>7}  "
                        f"{format_cost(usage.cost)}"
                    )
                    self._models_menu[model_id] = rumps.MenuItem(label, enabled=False)
            else:
                self._models_menu["none"] = rumps.MenuItem(
                    "  (사용 내역 없음)", enabled=False
                )

            # Timestamp
            from datetime import datetime
            self._last_updated.title = (
                "  최종 업데이트: "
                + datetime.now().strftime("%H:%M:%S")
            )

    # ── Display-mode callbacks ────────────────────────────────────────────────

    def _set_display_mode(self, mode: str):
        self.config.display_mode = mode
        self.config.save()
        self._disp_tokens.title = ("✓ 토큰 수"   if mode == DISPLAY_TOKENS else "  토큰 수")
        self._disp_cost.title   = ("✓ 비용"      if mode == DISPLAY_COST   else "  비용")
        self._disp_both.title   = ("✓ 토큰+비용" if mode == DISPLAY_BOTH   else "  토큰+비용")
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _set_tokens(self, _): self._set_display_mode(DISPLAY_TOKENS)
    def _set_cost(self, _):   self._set_display_mode(DISPLAY_COST)
    def _set_both(self, _):   self._set_display_mode(DISPLAY_BOTH)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def __del__(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()


# ─────────────────────────────────────────────────────────────────────────────

def run():
    ClaudeBarApp().run()
