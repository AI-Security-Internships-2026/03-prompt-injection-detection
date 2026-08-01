"""
Train + evaluate the reproducible RANA prompt-injection model (audit B1/B2 fix).

Pipeline:
  1. Load datasets/rana_train.csv (fetched by scripts/fetch_data.py).
  2. LEAKAGE CHECK vs datasets/eval_dataset_v2.csv (exact + normalized). Any
     training row whose normalized text also appears in the eval set is removed
     BEFORE training, so eval metrics are not inflated by leakage.
  3. Train TF-IDF (1,2-gram) + Logistic Regression (fixed seed, pinned deps).
  4. Save artifacts to experiments/models/rana_{vectorizer,classifier}.joblib
     (gitignored, regenerable) and record SHA-256 + producer versions in the
     artifact manifest with trusted:true.
  5. Evaluate on the held-out eval set; write reports/rana-model-results.md with
     honest metrics (overall + per-category + per-language). No claim is made
     that these match the intern's original numbers.

Usage:
    python scripts/train_rana.py
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from eval_checks import (  # noqa: E402
    exact_duplicates_across_splits,
    near_duplicate_pairs,
    normalized_duplicates_across_splits,
)

TRAIN_CSV = REPO / "datasets" / "rana_train.csv"
AUG_CSV = REPO / "datasets" / "rana_multilingual_aug.csv"
EVAL_CSV = REPO / "datasets" / "eval_dataset_v2.csv"
MODELS_DIR = REPO / "experiments" / "models"
VEC_PATH = MODELS_DIR / "rana_vectorizer.joblib"
CLF_PATH = MODELS_DIR / "rana_classifier.joblib"
MANIFEST = MODELS_DIR / "artifact_manifest.json"
REPORT = REPO / "reports" / "rana-model-results.md"
SEED = 42
THRESHOLD = 0.5


def _norm(s: str) -> str:
    import re

    return re.sub(r"\s+", " ", str(s).strip().lower())


def _metrics(y_true, y_pred) -> dict:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "fpr": round(float(fp / (fp + tn)), 4) if (fp + tn) else 0.0,
        "fnr": round(float(fn / (fn + tp)), 4) if (fn + tp) else 0.0,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not TRAIN_CSV.exists():
        raise FileNotFoundError(f"{TRAIN_CSV} missing. Run: python scripts/fetch_data.py first.")
    train = pd.read_csv(TRAIN_CSV)[["text", "label"]]
    # Multilingual augmentation (audit B3) is OPT-IN via RANA_AUGMENT=1. It is OFF
    # by default because it empirically did NOT help: adding balanced translated
    # rows dropped multilingual-category recall 0.38 -> 0.22 and encoded 0.88 ->
    # 0.62 (TF-IDF is lexical and does not transfer across scripts). B3 needs a
    # multilingual semantic model (docs/multilingual-plan.md), not augmentation.
    aug_rows = 0
    if os.environ.get("RANA_AUGMENT") and AUG_CSV.exists():
        aug = pd.read_csv(AUG_CSV)[["text", "label"]]
        aug_rows = len(aug)
        train = pd.concat([train, aug], ignore_index=True)
        print(f"Multilingual augmentation (experimental): +{aug_rows} rows")
    train["text"] = train["text"].astype(str)
    train["label"] = train["label"].astype(int)
    train = train.drop_duplicates(subset=["text"]).reset_index(drop=True)

    ev = pd.read_csv(EVAL_CSV).dropna(subset=["text", "label"])
    ev["label"] = ev["label"].astype(int)

    # ---- Leakage check (audit §9, B2): remove eval-overlapping rows from train ----
    tr_texts = train["text"].astype(str).tolist()
    ev_texts = ev["text"].astype(str).tolist()
    exact = exact_duplicates_across_splits(tr_texts, ev_texts)
    normd = normalized_duplicates_across_splits(tr_texts, ev_texts)
    ev_norm = {_norm(t) for t in ev_texts}
    keep = ~train["text"].map(lambda t: _norm(t) in ev_norm)
    removed = int((~keep).sum())
    train = train[keep].reset_index(drop=True)
    # Sampled near-duplicate check (bounded; full pairwise is O(train*eval)).
    sample = train["text"].sample(min(500, len(train)), random_state=SEED).tolist()
    near = near_duplicate_pairs(sample, ev_texts, threshold=0.9)
    print(
        f"Leakage check: exact={len(exact)} normalized={len(normd)} "
        f"near_dup(sampled@0.9)={len(near)} -> removed {removed} train rows"
    )

    X_train = train["text"].astype(str)
    y_train = train["label"].astype(int)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
        max_features=100000,
    )
    Xtr = vectorizer.fit_transform(X_train)
    clf = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=SEED)
    clf.fit(Xtr, y_train)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, VEC_PATH)
    joblib.dump(clf, CLF_PATH)

    # ---- Evaluate on held-out eval set ----
    Xev = vectorizer.transform(ev["text"].astype(str))
    proba = clf.predict_proba(Xev)[:, 1]
    pred = (proba >= THRESHOLD).astype(int)
    y = ev["label"].to_numpy()
    overall = _metrics(y, pred)

    per_cat = {}
    if "attack_type" in ev.columns:
        for cat in sorted(ev["attack_type"].dropna().unique()):
            m = (ev["attack_type"] == cat).to_numpy()
            per_cat[cat] = {"n": int(m.sum()), **_metrics(y[m], pred[m])}
    per_lang = {}
    if "language" in ev.columns:
        for lang in sorted(ev["language"].dropna().unique()):
            m = (ev["language"] == lang).to_numpy()
            per_lang[lang] = {"n": int(m.sum()), "recall": _metrics(y[m], pred[m])["recall"]}

    # ---- Update manifest (RANA artifacts are trusted: we built them here) ----
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    for name, path in (("rana_vectorizer.joblib", VEC_PATH), ("rana_classifier.joblib", CLF_PATH)):
        manifest[name] = {
            "sha256": _sha256(path),
            "source": "built by scripts/train_rana.py from datasets/rana_train.csv",
            "trusted": True,
            "producer_python": platform.python_version(),
            "producer_numpy": np.__version__,
            "producer_sklearn": sklearn.__version__,
            "notes": "Reproducible RANA model; rebuild via fetch_data.py + train_rana.py.",
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # ---- Write report ----
    ts = datetime.now(UTC).isoformat()
    lines = [
        "# RANA Model — Results",
        "",
        f"- Generated: {ts}",
        f"- Env: Python {platform.python_version()}, sklearn {sklearn.__version__}",
        "- Training data: datasets/rana_train.csv (see datasets/rana_train.provenance.json)",
        f"- Training rows after leakage removal: {len(train)} (removed {removed} eval-overlapping)",
        f"- Model: TF-IDF(1,2) + LogisticRegression(class_weight=balanced, seed={SEED})",
        f"- Artifacts (gitignored, regenerable): {VEC_PATH.name}, {CLF_PATH.name}",
        "",
        f"- Multilingual augmentation rows added (B3): {aug_rows}",
        "",
        "## Leakage check vs eval_dataset_v2.csv (B2)",
        f"- Exact-duplicate texts in both: {len(exact)}",
        f"- Normalized-duplicate texts in both: {len(normd)}",
        f"- Sampled near-duplicate pairs (@0.9): {len(near)}",
        f"- Train rows removed before training: {removed}",
        "",
        "## Held-out evaluation (datasets/eval_dataset_v2.csv, threshold 0.50)",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k in ("accuracy", "precision", "recall", "f1", "fpr", "fnr"):
        lines.append(f"| {k} | {overall[k]} |")
    lines += ["", "## Per-category recall", "| Category | n | recall |", "|---|---|---|"]
    for cat, m in per_cat.items():
        lines.append(f"| {cat} | {m['n']} | {m['recall']} |")
    lines += ["", "## Per-language recall", "| Language | n | recall |", "|---|---|---|"]
    for lang, m in per_lang.items():
        lines.append(f"| {lang} | {m['n']} | {m['recall']} |")
    lines += [
        "",
        "## Honesty notes",
        "- These are the RANA model's OWN metrics on a newly-sourced 2026 dataset; "
        "they are NOT the intern's original reported numbers and are not comparable to them.",
        "- Multilingual recall remains a known gap (B3): the training data is en-centric.",
        "- Reproduce: `python scripts/fetch_data.py && python scripts/train_rana.py`.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("OVERALL:", json.dumps(overall))
    print("Report ->", REPORT)


if __name__ == "__main__":
    main()
