"""Read and parse Claude Code JSONL session files."""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .models import UsageStats


_CLAUDE_DIR = Path.home() / ".claude"
_PROJECTS_DIR = _CLAUDE_DIR / "projects"


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _aggregate_from_jsonl(
    path: Path,
    stats: UsageStats,
    date_filter: Optional[Callable[[datetime], bool]],
) -> None:
    """Append usage entries from *path* into *stats*, respecting *date_filter*."""
    try:
        with open(path, encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "assistant":
                    continue

                if date_filter is not None:
                    ts = _parse_timestamp(entry.get("timestamp", ""))
                    if ts is None or not date_filter(ts):
                        continue

                message = entry.get("message") or {}
                usage = message.get("usage") or {}
                model = message.get("model") or "unknown"

                input_tokens          = int(usage.get("input_tokens", 0))
                output_tokens         = int(usage.get("output_tokens", 0))
                cache_creation_tokens = int(usage.get("cache_creation_input_tokens", 0))
                cache_read_tokens     = int(usage.get("cache_read_input_tokens", 0))

                if input_tokens == 0 and output_tokens == 0:
                    continue

                stats.add_usage(
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    cache_read_tokens=cache_read_tokens,
                )
    except (OSError, UnicodeDecodeError):
        pass


def _iter_jsonl_files(base_dir: Path):
    """Yield all *.jsonl files under *base_dir* (including subdirectories)."""
    if not base_dir.is_dir():
        return
    yield from base_dir.rglob("*.jsonl")


class ClaudeReader:
    """Reads token usage from Claude Code's local project JSONL files."""

    def __init__(self, projects_dir: Optional[Path] = None):
        self.projects_dir = projects_dir or _PROJECTS_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_stats_for_date(self, target: date) -> UsageStats:
        """Return aggregated stats for a single calendar date (local time)."""
        def _filter(ts: datetime) -> bool:
            local_date = ts.astimezone().date()
            return local_date == target

        return self._scan(_filter)

    def get_stats_for_month(self, year: int, month: int) -> UsageStats:
        """Return aggregated stats for an entire calendar month (local time)."""
        def _filter(ts: datetime) -> bool:
            local = ts.astimezone()
            return local.year == year and local.month == month

        return self._scan(_filter)

    def get_stats_all_time(self) -> UsageStats:
        return self._scan(None)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan(self, date_filter: Optional[Callable[[datetime], bool]]) -> UsageStats:
        stats = UsageStats()
        for jsonl_file in _iter_jsonl_files(self.projects_dir):
            _aggregate_from_jsonl(jsonl_file, stats, date_filter)
        return stats
