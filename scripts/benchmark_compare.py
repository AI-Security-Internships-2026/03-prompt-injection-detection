"""
Compare the updated code against the previous benchmark (audit deliverable).

Evaluates, on the same held-out datasets/eval_dataset_v2.csv:
  * RANA ML model (src/rana_model.py),
  * the deterministic pre-filter (src/detection_utils.analyze; BLOCK/REVIEW = flag),
  * a combined detector (ML attack OR deterministic flag),
and tabulates them beside the stored results for the intern's ML detector,
Protect AI LLM Guard, and Meta Llama Prompt Guard from
experiments/results/guardrail_comparison.json.

Writes reports/rana-comparison.md. Regenerate with:
    python scripts/benchmark_compare.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
import rana_model  # noqa: E402
from detection_utils import GuardrailDecision, analyze  # noqa: E402

EVAL = REPO / "datasets" / "eval_dataset_v2.csv"
STORED = REPO / "experiments" / "results" / "guardrail_comparison.json"
REPORT = REPO / "reports" / "rana-comparison.md"
THRESHOLD = 0.5


def _metrics(y, pred):
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "accuracy": round((tp + tn) / len(y), 3),
        "precision": round(prec, 3),
        "recall": round(rec, 3),
        "f1": round(2 * prec * rec / (prec + rec), 3) if (prec + rec) else 0.0,
        "fpr": round(fp / (fp + tn), 3) if (fp + tn) else 0.0,
    }


def _cat_recall_fpr(df, y, pred, cat):
    m = (df["attack_type"] == cat).to_numpy()
    if not m.any():
        return None
    tn, fp, fn, tp = confusion_matrix(y[m], pred[m], labels=[0, 1]).ravel()
    return {
        "recall": round(tp / (tp + fn), 3) if (tp + fn) else 0.0,
        "fpr": round(fp / (fp + tn), 3) if (fp + tn) else 0.0,
    }


def main() -> None:
    df = pd.read_csv(EVAL).dropna(subset=["text", "label"])
    df["label"] = df["label"].astype(int)
    y = df["label"].to_numpy()
    texts = df["text"].astype(str).tolist()

    # Our systems
    ml_proba = rana_model.predict_proba(texts) if rana_model.is_available() else None
    flag_set = (GuardrailDecision.BLOCK, GuardrailDecision.REVIEW)
    det_flag = [analyze(t).decision in flag_set for t in texts]
    det_pred = pd.Series(det_flag).astype(int).to_numpy()

    systems = {"RANA deterministic layer (analyze)": det_pred}
    if ml_proba is not None:
        ml_pred = (pd.Series(ml_proba) >= THRESHOLD).astype(int).to_numpy()
        combined = ((pd.Series(ml_proba) >= THRESHOLD) | pd.Series(det_flag)).astype(int).to_numpy()
        systems = {
            "RANA ML (TF-IDF+LR)": ml_pred,
            "RANA deterministic layer (analyze)": det_pred,
            "RANA combined (ML or deterministic)": combined,
        }

    cats = ["Multilingual Prompt Injection", "Encoded / Obfuscated Prompt Injection"]
    ours = {}
    for name, pred in systems.items():
        ours[name] = {
            "overall": _metrics(y, pred),
            "cats": {c: _cat_recall_fpr(df, y, pred, c) for c in cats},
        }

    # Stored previous benchmark
    stored = json.loads(STORED.read_text(encoding="utf-8"))
    prev = {}
    for sid in ("our_ml_detector", "llm_guard", "llama_prompt_guard"):
        r = stored["results"][sid]
        m = r["metrics"]
        prev[r.get("name", sid)] = {
            "overall": {
                "accuracy": round(m["accuracy"], 3),
                "precision": round(m["precision"], 3),
                "recall": round(m["recall"], 3),
                "f1": round(m["f1"], 3),
                "fpr": round(m["false_positive_rate"], 3),
            },
            "cats": {c: r.get("per_category_results", {}).get(c, {}) for c in cats},
        }

    # ---- write report ----
    L = [
        "# Updated code vs previous benchmark — eval_dataset_v2.csv (1000 rows)",
        "",
        "All systems evaluated on the SAME held-out set. 'Previous' rows are from",
        "experiments/results/guardrail_comparison.json (intern-run; the intern ML number",
        "is self-reported and does NOT reproduce on a current scikit-learn). 'RANA*' rows",
        "are freshly computed by this script.",
        "",
        "## Overall",
        "| System | acc | precision | recall | f1 | FPR |",
        "|---|---|---|---|---|---|",
    ]

    def row(name, o):
        return (
            f"| {name} | {o['accuracy']} | {o['precision']} | "
            f"{o['recall']} | {o['f1']} | {o['fpr']} |"
        )

    for name, d in ours.items():
        L.append(row("**" + name + "**", d["overall"]))
    for name, d in prev.items():
        L.append(row(name + " (previous)", d["overall"]))

    for c in cats:
        L += [
            "",
            f"## {c} — recall (higher=better) / FPR (lower=better)",
            "| System | recall | FPR |",
            "|---|---|---|",
        ]
        for name, d in ours.items():
            cc = d["cats"][c]
            if cc:
                L.append(f"| **{name}** | {cc.get('recall')} | {cc.get('fpr')} |")
        for name, d in prev.items():
            cc = d["cats"][c] or {}
            rec = cc.get("recall", cc.get("metrics", {}).get("recall"))
            fpr = cc.get("false_positive_rate", cc.get("metrics", {}).get("false_positive_rate"))
            L.append(f"| {name} (previous) | {rec} | {fpr} |")

    L += [
        "",
        "## Notes",
        "- Deterministic layer needs no training and no model; it targets encoded/obfuscated",
        "  and structural attacks and runs on any language.",
        "- Combined detector unions the ML and deterministic signals (recall up, FPR up).",
        "- Multilingual is the open gap (B3); see scripts/augment_multilingual.py.",
        "- Reproduce: python scripts/benchmark_compare.py",
    ]
    REPORT.write_text("\n".join(L), encoding="utf-8")

    print("Wrote", REPORT)
    for name, d in ours.items():
        print(name, d["overall"])


if __name__ == "__main__":
    main()
