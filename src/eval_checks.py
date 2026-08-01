"""
Train/test leakage-checking infrastructure (audit §9, Step 12).

Dependency-free helpers to detect data leakage across dataset splits. These run
on small synthetic fixtures in CI; **real performance claims stay blocked**
until the original training data is restored (blocker B1/B2). The point is that
the *checking machinery* exists and is tested, so that when data returns the
splits can be validated before any metric is trusted.

Do NOT random-row-split templated synthetic data: samples from one template
family must not straddle splits (Step 12).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def exact_duplicates_across_splits(train: Iterable[str], test: Iterable[str]) -> set[str]:
    """Return texts appearing verbatim in both splits."""
    return set(train) & set(test)


def normalized_duplicates_across_splits(train: Iterable[str], test: Iterable[str]) -> set[str]:
    """Return normalized texts (whitespace/case-folded) present in both splits."""
    tr = {_normalize(t) for t in train}
    te = {_normalize(t) for t in test}
    return tr & te


def _char_ngrams(text: str, n: int = 4) -> set[str]:
    t = _normalize(text)
    if len(t) < n:
        return {t} if t else set()
    return {t[i : i + n] for i in range(len(t) - n + 1)}


def jaccard(a: str, b: str, n: int = 4) -> float:
    ga, gb = _char_ngrams(a, n), _char_ngrams(b, n)
    if not ga or not gb:
        return 0.0
    inter = len(ga & gb)
    union = len(ga | gb)
    return inter / union if union else 0.0


def near_duplicate_pairs(
    train: Sequence[str], test: Sequence[str], threshold: float = 0.8, n: int = 4
) -> list[tuple[int, int, float]]:
    """Return (train_idx, test_idx, similarity) for near-duplicate cross-split pairs."""
    pairs: list[tuple[int, int, float]] = []
    for i, a in enumerate(train):
        for j, b in enumerate(test):
            sim = jaccard(a, b, n)
            if sim >= threshold:
                pairs.append((i, j, round(sim, 4)))
    return pairs


def group_split_is_clean(train_groups: Iterable[str], test_groups: Iterable[str]) -> bool:
    """True if no group id (e.g. template family) appears in both splits."""
    return not (set(train_groups) & set(test_groups))


def leakage_report(
    train: Sequence[str],
    test: Sequence[str],
    train_groups: Sequence[str] | None = None,
    test_groups: Sequence[str] | None = None,
    near_dup_threshold: float = 0.8,
) -> dict[str, object]:
    """Aggregate leakage signals into a single report dict."""
    report: dict[str, object] = {
        "exact_duplicates": sorted(exact_duplicates_across_splits(train, test)),
        "normalized_duplicates": sorted(normalized_duplicates_across_splits(train, test)),
        "near_duplicate_pairs": near_duplicate_pairs(train, test, near_dup_threshold),
    }
    if train_groups is not None and test_groups is not None:
        report["group_split_clean"] = group_split_is_clean(train_groups, test_groups)
    report["leaking"] = bool(
        report["exact_duplicates"]
        or report["normalized_duplicates"]
        or report["near_duplicate_pairs"]
        or (train_groups is not None and not report.get("group_split_clean", True))
    )
    return report
