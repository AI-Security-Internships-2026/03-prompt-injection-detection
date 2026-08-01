"""
Cross-turn / KV-cache persistence injection detection (deeper novel track).

Every guard we surveyed (ATR rules, PIGuard, LLM Guard, Llama Prompt Guard, and
our own single-turn pre-filter) classifies ONE message at a time. But a model's
KV cache accumulates *all* prior turns, so an attacker can:

  1. **Split** an instruction across turns — each turn is benign in isolation,
     but the assembled context ("ignore" + "all previous" + "instructions") is a
     live injection in the cached state.
  2. **Plant persistent state** — "from now on / for the rest of this chat /
     you are now X" — that steers every later turn even after the topic moves
     on. The directive persists in the KV cache.

A single-turn guard inspects turn N alone and passes it; the attack lives in
turns N-k..N together. This module inspects the CONVERSATION, not the turn:

  * per-turn (the single-turn baseline any existing guard gives),
  * the assembled/concatenated context (catches split instructions),
  * persistence markers (catches planted cross-turn directives).

`analyze_conversation` reports what the cross-turn view catches that the
single-turn baseline misses. (A model-internals demo that manipulates real
past_key_values tensors needs a local transformer + torch; that is documented
future work — this is the detection layer, and it runs offline.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from detection_utils import GuardrailDecision, analyze, collect_evidence, normalize_text

# Only strong signals (specific override phrases, role spoofing, decoded
# payloads) drive a cross-turn flag. Lone generic cues like "from now on" do
# NOT — benign conversations use them ("from now on use metric units"), so
# firing on them is the over-defense the cross-turn view is meant to avoid.
_STRONG_SIGNALS = {"high_signal", "role_spoof", "encoded_payload"}

# Directives that persist across turns (the KV-cache persistence vector).
PERSISTENCE_MARKERS: tuple[str, ...] = (
    "from now on",
    "for the rest of this conversation",
    "for the rest of our chat",
    "for all future responses",
    "in every response",
    "in all your responses",
    "in all subsequent",
    "going forward",
    "from here on",
    "until i tell you to stop",
    "always respond",
    "always answer",
    "always start",
    "always begin",
    "never mention",
    "never refuse",
    "you are now",
    "you will now",
    "permanently",
    "remember this for later",
    "remember to always",
)

_SEVERITY = {
    GuardrailDecision.ALLOW: 0,
    GuardrailDecision.REVIEW: 1,
    GuardrailDecision.BLOCK: 2,
    GuardrailDecision.ERROR: 0,
}


@dataclass(frozen=True)
class ConversationResult:
    single_turn_decision: GuardrailDecision  # best any single-turn guard can do
    cross_turn_decision: GuardrailDecision  # inspecting the assembled context
    persistence_markers: list[str] = field(default_factory=list)
    caught_by_cross_turn_only: bool = False  # the value-add over single-turn
    per_turn: list[GuardrailDecision] = field(default_factory=list)
    reason: str = ""


def _worst(decisions: list[GuardrailDecision]) -> GuardrailDecision:
    if not decisions:
        return GuardrailDecision.ALLOW
    return max(decisions, key=lambda d: _SEVERITY[d])


def analyze_conversation(turns: list[str]) -> ConversationResult:
    """Detect cross-turn injection across a sequence of user turns.

    ``turns`` is the ordered list of user messages. Returns the single-turn
    baseline decision, the cross-turn decision, any persistence markers, and
    whether the cross-turn view caught something the single-turn baseline missed.
    """
    if not turns:
        return ConversationResult(GuardrailDecision.ALLOW, GuardrailDecision.ALLOW)

    # Single-turn baseline: the best any per-message guard can do (this also
    # exposes its over-defense on benign persistence phrasing).
    per_turn = [analyze(t).decision for t in turns]
    single = _worst(per_turn)

    # Join with a space so an instruction split across turns at word boundaries
    # reassembles the way it does in the model's accumulated KV-cache context.
    assembled = " ".join(turns)
    norm = normalize_text(assembled)
    markers = [m for m in PERSISTENCE_MARKERS if m in norm]

    # Cross-turn decision from STRONG evidence in the assembled context only.
    strong = [e for e in collect_evidence(assembled) if e.signal in _STRONG_SIGNALS]
    if strong:
        score = min(1.0, sum(e.weight for e in strong))
        # A planted persistence directive + an injection = high severity.
        cross = GuardrailDecision.BLOCK if (markers or score >= 0.8) else GuardrailDecision.REVIEW
    else:
        cross = GuardrailDecision.ALLOW

    caught_only = _SEVERITY[cross] > _SEVERITY[single]
    if caught_only:
        reason = "assembled cross-turn context carries a strong injection each turn hides"
    elif strong and markers:
        reason = f"persistent cross-turn directive + injection: {markers}"
    elif cross is GuardrailDecision.ALLOW and single is not GuardrailDecision.ALLOW:
        reason = "single-turn over-defense; cross-turn context is benign"
    else:
        reason = "no cross-turn injection detected"

    return ConversationResult(
        single_turn_decision=single,
        cross_turn_decision=cross,
        persistence_markers=markers,
        caught_by_cross_turn_only=caught_only,
        per_turn=per_turn,
        reason=reason,
    )
