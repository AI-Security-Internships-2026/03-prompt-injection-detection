"""
HardenedGuard — a composite prompt-injection guard (the novel system).

    input
      -> canonicalization front-end        (decode base64/hex, de-obfuscate Unicode)
      -> deterministic rule layer          (high-precision structural veto)
         + fine-tuned semantic core        (PIGuard-class; injected, optional)
      -> cross-turn / KV-cache detector    (multi-turn persistence)
      -> calibrated decision

Rationale (measured on eval_dataset_v2):
  * A fine-tuned semantic guard (PIGuard) is the strongest single system (acc
    0.808) but over-defends -> FPR 0.228 caps its accuracy.
  * Feeding it the CANONICAL form recovers encoded attacks and cuts encoded FPR.
  * A calibrated threshold trades a little recall for a large FPR drop.
  * The deterministic rule layer (precision 0.869, FPR 0.032) adds back
    high-precision recall for structural attacks the semantic core misses.
  * The cross-turn detector adds a capability no single-turn guard has.

The semantic core is INJECTED (`semantic_score_fn`), so this module needs no
torch/transformers and stays importable/testable offline. Wrap PIGuard (or any
guard) with `canonicalize` when injecting for best results.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from canonicalize import canonicalize
from detection_utils import GuardrailDecision, analyze
from multiturn import analyze_conversation


@dataclass(frozen=True)
class HardenedVerdict:
    is_attack: bool
    score: float
    decision: GuardrailDecision
    rule_decision: GuardrailDecision
    semantic_score: float | None
    cross_turn_flag: bool
    reason: str


class HardenedGuard:
    """Compose canonicalization + rules + a semantic core + cross-turn detection."""

    def __init__(
        self,
        semantic_score_fn: Callable[[str], float] | None = None,
        semantic_threshold: float = 0.5,
    ) -> None:
        # semantic_score_fn should already score the RAW text; HardenedGuard
        # feeds it the canonical form, so no need to pre-wrap it.
        self._semantic = semantic_score_fn
        self.threshold = semantic_threshold

    def assess(self, text: str, history: Sequence[str] | None = None) -> HardenedVerdict:
        canon = canonicalize(text)
        rule = analyze(canon).decision
        rule_block = rule is GuardrailDecision.BLOCK

        sem: float | None = None
        if self._semantic is not None:
            sem = float(self._semantic(canon))
        sem_flag = sem is not None and sem >= self.threshold

        cross_flag = False
        if history:
            conv = analyze_conversation([*history, text])
            cross_flag = conv.caught_by_cross_turn_only or (
                conv.cross_turn_decision is GuardrailDecision.BLOCK
            )

        is_attack = bool(sem_flag or rule_block or cross_flag)

        # Continuous fused score (for calibration / ranking).
        rule_component = 1.0 if rule_block else (0.5 if rule is GuardrailDecision.REVIEW else 0.0)
        score = max(sem or 0.0, rule_component, 1.0 if cross_flag else 0.0)

        if is_attack:
            decision = GuardrailDecision.BLOCK
        elif rule is GuardrailDecision.REVIEW:
            decision = GuardrailDecision.REVIEW
        else:
            decision = GuardrailDecision.ALLOW

        parts = []
        if sem_flag:
            parts.append(f"semantic={sem:.2f}>=thr")
        if rule_block:
            parts.append("rule=BLOCK")
        if cross_flag:
            parts.append("cross_turn")
        reason = " + ".join(parts) if parts else "no attack signal"

        return HardenedVerdict(
            is_attack=is_attack,
            score=score,
            decision=decision,
            rule_decision=rule,
            semantic_score=sem,
            cross_turn_flag=cross_flag,
            reason=reason,
        )
