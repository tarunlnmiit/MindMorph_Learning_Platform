"""Token + cost accounting (services/cost.py): price math and TokenMeter aggregation. No LLM/network —
the meter is fed fake LLMResults that mirror the LangChain shapes ChatGroq / the CLI placeholder emit."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from types import SimpleNamespace

from langchain_core.outputs import ChatGeneration, LLMResult
from langchain_core.messages import AIMessage

from services.cost import MODEL_PRICES, TokenMeter, estimate_cost


def _result(model, in_tok, out_tok):
    """An LLMResult shaped like ChatGroq's: usage_metadata + model_name on the AIMessage."""
    msg = AIMessage(
        content="x",
        usage_metadata={"input_tokens": in_tok, "output_tokens": out_tok, "total_tokens": in_tok + out_tok},
        response_metadata={"model_name": model},
    )
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


def _result_no_usage():
    """An LLMResult with no usage reported (mirrors the Claude CLI placeholder backend)."""
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(content="x"))]])


# --- estimate_cost -----------------------------------------------------------------------------

def test_estimate_cost_known_model_math():
    in_price, out_price = MODEL_PRICES["llama-3.3-70b-versatile"]
    cost = estimate_cost("llama-3.3-70b-versatile", 1_000_000, 1_000_000)
    assert cost == in_price + out_price


def test_estimate_cost_unknown_model_is_zero_no_raise():
    assert estimate_cost("gpt-imaginary-9", 1000, 1000) == 0.0


def test_estimate_cost_placeholder_model_is_free():
    assert estimate_cost("haiku", 5000, 5000) == 0.0


# --- TokenMeter --------------------------------------------------------------------------------

def test_meter_aggregates_multiple_calls():
    meter = TokenMeter()
    meter.on_llm_end(_result("llama-3.3-70b-versatile", 100, 50))
    meter.on_llm_end(_result("llama-3.3-70b-versatile", 200, 80))
    totals = meter.totals()
    assert totals["tokens_in"] == 300
    assert totals["tokens_out"] == 130
    assert totals["est_cost_usd"] > 0.0
    assert totals["unknown"] is False
    assert meter.calls == 2
    assert totals["by_model"]["llama-3.3-70b-versatile"]["input_tokens"] == 300


def test_meter_flags_unknown_when_usage_missing():
    meter = TokenMeter()
    meter.on_llm_end(_result_no_usage())
    totals = meter.totals()
    assert totals["unknown"] is True
    assert totals["tokens_in"] == 0 and totals["tokens_out"] == 0
    assert totals["est_cost_usd"] == 0.0


def test_meter_mixed_known_and_missing():
    meter = TokenMeter()
    meter.on_llm_end(_result("llama-3.3-70b-versatile", 100, 50))
    meter.on_llm_end(_result_no_usage())
    totals = meter.totals()
    assert totals["tokens_in"] == 100  # the reported call still counts
    assert totals["unknown"] is True   # but the silent one is flagged
