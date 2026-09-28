"""Unit tests for structured provider-outcome classification (Step 10/14)."""

import pytest

from provider_outcome import (
    ProviderOutcome,
    classify_provider_outcome,
    is_refusal_text,
)


# --- Anthropic-style stop_reason -------------------------------------------
@pytest.mark.parametrize(
    "stop_reason,expected",
    [
        ("refusal", ProviderOutcome.REFUSAL),
        ("max_tokens", ProviderOutcome.TRUNCATED),
        ("tool_use", ProviderOutcome.TOOL_USE),
        ("end_turn", ProviderOutcome.COMPLETED),
        ("stop_sequence", ProviderOutcome.COMPLETED),
    ],
)
def test_anthropic_stop_reason(stop_reason, expected):
    assert classify_provider_outcome({"stop_reason": stop_reason}) is expected


# --- OpenAI/Groq-style finish_reason ---------------------------------------
@pytest.mark.parametrize(
    "finish_reason,expected",
    [
        ("content_filter", ProviderOutcome.REFUSAL),
        ("length", ProviderOutcome.TRUNCATED),
        ("tool_calls", ProviderOutcome.TOOL_USE),
        ("stop", ProviderOutcome.COMPLETED),
    ],
)
def test_openai_finish_reason(finish_reason, expected):
    resp = {"choices": [{"finish_reason": finish_reason}]}
    assert classify_provider_outcome(resp) is expected


def test_attribute_style_object():
    class Resp:
        stop_reason = "refusal"

    assert classify_provider_outcome(Resp()) is ProviderOutcome.REFUSAL


def test_none_is_error():
    assert classify_provider_outcome(None) is ProviderOutcome.ERROR


def test_unknown_shape_defaults_completed():
    assert classify_provider_outcome({"foo": "bar"}) is ProviderOutcome.COMPLETED


def test_malformed_choices_no_crash():
    assert classify_provider_outcome({"choices": []}) is ProviderOutcome.COMPLETED


def test_refusal_text_fallback():
    assert is_refusal_text("I'm sorry, but I can't help with that.")
    assert not is_refusal_text("Sure, here is the answer you asked for.")
    assert not is_refusal_text("")


def test_refusal_not_confused_with_injection():
    # A refusal response is not a detected injection; it is a provider outcome.
    from detection_utils import GuardrailDecision, analyze

    refusal = "I'm sorry, but I can't help with that."
    assert is_refusal_text(refusal)
    # And the refusal text itself contains no attack imperative -> ALLOW.
    assert analyze(refusal).decision is GuardrailDecision.ALLOW
