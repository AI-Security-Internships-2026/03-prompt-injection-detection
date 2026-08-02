"""
K-fold cross-validated HardenedGuard evaluation on TWO benchmarks.

Strengthens external validity beyond the single split in scripts/eval_paper.py:
  * stratified 5-fold CV — the decision threshold is calibrated on the training
    folds and evaluated on the held-out fold (never tuned on data it is scored
    on), aggregated as mean +/- std across folds;
  * a SECOND, independent public benchmark (deepset/prompt-injections, apache-2.0)
    in addition to the project's eval_dataset_v2;
  * pooled out-of-fold McNemar significance vs the PIGuard baseline.

PIGuard scores are cached per dataset (scratchpad .npz) so re-runs are instant.
Needs the guards + data extras and a local PIGuard download. Deterministic (seed 42).

    python scripts/eval_kfold.py
"""

from __future__ import annotations

import hashlib
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from scipy.stats import chi2  # noqa: E402
from sklearn.model_selection import StratifiedKFold  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
from canonicalize import canonicalize  # noqa: E402
from detection_utils import GuardrailDecision, analyze  # noqa: E402

SEED = 42
K = 5
CACHE = Path(__file__).resolve().parent.parent / "reports" / ".piguard_score_cache"


def _metrics(pred: np.ndarray, y: np.ndarray) -> dict[str, float]:
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "acc": (tp + tn) / len(y),
        "f1": 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0,
        "fpr": fp / (fp + tn) if (fp + tn) else 0.0,
        "rec": rec,
    }


def _mcnemar_p(a: np.ndarray, b: np.ndarray, y: np.ndarray) -> tuple[float, int, int]:
    a_ok, b_ok = a == y, b == y
    nb = int((a_ok & ~b_ok).sum())
    nc = int((~a_ok & b_ok).sum())
    stat = (abs(nb - nc) - 1) ** 2 / (nb + nc) if (nb + nc) else 0.0
    return round(float(chi2.sf(stat, 1)), 5), nb, nc


def _load_benchmarks() -> dict[str, tuple[list[str], np.ndarray]]:
    out: dict[str, tuple[list[str], np.ndarray]] = {}
    df = pd.read_csv(REPO / "datasets" / "eval_dataset_v2.csv").dropna(subset=["text", "label"])
    out["eval_dataset_v2 (synthetic held-out)"] = (
        df["text"].astype(str).tolist(),
        df["label"].astype(int).to_numpy(),
    )
    from datasets import load_dataset

    ds = load_dataset("deepset/prompt-injections")
    frames = [ds[s].to_pandas()[["text", "label"]] for s in ds]
    dd = pd.concat(frames, ignore_index=True).dropna(subset=["text", "label"])
    dd = dd[dd["text"].astype(str).str.strip() != ""]
    out["deepset/prompt-injections (public, apache-2.0)"] = (
        dd["text"].astype(str).tolist(),
        dd["label"].astype(int).to_numpy(),
    )
    return out


def _scores(name: str, texts: list[str], pig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((name + str(len(texts))).encode()).hexdigest()[:16]
    fp = CACHE / f"{key}.npz"
    if fp.exists():
        d = np.load(fp)
        return d["raw"], d["canon"], d["rule"]
    print(f"  scoring {len(texts)} rows x2 through PIGuard ...", flush=True)
    raw = np.array([pig(t) for t in texts])
    canon = np.array([pig(canonicalize(t)) for t in texts])
    rule = np.array(
        [analyze(canonicalize(t)).decision is GuardrailDecision.BLOCK for t in texts], dtype=int
    )
    np.savez(fp, raw=raw, canon=canon, rule=rule)
    return raw, canon, rule


def main() -> None:
    name = "leolee99/PIGuard"
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModelForSequenceClassification.from_pretrained(name, trust_remote_code=True)
    model.eval()

    def pig(text: str) -> float:
        with torch.no_grad():
            lg = model(**tok(text, return_tensors="pt", truncation=True, max_length=512)).logits
            return float(torch.softmax(lg, dim=-1)[0][1])

    print(f"{'benchmark':<44}{'system':<16}{'acc (mean+/-std)':>20}{'F1':>7}{'FPR':>7}")
    print("=" * 94)
    for bench, (texts, y) in _load_benchmarks().items():
        raw, canon, rule = _scores(bench, texts, pig)
        skf = StratifiedKFold(n_splits=K, shuffle=True, random_state=SEED)
        pig_oof = np.zeros(len(y), int)
        hard_oof = np.zeros(len(y), int)
        fold: dict[str, list[dict[str, float]]] = {"pig": [], "hard": []}
        taus = []
        for tr, te in skf.split(np.zeros(len(y)), y):
            best_t, best = 0.5, -1.0
            for t in np.arange(0.30, 0.99, 0.01):
                p = ((canon[tr] >= t) | (rule[tr] == 1)).astype(int)
                a = _metrics(p, y[tr])["acc"]
                if a > best:
                    best, best_t = a, round(float(t), 2)
            taus.append(best_t)
            pig_oof[te] = (raw[te] >= 0.5).astype(int)
            hard_oof[te] = ((canon[te] >= best_t) | (rule[te] == 1)).astype(int)
            fold["pig"].append(_metrics(pig_oof[te], y[te]))
            fold["hard"].append(_metrics(hard_oof[te], y[te]))

        def agg(rows: list[dict[str, float]], k: str) -> str:
            v = np.array([r[k] for r in rows])
            return f"{v.mean():.3f}+/-{v.std():.3f}"

        p, nb, nc = _mcnemar_p(pig_oof, hard_oof, y)
        print(
            f"{bench:<44}{'PIGuard raw':<16}{agg(fold['pig'], 'acc'):>20}"
            f"{np.mean([r['f1'] for r in fold['pig']]):>7.3f}"
            f"{np.mean([r['fpr'] for r in fold['pig']]):>7.3f}"
        )
        print(
            f"{'':<44}{'HardenedGuard':<16}{agg(fold['hard'], 'acc'):>20}"
            f"{np.mean([r['f1'] for r in fold['hard']]):>7.3f}"
            f"{np.mean([r['fpr'] for r in fold['hard']]):>7.3f}"
        )
        print(
            f"{'':<44}(n={len(y)}, tau in {sorted(set(taus))}; "
            f"pooled McNemar p={p}, corrected={nc}/broke={nb})"
        )
        print("-" * 94)


if __name__ == "__main__":
    main()
