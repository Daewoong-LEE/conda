"""Data models and pricing for Claude token tracking."""
from dataclasses import dataclass, field
from typing import Dict

# Price per 1M tokens (USD) — updated for Claude 4.x / 3.x series
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Claude 4
    "claude-opus-4-6":              {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "claude-sonnet-4-6":            {"input":  3.00, "output": 15.00, "cache_write":  3.75, "cache_read": 0.30},
    # Claude 3.7 / 3.5 / 3
    "claude-3-7-sonnet-20250219":   {"input":  3.00, "output": 15.00, "cache_write":  3.75, "cache_read": 0.30},
    "claude-3-5-sonnet-20241022":   {"input":  3.00, "output": 15.00, "cache_write":  3.75, "cache_read": 0.30},
    "claude-3-5-sonnet-20240620":   {"input":  3.00, "output": 15.00, "cache_write":  3.75, "cache_read": 0.30},
    "claude-3-5-haiku-20241022":    {"input":  0.80, "output":  4.00, "cache_write":  1.00, "cache_read": 0.08},
    "claude-haiku-4-5":             {"input":  0.80, "output":  4.00, "cache_write":  1.00, "cache_read": 0.08},
    "claude-haiku-4-5-20251001":    {"input":  0.80, "output":  4.00, "cache_write":  1.00, "cache_read": 0.08},
    "claude-3-opus-20240229":       {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "claude-3-sonnet-20240229":     {"input":  3.00, "output": 15.00, "cache_write":  3.75, "cache_read": 0.30},
    "claude-3-haiku-20240307":      {"input":  0.25, "output":  1.25, "cache_write":  0.30, "cache_read": 0.03},
}

_DEFAULT_PRICING = {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30}


def get_pricing(model: str) -> Dict[str, float]:
    """Return pricing for a model, falling back to sonnet pricing for unknowns."""
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    # Partial match (e.g. "claude-opus-4-6-something")
    for key, pricing in MODEL_PRICING.items():
        if model.startswith(key) or key in model:
            return pricing
    return _DEFAULT_PRICING


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
) -> float:
    p = get_pricing(model)
    return (
        input_tokens          * p["input"]       / 1_000_000
        + output_tokens       * p["output"]      / 1_000_000
        + cache_creation_tokens * p["cache_write"] / 1_000_000
        + cache_read_tokens   * p["cache_read"]  / 1_000_000
    )


def shorten_model_name(model: str) -> str:
    """Return a compact display name for a model."""
    replacements = [
        ("claude-", ""),
        ("-20250219", ""),
        ("-20241022", ""),
        ("-20240620", ""),
        ("-20240229", ""),
        ("-20240307", ""),
        ("-20251001", ""),
    ]
    name = model
    for old, new in replacements:
        name = name.replace(old, new)
    return name


def format_tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.2f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def format_cost(amount: float) -> str:
    if amount < 0.0001:
        return "$0.0000"
    if amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.3f}"


@dataclass
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    total_cost: float = 0.0
    by_model: Dict[str, ModelUsage] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int,
        cache_read_tokens: int,
    ) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_creation_tokens += cache_creation_tokens
        self.cache_read_tokens += cache_read_tokens

        cost = compute_cost(model, input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens)
        self.total_cost += cost

        if model not in self.by_model:
            self.by_model[model] = ModelUsage()
        m = self.by_model[model]
        m.input_tokens += input_tokens
        m.output_tokens += output_tokens
        m.cache_creation_tokens += cache_creation_tokens
        m.cache_read_tokens += cache_read_tokens
        m.cost += cost
