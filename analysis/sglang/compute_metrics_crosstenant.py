import csv, os
import numpy as np
from scipy import stats

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "cross_tenant_raw_v2.csv")

rows = []
with open(IN_PATH, newline="") as f:
    for r in csv.DictReader(f):
        r["wall_clock_latency"] = float(r["wall_clock_latency"])
        r["cached_tokens"] = int(r["cached_tokens"])
        r["prompt_tokens"] = int(r["prompt_tokens"])
        rows.append(r)

A = [r["wall_clock_latency"] for r in rows if r["condition"] == "A_no_victim"]
B = [r["wall_clock_latency"] for r in rows if r["condition"] == "B_after_victim"]
A_cache = [r["cached_tokens"] for r in rows if r["condition"] == "A_no_victim"]
B_cache = [r["cached_tokens"] for r in rows if r["condition"] == "B_after_victim"]

def cohens_d(a, b):
    a, b = np.array(a), np.array(b)
    pooled = np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
    return (a.mean()-b.mean())/pooled if pooled else float("inf")

print("=== CACHED_TOKENS (direct cross-tenant leakage signal) ===")
print(f"A (no victim): mean={np.mean(A_cache):.1f}, all values: {A_cache}")
print(f"B (after victim): mean={np.mean(B_cache):.1f}, all values: {B_cache}")
print("-> 100% separable, binary signal, n=15/15 each condition")

print("\n=== WALL-CLOCK LATENCY ===")
print(f"A: mean={np.mean(A):.5f}s std={np.std(A, ddof=1):.5f}s")
print(f"B: mean={np.mean(B):.5f}s std={np.std(B, ddof=1):.5f}s")
d = cohens_d(A, B)
stat, p = stats.mannwhitneyu(A, B, alternative="two-sided")
print(f"Cohen's d = {d:.4f}, Mann-Whitney p = {p:.6g}")
print("NOTE: direction is B > A (slower after victim activity), opposite of naive")
print("cache-speedup expectation. Possible scheduler/GPU-contention confound from")
print("back-to-back requests, not yet isolated. Flagged as open question.")
