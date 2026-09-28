"""
Paper-ready evaluation of HardenedGuard (rigorous, leakage-free).

Fixes the calibration-on-test bias: the decision threshold is tuned on a held-out
CALIBRATION split and all headline numbers are reported on a DISJOINT TEST split.
Reports an ablation (raw -> +canonicalize -> +calibrated threshold -> +rule veto),
bootstrap 95% confidence intervals, a McNemar paired-significance test vs PIGuard,
and per-category recall.

Deterministic (seed 42). Needs the guards extra + a local PIGuard download.
Writes a JSON of results next to the script's stdout.

    python scripts/eval_paper.py
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
from scipy.stats import chi2  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from canonicalize import canonicalize  # noqa: E402
from detection_utils import GuardrailDecision, analyze  # noqa: E402

EVAL = REPO / "datasets" / "eval_dataset_v2.csv"
OUT = REPO / "reports" / "hardenedguard-paper-results.json"
SEED = 42
N_BOOT = 2000


def confusion(pred: np.ndarray, y: np.ndarray) -> tuple[int, int, int, int]:
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return tp, tn, fp, fn


def metrics(pred: np.ndarray, y: np.ndarray) -> dict[str, float]:
    tp, tn, fp, fn = confusion(pred, y)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "acc": (tp + tn) / len(y),
        "prec": prec,
        "rec": rec,
        "f1": 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0,
        "fpr": fp / (fp + tn) if (fp + tn) else 0.0,
    }


def boot_ci(
    pred: np.ndarray, y: np.ndarray, key: str, rng: np.random.Generator
) -> tuple[float, float]:
    n = len(y)
    vals = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, n)
        vals.append(metrics(pred[idx], y[idx])[key])
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return round(float(lo), 3), round(float(hi), 3)


def mcnemar(pred_a: np.ndarray, pred_b: np.ndarray, y: np.ndarray) -> dict[str, float]:
    a_ok = pred_a == y
    b_ok = pred_b == y
    b = int((a_ok & ~b_ok).sum())  # A right, B wrong
    c = int((~a_ok & b_ok).sum())  # A wrong, B right
    stat = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) else 0.0
    p = float(chi2.sf(stat, 1))
    return {
        "b_A_right_B_wrong": b,
        "c_A_wrong_B_right": c,
        "chi2": round(stat, 3),
        "p_value": round(p, 5),
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(EVAL).dropna(subset=["text", "label"]).reset_index(drop=True)
    df["label"] = df["label"].astype(int)
    y = df["label"].to_numpy()

    # Stratified 50/50 calibration/test split.
    i0, i1 = np.where(y == 0)[0].copy(), np.where(y == 1)[0].copy()
    rng.shuffle(i0)
    rng.shuffle(i1)
    cal = np.concatenate([i0[: len(i0) // 2], i1[: len(i1) // 2]])
    test = np.concatenate([i0[len(i0) // 2 :], i1[len(i1) // 2 :]])

    name = "leolee99/PIGuard"
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModelForSequenceClassification.from_pretrained(name, trust_remote_code=True)
    model.eval()

    def pig(text: str) -> float:
        with torch.no_grad():
            lg = model(**tok(text, return_tensors="pt", truncation=True, max_length=512)).logits
            return float(torch.softmax(lg, dim=-1)[0][1])

    print(f"scoring {len(df)} rows x2 (raw + canonical) through PIGuard ...", flush=True)
    raw = np.array([pig(t) for t in df["text"].astype(str)])
    canon = np.array([pig(canonicalize(t)) for t in df["text"].astype(str)])
    rule_block = np.array(
        [
            analyze(canonicalize(t)).decision is GuardrailDecision.BLOCK
            for t in df["text"].astype(str)
        ],
        dtype=int,
    )

    # Calibrate threshold on CAL split only (maximize accuracy).
    best_t, best_acc = 0.5, -1.0
    for t in np.arange(0.30, 0.99, 0.01):
        pred = ((canon[cal] >= t) | (rule_block[cal] == 1)).astype(int)
        acc = metrics(pred, y[cal])["acc"]
        if acc > best_acc:
            best_acc, best_t = acc, round(float(t), 2)

    systems = {
        "PIGuard raw @0.50": (raw >= 0.5).astype(int),
        "+ canonicalize @0.50": (canon >= 0.5).astype(int),
        f"+ calibrated threshold @{best_t}": (canon >= best_t).astype(int),
        f"HardenedGuard (canon@{best_t} OR rule-BLOCK)": (
            (canon >= best_t) | (rule_block == 1)
        ).astype(int),
    }

    results = {
        "seed": SEED,
        "calibration_threshold": best_t,
        "n_test": int(len(test)),
        "systems": {},
    }
    print(f"\ncalibrated threshold (on CAL split) = {best_t}\n")
    print(f"{'system':<44}{'acc [95% CI]':>22}{'F1':>7}{'FPR':>7}{'rec':>7}")
    print("-" * 87)
    for label, pred in systems.items():
        m = metrics(pred[test], y[test])
        lo, hi = boot_ci(pred[test], y[test], "acc", np.random.default_rng(SEED))
        results["systems"][label] = {k: round(v, 3) for k, v in m.items()} | {"acc_ci": [lo, hi]}
        cell = f"{m['acc']:.3f} [{lo},{hi}]"
        print(f"{label:<44}{cell:>22}{m['f1']:>7.3f}{m['fpr']:>7.3f}{m['rec']:>7.3f}")

    hardened = list(systems.values())[-1]
    mc = mcnemar(systems["PIGuard raw @0.50"][test], hardened[test], y[test])
    results["mcnemar_hardened_vs_piguard"] = mc
    print(
        f"\nMcNemar HardenedGuard vs PIGuard raw (test): chi2={mc['chi2']} p={mc['p_value']} "
        f"(A_right_B_wrong={mc['b_A_right_B_wrong']}, A_wrong_B_right={mc['c_A_wrong_B_right']})"
    )

    # Per-category recall on TEST.
    results["per_category"] = {}
    if "attack_type" in df.columns:
        print(f"\n{'category (test)':<42}{'PIGuard rec':>12}{'Hardened rec':>13}")
        print("-" * 67)
        for cat in sorted(df["attack_type"].dropna().unique()):
            m = (df.iloc[test]["attack_type"] == cat).to_numpy()
            if not m.any():
                continue
            yt = y[test][m]
            rr = metrics(systems["PIGuard raw @0.50"][test][m], yt)["rec"]
            hr = metrics(hardened[test][m], yt)["rec"]
            results["per_category"][cat] = {
                "piguard_rec": round(rr, 3),
                "hardened_rec": round(hr, 3),
            }
            print(f"{cat:<42}{rr:>12.3f}{hr:>13.3f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nJSON -> {OUT}")


if __name__ == "__main__":
    main()
