"""
compute_metrics_mitigation.py — significance stats comparing baseline
(unmitigated) vs. cache-salt-mitigated PIN recovery attack data.

New script (no prior version existed — confirmed via repo search before
writing). Reuses the cohens_d() implementation verified in
compute_metrics_crosstenant.py.

Compares cached_tokens (the direct cross-tenant leakage signal) between:
  - baseline: results/sglang/pin_chained_recovery.csv        (100% attack success)
  - salted:   results/sglang/pin_chained_recovery_salted.csv (0% attack success)

NOTE: the salted condition has cached_tokens == 0 on every row (zero
variance), so Cohen's d is mathematically undefined / infinite — this
script reports that explicitly rather than masking it, since it is the
correct statistical description of two fully non-overlapping
distributions, not a computation error.
"""
import csv
import os
import numpy as np
from scipy import stats

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "pin_chained_recovery.csv")
SALTED_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "pin_chained_recovery_salted.csv")

def load(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            r["cached_tokens"] = int(r["cached_tokens"])
            r["wall_clock_latency"] = float(r["wall_clock_latency"])
            rows.append(r)
    return rows

def cohens_d(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    pooled = np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
    return (a.mean()-b.mean())/pooled if pooled else float("inf")

def run():
    baseline_rows = load(BASELINE_PATH)
    salted_rows = load(SALTED_PATH)

    baseline_cache = [r["cached_tokens"] for r in baseline_rows]
    salted_cache = [r["cached_tokens"] for r in salted_rows]

    print("=== CACHED_TOKENS (direct cross-tenant leakage signal) ===")
    print(f"baseline: n={len(baseline_cache)}, mean={np.mean(baseline_cache):.1f}, std={np.std(baseline_cache, ddof=1):.3f}")
    print(f"salted:   n={len(salted_cache)}, mean={np.mean(salted_cache):.1f}, std={np.std(salted_cache, ddof=1):.3f}")

    if np.std(salted_cache, ddof=1) == 0:
        print("\nNOTE: salted condition has ZERO variance (cached_tokens==0 on every row).")
        print("Cohen's d is mathematically undefined/infinite for two fully")
        print("non-overlapping, one-degenerate distributions. This IS the correct")
        print("statistical statement of complete separation, not a bug.")

    d = cohens_d(baseline_cache, salted_cache)
    stat, p = stats.mannwhitneyu(baseline_cache, salted_cache, alternative="two-sided")
    print(f"\nCohen's d = {d}")
    print(f"Mann-Whitney U = {stat}, p = {p:.6g}")

    print("\n=== WALL-CLOCK LATENCY (secondary check: mitigation shouldn't need to change probe timing) ===")
    baseline_lat = [r["wall_clock_latency"] for r in baseline_rows]
    salted_lat = [r["wall_clock_latency"] for r in salted_rows]
    print(f"baseline: mean={np.mean(baseline_lat):.5f}s std={np.std(baseline_lat, ddof=1):.5f}s")
    print(f"salted:   mean={np.mean(salted_lat):.5f}s std={np.std(salted_lat, ddof=1):.5f}s")
    d_lat = cohens_d(baseline_lat, salted_lat)
    stat_lat, p_lat = stats.mannwhitneyu(baseline_lat, salted_lat, alternative="two-sided")
    print(f"Cohen's d (latency) = {d_lat:.4f}, Mann-Whitney p = {p_lat:.6g}")

if __name__ == "__main__":
    run()
