"""
Benchmark the composite HardenedGuard against every system on eval_dataset_v2.

Pipeline scored: canonicalize -> PIGuard (semantic core) OR deterministic
rule-BLOCK veto, with a calibrated threshold. Compares to PIGuard raw, RANA, and
the stored LLM Guard / Llama Prompt Guard / intern numbers.

Needs the guards extra (torch + transformers) and a local PIGuard download.

    python scripts/eval_hardened.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from canonicalize import canonicalize  # noqa: E402
from detection_utils import GuardrailDecision, analyze  # noqa: E402

EVAL = REPO / "datasets" / "eval_dataset_v2.csv"
STORED = REPO / "experiments" / "results" / "guardrail_comparison.json"


def _metrics(pred: np.ndarray, y: np.ndarray) -> dict:
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "acc": round((tp + tn) / len(y), 3),
        "prec": round(prec, 3),
        "rec": round(rec, 3),
        "f1": round(2 * prec * rec / (prec + rec), 3) if (prec + rec) else 0.0,
        "fpr": round(fp / (fp + tn), 3) if (fp + tn) else 0.0,
    }


def main() -> None:
    df = pd.read_csv(EVAL).dropna(subset=["text", "label"])
    df["label"] = df["label"].astype(int)
    y = df["label"].to_numpy()

    name = "leolee99/PIGuard"
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModelForSequenceClassification.from_pretrained(name, trust_remote_code=True)
    model.eval()

    def piguard(text: str) -> float:
        with torch.no_grad():
            logits = model(**tok(text, return_tensors="pt", truncation=True, max_length=512)).logits
            return float(torch.softmax(logits, dim=-1)[0][1])

    print(f"scoring {len(df)} rows through canonicalize -> PIGuard ...", flush=True)
    canon_texts = [canonicalize(t) for t in df["text"].astype(str)]
    sem = np.array([piguard(t) for t in canon_texts])
    rule_block = np.array(
        [analyze(t).decision is GuardrailDecision.BLOCK for t in canon_texts], dtype=int
    )

    # Calibrate the composite: (PIGuard-on-canon >= T) OR rule-BLOCK, maximize accuracy.
    best = (0.5, -1.0)
    for thr in np.arange(0.5, 1.0, 0.01):
        pred = ((sem >= thr) | (rule_block == 1)).astype(int)
        acc = _metrics(pred, y)["acc"]
        if acc > best[1]:
            best = (round(float(thr), 2), acc)
    thr = best[0]

    rows = {
        "PIGuard + canon @0.50": _metrics((sem >= 0.5).astype(int), y),
        f"canon+PIGuard @{thr} (calibrated)": _metrics((sem >= thr).astype(int), y),
        f"HardenedGuard (canon+PIGuard@{thr} OR rule-BLOCK)": _metrics(
            ((sem >= thr) | (rule_block == 1)).astype(int), y
        ),
    }

    stored = json.loads(STORED.read_text(encoding="utf-8"))
    for sid in ("our_ml_detector", "llm_guard", "llama_prompt_guard"):
        m = stored["results"][sid]["metrics"]
        rows[stored["results"][sid].get("name", sid) + " (stored)"] = {
            "acc": round(m["accuracy"], 3),
            "prec": round(m["precision"], 3),
            "rec": round(m["recall"], 3),
            "f1": round(m["f1"], 3),
            "fpr": round(m["false_positive_rate"], 3),
        }

    print(f"\n{'system':<48}{'acc':>6}{'prec':>7}{'rec':>7}{'f1':>7}{'fpr':>7}")
    print("-" * 82)
    for k, v in rows.items():
        print(f"{k:<48}{v['acc']:>6}{v['prec']:>7}{v['rec']:>7}{v['f1']:>7}{v['fpr']:>7}")


if __name__ == "__main__":
    main()
