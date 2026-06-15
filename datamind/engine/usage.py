"""UsageTracker — per-session token counting and cost calculation.

Provides:
- :class:`UsageTracker` — tracks prompt/completion tokens across calls,
  computes cost from configurable per-model rates, and exports summaries.
"""

import time

from datamind.config import LLM_DEFAULT_COST_RATES


class UsageTracker:
    """Track token usage and cost across one session.

    Rates are keyed by model name and stored as per-1K-token dollar
    amounts.  Models not found in *cost_rates* (e.g. local Ollama models)
    are charged at zero cost.
    """

    def __init__(self, cost_rates: dict | None = None) -> None:
        self._cost_rates: dict = cost_rates if cost_rates is not None else LLM_DEFAULT_COST_RATES
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._model_tokens: dict[str, dict[str, int]] = {}
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> None:
        """Register token usage for one LLM call."""
        self._prompt_tokens += prompt_tokens
        self._completion_tokens += completion_tokens

        if model not in self._model_tokens:
            self._model_tokens[model] = {"prompt_tokens": 0, "completion_tokens": 0}
        self._model_tokens[model]["prompt_tokens"] += prompt_tokens
        self._model_tokens[model]["completion_tokens"] += completion_tokens

        self._history.append({
            "timestamp": time.time(),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        })

    @property
    def prompt_tokens(self) -> int:
        """Total prompt (input) tokens across all calls."""
        return self._prompt_tokens

    @property
    def completion_tokens(self) -> int:
        """Total completion (output) tokens across all calls."""
        return self._completion_tokens

    @property
    def total_tokens(self) -> int:
        """Total tokens (prompt + completion) across all calls."""
        return self._prompt_tokens + self._completion_tokens

    @property
    def cost(self) -> float:
        """Total estimated cost in dollars.

        Computed as ``(prompt * input_rate + completion * output_rate) / 1000``
        for each model using the configured per-1K-token rates.
        Models not in the rate table contribute zero cost.
        """
        total = 0.0
        for model, tokens in self._model_tokens.items():
            rates = self._cost_rates.get(model, {"input": 0.0, "output": 0.0})
            total += (tokens["prompt_tokens"] * rates["input"] +
                       tokens["completion_tokens"] * rates["output"]) / 1000
        return total

    def export(self) -> dict:
        """Return a summary dict with totals, per-model breakdown, cost, and history."""
        return {
            "totals": {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
            },
            "by_model": dict(self._model_tokens),
            "cost": self.cost,
            "history": list(self._history),
        }
