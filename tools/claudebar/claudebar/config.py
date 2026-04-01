"""Persistent configuration for ClaudeBar."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".claudebar"
CONFIG_FILE = CONFIG_DIR / "config.json"

DISPLAY_TOKENS = "tokens"
DISPLAY_COST = "cost"
DISPLAY_BOTH = "both"


@dataclass
class Config:
    display_mode: str = DISPLAY_TOKENS   # "tokens" | "cost" | "both"
    refresh_interval: int = 10           # seconds (timer fallback)
    show_cache_details: bool = True

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, encoding="utf-8") as fh:
                    raw = json.load(fh)
                valid = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
                return cls(**valid)
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
