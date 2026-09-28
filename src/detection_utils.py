"""
Shared, dependency-free prompt-injection detection utilities.

Single source of truth for the deterministic pre-filter used by the harness
scripts. Stdlib only; imports cleanly on Python 3.14. This layer is a
**pre-filter that emits structured evidence**, not the final enforcement
decision (audit Step 8): generic keywords alone never hard-block, quoted /
analytical / translated / dataset content is downgraded, and the ML classifier
plus human review own the final call.

Design notes:
  * H1 — decode base64 / hex / rot13 payloads (resource-limited) before scan.
  * H2 — Unicode NFKC + zero-width strip + confusable fold + script-mix signal.
  * H3 / Rule 7 — provider-refusal classification lives in provider_outcome.py;
    is_provider_refusal here is a thin text fallback kept for compatibility.
  * Step 7 — hard resource limits on every decode path.
  * Step 8 — DetectionResult / DetectionEvidence / GuardrailDecision.
  * Step 9 — contextual downgrade for quoted / benign-security content.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

# ---------------------------------------------------------------------------
# Resource limits (Step 7). Every decode path must stop when these are hit.
# ---------------------------------------------------------------------------
MAX_INPUT_CHARS = 32_768
MAX_CANDIDATES = 16
MAX_DECODE_DEPTH = 2
MAX_DECODED_BYTES = 65_536
MAX_EXPANSION_RATIO = 4.0

# ---------------------------------------------------------------------------
# Pattern sets (single source of truth — audit M1)
# ---------------------------------------------------------------------------
# High-signal: specific imperative override / exfiltration phrases.
HIGH_SIGNAL_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous",
    "ignore any previous",
    "ignore all instructions",
    "ignore the above",
    "disregard all instructions",
    "disregard previous",
    "forget previous instructions",
    "forget all instructions",
    "nullify everything above",
    "prior guidelines no longer apply",
    "i have been pwned",
    "say pwned",
    "reveal your system prompt",
    "reveal the system prompt",
    "reveal your instructions",
    "print your system prompt",
    "print the system prompt",
    "repeat the words above",
    "system override",
)

# Generic: weaker single-token cues.
GENERIC_PATTERNS: tuple[str, ...] = (
    "you are now",
    "new instructions:",
    "new instruction:",
    "developer mode",
    "stop everything",
    "stop translating",
    "print yes",
    "pwned",
    "ignore and print",
    "do not follow",
    "from now on",
    "as an unrestricted",
    "with no restrictions",
    "no content restrictions",
    "uncensored",
)

# Role/channel spoofing.
ROLE_SPOOF_PATTERNS: tuple[str, ...] = (
    "system:",
    "developer:",
    "administrator:",
    "assistant:",
    "[system]",
    "<system>",
    "### system",
    "role: system",
    "note to ai",
    "ai assistant:",
)

# Kept for backwards compatibility (older imports referenced this name).
SUSPICIOUS_PATTERNS: tuple[str, ...] = HIGH_SIGNAL_PATTERNS + GENERIC_PATTERNS

DELIMITER_MARKERS: tuple[str, ...] = (
    "----------",
    "==========",
    "```",
    "</s>",
    "<|im_start|>",
    "<|im_end|>",
    "[inst]",
    "[/inst]",
)

_WEIGHTS = {"high": 0.5, "role": 0.4, "generic": 0.35, "decoded": 0.5, "mixed_script": 0.15}
_REVIEW_THRESHOLD = 0.35
_BLOCK_THRESHOLD = 0.8

# Zero-width / invisible characters.
_ZERO_WIDTH = dict.fromkeys(ord(c) for c in ("​", "‌", "‍", "⁠", "﻿", "­"))

# Minimal, explicitly-partial confusable map (NFKC does not fold these).
_CONFUSABLES = {
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
    "ԁ": "d",
    "А": "a",
    "В": "b",
    "С": "c",
    "Е": "e",
    "Н": "h",
    "К": "k",
    "М": "m",
    "О": "o",
    "Р": "p",
    "Т": "t",
    "Х": "x",
    "Ѕ": "s",
    "ѕ": "s",
}

_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_HEX_RE = re.compile(r"(?:[0-9a-fA-F]{2}\s*){8,}")
_CYRILLIC_GREEK = re.compile(r"[Ͱ-ϿЀ-ӿ]")
_LATIN = re.compile(r"[A-Za-z]")

# Context cues that downgrade a hard block (Step 9).
_CONTEXT_CUES = (
    "explain",
    "explanation",
    "why is",
    "why are",
    "analyze",
    "analysis",
    "translate",
    "translation",
    "example of",
    "is this an attack",
    "dataset",
    "sample",
    "the log contains",
    "log entry",
    "incident report",
    "detect the phrase",
    "our detector",
    "how can a guardrail",
    "how do guardrails",
    "what is a",
    "what is an",
    "for research",
    "academic",
)


# ---------------------------------------------------------------------------
# Structured result types (Step 8)
# ---------------------------------------------------------------------------
class GuardrailDecision(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"
    ERROR = "error"


@dataclass(frozen=True)
class DetectionEvidence:
    signal: str
    source: str
    matched_text: str
    transformation: str | None
    weight: float


@dataclass(frozen=True)
class DetectionResult:
    decision: GuardrailDecision
    score: float
    categories: list[str] = field(default_factory=list)
    evidence: list[DetectionEvidence] = field(default_factory=list)
    reason: str = ""


# ---------------------------------------------------------------------------
# Normalization (H2)
# ---------------------------------------------------------------------------
def normalize_text(text: str) -> str:
    """NFKC-normalize, strip zero-width chars, fold confusables, lowercase.

    Input is truncated to ``MAX_INPUT_CHARS`` first (Step 7).
    """
    if not text:
        return ""
    text = text[:MAX_INPUT_CHARS]
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_ZERO_WIDTH)
    text = "".join(_CONFUSABLES.get(ch, ch) for ch in text)
    return text.lower()


def has_mixed_script(text: str) -> bool:
    """True if the text mixes Latin with Cyrillic/Greek letters (obfuscation cue)."""
    if not text:
        return False
    sample = text[:MAX_INPUT_CHARS]
    return bool(_LATIN.search(sample)) and bool(_CYRILLIC_GREEK.search(sample))


# ---------------------------------------------------------------------------
# Bounded decoders (H1 + Step 7)
# ---------------------------------------------------------------------------
def _printable_ratio(s: str) -> float:
    if not s:
        return 0.0
    return sum(c.isprintable() or c.isspace() for c in s) / len(s)


def _decode_base64(token: str) -> str:
    if not (16 <= len(token) <= MAX_DECODED_BYTES):
        return ""
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.b64decode(padded, validate=True)
    except binascii.Error, ValueError:
        return ""
    if len(raw) > MAX_DECODED_BYTES or len(raw) > MAX_EXPANSION_RATIO * len(token):
        return ""
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""
    return decoded if _printable_ratio(decoded) >= 0.8 else ""


def _decode_hex(token: str) -> str:
    cleaned = re.sub(r"\s+", "", token)
    if len(cleaned) % 2 != 0 or not (16 <= len(cleaned) <= 2 * MAX_DECODED_BYTES):
        return ""
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError:
        return ""
    if len(raw) > MAX_DECODED_BYTES:
        return ""
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""
    return decoded if _printable_ratio(decoded) >= 0.8 else ""


def _rot13(text: str) -> str:
    return codecs.encode(text[:MAX_DECODED_BYTES], "rot_13")


def _decode_candidates(text: str) -> list[tuple[str, str]]:
    """Return ``(decoded_text, transformation)`` pairs, resource-limited.

    Applies base64/hex up to ``MAX_DECODE_DEPTH`` (nested encodings) plus a
    single rot13 transform, capped at ``MAX_CANDIDATES`` total.
    """
    if not text:
        return []
    text = text[:MAX_INPUT_CHARS]
    out: list[tuple[str, str]] = []
    seen = set()

    frontier = [text]
    for depth in range(MAX_DECODE_DEPTH):
        next_frontier: list[str] = []
        for src in frontier:
            for tok in _BASE64_RE.findall(src)[:MAX_CANDIDATES]:
                dec = _decode_base64(tok)
                if dec and dec.lower() != tok.lower() and dec not in seen:
                    seen.add(dec)
                    tag = "base64" if depth == 0 else f"base64^{depth + 1}"
                    out.append((dec, tag))
                    next_frontier.append(dec)
                    if len(out) >= MAX_CANDIDATES:
                        return out
            for tok in _HEX_RE.findall(src)[:MAX_CANDIDATES]:
                dec = _decode_hex(tok)
                if dec and dec not in seen:
                    seen.add(dec)
                    out.append((dec, "hex" if depth == 0 else f"hex^{depth + 1}"))
                    next_frontier.append(dec)
                    if len(out) >= MAX_CANDIDATES:
                        return out
        frontier = next_frontier
        if not frontier:
            break

    rot = _rot13(text)
    if rot != text and rot not in seen:
        out.append((rot, "rot13"))
    return out[:MAX_CANDIDATES]


def decode_layers(text: str) -> list[str]:
    """Backward-compatible: decoded candidate strings hidden inside ``text``."""
    return [c for c, _ in _decode_candidates(text)]


# ---------------------------------------------------------------------------
# Signal collection
# ---------------------------------------------------------------------------
def _match(surface: str, patterns: tuple[str, ...]) -> list[str]:
    return [p for p in patterns if p in surface]


def collect_evidence(prompt: str) -> list[DetectionEvidence]:
    """Gather structured evidence from the normalized prompt and decoded layers."""
    if not prompt:
        return []
    evidence: list[DetectionEvidence] = []
    norm = normalize_text(prompt)

    for p in _match(norm, HIGH_SIGNAL_PATTERNS):
        evidence.append(DetectionEvidence("high_signal", "surface", p, None, _WEIGHTS["high"]))
    for p in _match(norm, GENERIC_PATTERNS):
        evidence.append(DetectionEvidence("generic", "surface", p, None, _WEIGHTS["generic"]))
    for p in _match(norm, ROLE_SPOOF_PATTERNS):
        evidence.append(DetectionEvidence("role_spoof", "surface", p, None, _WEIGHTS["role"]))

    if has_mixed_script(prompt) and (
        _match(norm, HIGH_SIGNAL_PATTERNS) or _match(norm, GENERIC_PATTERNS)
    ):
        evidence.append(
            DetectionEvidence(
                "mixed_script",
                "surface",
                "latin+cyrillic/greek",
                "confusable_fold",
                _WEIGHTS["mixed_script"],
            )
        )

    # Decoded layers. Base64/hex only count when the decoded text carries a
    # suspicious signal; rot13 only counts on a HIGH-signal hit (Step 7 gating).
    for decoded, transform in _decode_candidates(prompt):
        dnorm = normalize_text(decoded)
        high = _match(dnorm, HIGH_SIGNAL_PATTERNS)
        generic = _match(dnorm, GENERIC_PATTERNS)
        if transform == "rot13":
            for p in high:
                evidence.append(
                    DetectionEvidence("high_signal", "decoded", p, transform, _WEIGHTS["decoded"])
                )
        else:
            for p in high + generic:
                evidence.append(
                    DetectionEvidence(
                        "encoded_payload", "decoded", p, transform, _WEIGHTS["decoded"]
                    )
                )
    return evidence


def _context_tags(prompt: str) -> list[str]:
    """Detect quotation / analytical / dataset context that should downgrade a block."""
    norm = normalize_text(prompt)
    tags = [cue for cue in _CONTEXT_CUES if cue in norm]
    # Quoted or code-fenced payload.
    if re.search(r"[\"'`].{0,200}?[\"'`]", prompt) or "```" in prompt:
        # Only treat as quotation context if a suspicious phrase sits inside quotes.
        for p in HIGH_SIGNAL_PATTERNS + GENERIC_PATTERNS:
            if re.search(r"[\"'`][^\"'`]*" + re.escape(p) + r"[^\"'`]*[\"'`]", norm):
                tags.append("quoted")
                break
    return tags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze(prompt: str) -> DetectionResult:
    """Context-aware structured pre-filter decision (Step 8/9).

    Contract:
      * no evidence          -> ALLOW
      * evidence + context   -> REVIEW  (never auto-BLOCK; never silently ALLOW)
      * score >= 0.8         -> BLOCK
      * score >= 0.35        -> REVIEW
    """
    if prompt is None:
        return DetectionResult(GuardrailDecision.ERROR, 0.0, [], [], "no input")

    evidence = collect_evidence(prompt)
    if not evidence:
        return DetectionResult(GuardrailDecision.ALLOW, 0.0, [], [], "no suspicious signal")

    score = min(1.0, sum(e.weight for e in evidence))
    categories = sorted({e.signal for e in evidence})
    context = _context_tags(prompt)

    if context:
        return DetectionResult(
            GuardrailDecision.REVIEW,
            score,
            categories,
            evidence,
            f"suspicious phrase(s) present but in {'/'.join(sorted(set(context)))} context; "
            "downgraded to human review",
        )
    if score >= _BLOCK_THRESHOLD:
        decision = GuardrailDecision.BLOCK
    elif score >= _REVIEW_THRESHOLD:
        decision = GuardrailDecision.REVIEW
    else:
        decision = GuardrailDecision.ALLOW
    return DetectionResult(
        decision, score, categories, evidence, f"{len(evidence)} signal(s); score={score:.2f}"
    )


def keyword_signals(prompt: str) -> list[str]:
    """Backward-compatible: flat list of matched pattern strings."""
    return [e.matched_text for e in collect_evidence(prompt)]


def detect_injection(prompt: str) -> tuple[bool, list[str]]:
    """Backward-compatible pattern-presence detector: ``(is_suspicious, matched)``.

    Low-level layer (not context-aware); use :func:`analyze` for a decision.
    """
    matched = keyword_signals(prompt)
    # De-duplicate preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for m in matched:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return (len(unique) > 0, unique)


def is_provider_refusal(response: str) -> bool:
    """Thin text fallback for provider refusal (prefer provider_outcome)."""
    from provider_outcome import is_refusal_text

    return is_refusal_text(response)
