"""
compute_metrics.py — Stage 2 statistical analysis.
Computes descriptive stats + effect sizes across fresh/repeat/modified conditions.
Excludes the true cold-start request (trial 0 of 'fresh') from the main comparison,
reporting it separately since it is not part of the repeated-measures noise floor.
"""
import csv
import os
import numpy as np
from scipy import stats

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "single_tenant_raw.csv")

def load():
    rows = []
    with open(IN_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["wall_clock_latency"] = float(r["wall_clock_latency"])
            r["cached_tokens"] = int(r["cached_tokens"])
            r["prompt_tokens"] = int(r["prompt_tokens"])
            r["trial"] = int(r["trial"])
            rows.append(r)
    return rows

def describe(name, values):
    values = np.array(values)
    n = len(values)
    mean = values.mean()
    median = np.median(values)
    std = values.std(ddof=1) if n > 1 else float("nan")
    sem = std / np.sqrt(n) if n > 1 else float("nan")
    ci95 = 1.96 * sem if n > 1 else float("nan")
    print(f"{name}: n={n} mean={mean:.5f}s median={median:.5f}s std={std:.5f}s 95% CI=±{ci95:.5f}s")
    return values

def cohens_d(a, b):
    a, b = np.array(a), np.array(b)
    na, nb = len(a), len(b)
    pooled_std = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if pooled_std == 0:
        return float("inf") if a.mean() != b.mean() else 0.0
    return (a.mean() - b.mean()) / pooled_std

def compare(name_a, a, name_b, b):
    d = cohens_d(a, b)
    # Check normality-ish via Shapiro before picking t-test vs Mann-Whitney
    try:
        _, p_norm_a = stats.shapiro(a)
        _, p_norm_b = stats.shapiro(b)
    except Exception:
        p_norm_a = p_norm_b = 0.0
    if p_norm_a > 0.05 and p_norm_b > 0.05:
        stat, p = stats.ttest_ind(a, b, equal_var=False)
        test_used = "Welch t-test"
    else:
        stat, p = stats.mannwhitneyu(a, b, alternative="two-sided")
        test_used = "Mann-Whitney U"
    print(f"\n{name_a} vs {name_b}: Cohen's d={d:.4f}, {test_used} stat={stat:.4f}, p={p:.6g}")

def main():
    rows = load()

    fresh_cold = [r["wall_clock_latency"] for r in rows if r["condition"] == "fresh" and r["trial"] == 0]
    fresh_warm = [r["wall_clock_latency"] for r in rows if r["condition"] == "fresh" and r["trial"] > 0]
    repeat = [r["wall_clock_latency"] for r in rows if r["condition"] == "repeat"]
    modified = [r["wall_clock_latency"] for r in rows if r["condition"] == "modified"]

    print("=== DESCRIPTIVE STATS ===")
    print(f"fresh[0] (cold, n=1): {fresh_cold[0]:.5f}s  <- excluded from inferential tests, n=1")
    describe("fresh_warm (trials 1-9)", fresh_warm)
    describe("repeat", repeat)
    describe("modified", modified)

    print("\n=== CACHE-HIT FRACTION BY CONDITION ===")
    for cond in ["fresh", "repeat", "modified"]:
        fracs = [r["cached_tokens"] / r["prompt_tokens"] for r in rows if r["condition"] == cond]
        print(f"{cond}: mean cache-hit fraction = {np.mean(fracs):.4f} (n={len(fracs)})")

    print("\n=== PAIRWISE COMPARISONS (warm conditions only) ===")
    compare("fresh_warm", fresh_warm, "repeat", repeat)
    compare("repeat", repeat, "modified", modified)
    compare("fresh_warm", fresh_warm, "modified", modified)

if __name__ == "__main__":
    main()
