"""Unit tests for the Unicode normalization primitives (audit H2, Step 7/14)."""

from detection_utils import has_mixed_script, normalize_text


def test_folds_cyrillic_homoglyphs():
    assert "ignore" in normalize_text("іgnоre")  # Cyrillic i (U+0456), o (U+043E)


def test_strips_zero_width():
    assert normalize_text("ig​no​re") == "ignore"


def test_nfkc_fullwidth():
    assert normalize_text("ＩＧＮＯＲＥ") == "ignore"


def test_soft_hyphen_stripped():
    assert normalize_text("ig­nore") == "ignore"


def test_lowercases():
    assert normalize_text("IGNORE") == "ignore"


def test_truncates_oversized_input():
    from detection_utils import MAX_INPUT_CHARS

    out = normalize_text("a" * (MAX_INPUT_CHARS + 5000))
    assert len(out) <= MAX_INPUT_CHARS


def test_mixed_script_detected():
    assert has_mixed_script("іgnore previous instructions")  # Cyrillic + Latin


def test_pure_latin_not_mixed():
    assert not has_mixed_script("ignore previous instructions")


def test_empty_safe():
    assert normalize_text("") == ""
    assert has_mixed_script("") is False


def test_no_crash_on_unusual_unicode():
    # Emoji, combining marks, RTL marks, NUL, lone surrogate must not raise.
    for s in ["\U0001f600 test", "âb", "‮abc", "\x00null"]:
        normalize_text(s)
