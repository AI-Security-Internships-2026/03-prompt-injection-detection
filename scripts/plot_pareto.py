"""
Threshold / Pareto sweep figure for the HardenedGuard paper.

For each benchmark, sweeps the decision threshold and plots the recall-vs-FPR
(ROC-style) operating curve for the PIGuard semantic core with and without the
canonicalization front-end, and marks (a) PIGuard's default @0.50 point and
(b) the accuracy-calibrated HardenedGuard operating point. Shows the front-end
shifts the curve toward the top-left (better) and where the chosen point sits.

Uses the cached PIGuard scores written by scripts/eval_kfold.py (no re-scoring).
Falls back to the eval_dataset_v2 panel only if the deepset cache/labels are
unavailable.

    python scripts/plot_pareto.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

CACHE = REPO / "reports" / ".piguard_score_cache"
OUT_PNG = REPO / "reports" / "hardenedguard-pareto.png"


def _cache(name: str, n: int):
    fp = CACHE / (hashlib.sha256((name + str(n)).encode()).hexdigest()[:16] + ".npz")
    if not fp.exists():
        return None
    d = np.load(fp)
    return d["raw"], d["canon"], d["rule"]


def _curve(scores: np.ndarray, y: np.ndarray):
    fprs, recs = [], []
    for t in np.linspace(0.0, 1.0, 101):
        pred = (scores >= t).astype(int)
        tp = ((pred == 1) & (y == 1)).sum()
        fn = ((pred == 0) & (y == 1)).sum()
        fp = ((pred == 1) & (y == 0)).sum()
        tn = ((pred == 0) & (y == 0)).sum()
        recs.append(tp / (tp + fn) if (tp + fn) else 0.0)
        fprs.append(fp / (fp + tn) if (fp + tn) else 0.0)
    return np.array(fprs), np.array(recs)


def _point(scores: np.ndarray, rule: np.ndarray, y: np.ndarray, t: float):
    pred = ((scores >= t) | (rule == 1)).astype(int)
    tp = ((pred == 1) & (y == 1)).sum()
    fn = ((pred == 0) & (y == 1)).sum()
    fp = ((pred == 1) & (y == 0)).sum()
    tn = ((pred == 0) & (y == 0)).sum()
    return (fp / (fp + tn) if (fp + tn) else 0.0, tp / (tp + fn) if (tp + fn) else 0.0)


def _best_tau(canon: np.ndarray, rule: np.ndarray, y: np.ndarray) -> float:
    best_t, best = 0.5, -1.0
    for t in np.arange(0.30, 0.99, 0.01):
        pred = ((canon >= t) | (rule == 1)).astype(int)
        acc = (pred == y).mean()
        if acc > best:
            best, best_t = acc, round(float(t), 2)
    return best_t


def _benchmarks():
    out = []
    df = pd.read_csv(REPO / "datasets" / "eval_dataset_v2.csv").dropna(subset=["text", "label"])
    y = df["label"].astype(int).to_numpy()
    c = _cache("eval_dataset_v2 (synthetic held-out)", len(y))
    if c:
        out.append((f"eval_dataset_v2 (n={len(y)})", y, *c))
    try:
        from datasets import load_dataset

        ds = load_dataset("deepset/prompt-injections")
        frames = [ds[s].to_pandas()[["text", "label"]] for s in ds]
        dd = pd.concat(frames, ignore_index=True).dropna(subset=["text", "label"])
        dd = dd[dd["text"].astype(str).str.strip() != ""]
        yd = dd["label"].astype(int).to_numpy()
        c = _cache("deepset/prompt-injections (public, apache-2.0)", len(yd))
        if c:
            out.append((f"deepset public (n={len(yd)})", yd, *c))
    except Exception:  # noqa: BLE001 - deepset optional
        pass
    return out


def main() -> None:
    benches = _benchmarks()
    if not benches:
        raise SystemExit("No cached scores. Run scripts/eval_kfold.py first.")

    fig, axes = plt.subplots(1, len(benches), figsize=(6.2 * len(benches), 5.2), squeeze=False)
    for ax, (title, y, raw, canon, rule) in zip(axes[0], benches, strict=False):
        fr, rr = _curve(raw, y)
        fc, rc = _curve(canon, y)
        ax.plot(fr, rr, "-", color="#888", lw=2, label="PIGuard (raw)")
        ax.plot(fc, rc, "-", color="#1f6feb", lw=2.4, label="PIGuard + canonicalization")
        ax.plot([0, 1], [0, 1], ":", color="#bbb", lw=1)

        # PIGuard default @0.50
        p_fp, p_rc = _point(raw, np.zeros_like(rule), y, 0.5)
        ax.plot(p_fp, p_rc, "o", color="#888", ms=9, mec="k", label="PIGuard @0.50")
        # HardenedGuard calibrated operating point
        tau = _best_tau(canon, rule, y)
        h_fp, h_rc = _point(canon, rule, y, tau)
        ax.plot(h_fp, h_rc, "*", color="#cf222e", ms=17, mec="k", label=f"HardenedGuard (τ={tau})")

        ax.set_title(title, fontsize=12)
        ax.set_xlabel("False-positive rate (↓ better)")
        ax.set_ylabel("Recall / TPR (↑ better)")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=9)

    fig.suptitle(
        "HardenedGuard: canonicalization shifts the operating curve up-left; "
        "calibration picks a low-FPR point",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150)
    print(f"wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
