"""Tests for UsageTracker — per-session token counting and cost calculation."""
import pytest

from datamind.config import LLM_DEFAULT_COST_RATES
from datamind.engine.usage import UsageTracker


# ---------------------------------------------------------------------------
# test_initial_state_zero
# ---------------------------------------------------------------------------

def test_initial_state_zero():
    """All token counts and cost start at zero."""
    tracker = UsageTracker()
    assert tracker.prompt_tokens == 0
    assert tracker.completion_tokens == 0
    assert tracker.total_tokens == 0
    assert tracker.cost == 0.0


# ---------------------------------------------------------------------------
# test_record_accumulates_tokens
# ---------------------------------------------------------------------------

def test_record_accumulates_tokens():
    """Three record() calls accumulate prompt and completion tokens correctly."""
    tracker = UsageTracker()
    tracker.record(100, 50, "gpt-4o")
    tracker.record(200, 80, "gpt-4o")
    tracker.record(150, 70, "gpt-4o")

    assert tracker.prompt_tokens == 450
    assert tracker.completion_tokens == 200
    assert tracker.total_tokens == 650


# ---------------------------------------------------------------------------
# test_cost_calculation
# ---------------------------------------------------------------------------

def test_cost_calculation():
    """Cost is calculated using the configured model rates: (input*input_rate + output*output_rate) / 1000."""
    tracker = UsageTracker(cost_rates={
        "gpt-4o": {"input": 0.0025, "output": 0.01},
    })
    # 1000 prompt + 500 completion
    # cost = (1000*0.0025 + 500*0.01) / 1000 = (2.5 + 5.0) / 1000 = 0.0075
    tracker.record(1000, 500, "gpt-4o")
    expected = (1000 * 0.0025 + 500 * 0.01) / 1000
    assert tracker.cost == pytest.approx(expected)


# ---------------------------------------------------------------------------
# test_ollama_zero_cost
# ---------------------------------------------------------------------------

def test_ollama_zero_cost():
    """Ollama models (or models not in cost_rates) incur zero cost."""
    tracker = UsageTracker()
    tracker.record(5000, 3000, "llama3:latest")
    assert tracker.cost == 0.0
    assert tracker.prompt_tokens == 5000
    assert tracker.completion_tokens == 3000


# ---------------------------------------------------------------------------
# test_export_returns_complete_data
# ---------------------------------------------------------------------------

def test_export_returns_complete_data():
    """export() returns a dict with totals, per-model breakdown, and call history."""
    tracker = UsageTracker()
    tracker.record(100, 50, "gpt-4o")
    tracker.record(200, 80, "gpt-4o-mini")

    result = tracker.export()
    assert "totals" in result
    assert "by_model" in result
    assert "history" in result
    assert "cost" in result

    assert result["totals"]["prompt_tokens"] == 300
    assert result["totals"]["completion_tokens"] == 130
    assert result["totals"]["total_tokens"] == 430
    assert isinstance(result["history"], list)
    assert len(result["history"]) == 2


# ---------------------------------------------------------------------------
# test_per_model_breakdown
# ---------------------------------------------------------------------------

def test_per_model_breakdown():
    """Calls to different models are tracked separately in the per-model breakdown."""
    tracker = UsageTracker(cost_rates={
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    })
    tracker.record(100, 50, "gpt-4o")
    tracker.record(200, 80, "gpt-4o-mini")
    tracker.record(50, 30, "gpt-4o")

    breakdown = tracker.export()["by_model"]
    assert "gpt-4o" in breakdown
    assert "gpt-4o-mini" in breakdown

    gpt4o = breakdown["gpt-4o"]
    assert gpt4o["prompt_tokens"] == 150
    assert gpt4o["completion_tokens"] == 80

    gpt4o_mini = breakdown["gpt-4o-mini"]
    assert gpt4o_mini["prompt_tokens"] == 200
    assert gpt4o_mini["completion_tokens"] == 80


# ---------------------------------------------------------------------------
# test_call_history
# ---------------------------------------------------------------------------

def test_call_history():
    """Each record() call stores an entry with timestamp, model, and token counts."""
    tracker = UsageTracker()
    tracker.record(100, 50, "gpt-4o")
    tracker.record(200, 80, "gpt-4o-mini")

    history = tracker.export()["history"]
    assert len(history) == 2

    entry1 = history[0]
    assert "timestamp" in entry1
    assert entry1["model"] == "gpt-4o"
    assert entry1["prompt_tokens"] == 100
    assert entry1["completion_tokens"] == 50

    entry2 = history[1]
    assert "timestamp" in entry2
    assert entry2["model"] == "gpt-4o-mini"
    assert entry2["prompt_tokens"] == 200
    assert entry2["completion_tokens"] == 80
