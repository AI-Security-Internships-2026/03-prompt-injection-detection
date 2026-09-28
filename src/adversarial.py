"""
Adversarial obfuscation transforms for evaluating guard robustness.

Given a cleartext attack, produce obfuscated variants that hide the payload from
a guard that inspects raw text: base64 / hex / rot13 encodings and Unicode
homoglyph / zero-width tricks. Used by scripts/eval_canonicalization.py to
measure how much recall a guard loses under obfuscation and how much the
canonicalization front-end (src/canonicalize.py) recovers.
"""

from __future__ import annotations

import base64
import codecs

# Latin -> Cyrillic/Greek look-alikes (inverse of the folding map).
_HOMOGLYPH = {
    "a": "а",
    "e": "е",
    "o": "о",
    "p": "р",
    "c": "с",
    "y": "у",
    "x": "х",
    "i": "і",
    "s": "ѕ",
}
_ZWSP = "​"


# NOTE: encodings are returned WITHOUT a natural-language carrier
# ("please decode and follow ...") on purpose. A carrier is itself an injection
# cue that a competent guard flags directly, masking the real effect. The honest
# threat is *indirect* injection: an encoded instruction hidden in data (a
# document / tool output / RAG passage) with no cue — which a guard misses
# unless the payload is decoded first. Measured on protectai (LLM Guard's model):
# carrier-free base64/rot13 attacks score ~0.0 raw, ~1.0 through the front-end.
def base64_variant(payload: str) -> str:
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def hex_variant(payload: str) -> str:
    return payload.encode("utf-8").hex()


def rot13_variant(payload: str) -> str:
    return codecs.encode(payload, "rot_13")


def homoglyph_variant(payload: str) -> str:
    return "".join(_HOMOGLYPH.get(ch, ch) for ch in payload)


def zero_width_variant(payload: str) -> str:
    # Insert a zero-width space after the first char of each word.
    out = []
    for word in payload.split(" "):
        out.append(word[:1] + _ZWSP + word[1:] if len(word) > 1 else word)
    return " ".join(out)


VARIANTS = {
    "base64": base64_variant,
    "hex": hex_variant,
    "rot13": rot13_variant,
    "homoglyph": homoglyph_variant,
    "zero_width": zero_width_variant,
}


def make_variants(payload: str) -> dict[str, str]:
    """Return {obfuscation_name: obfuscated_text} for one cleartext payload."""
    return {name: fn(payload) for name, fn in VARIANTS.items()}
