import csv, os
import numpy as np
from scipy import stats

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "cross_tenant_gap_sweep.csv")

rows = []
with open(IN_PATH, newline="") as f:
    for r in csv.DictReader(f):
        r["wall_clock_latency"] = float(r["wall_clock_latency"])
        r["gap_seconds"] = float(r["gap_seconds"])
        rows.append(r)

def cohens_d(a, b):
    a, b = np.array(a), np.array(b)
    pooled = np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
    return (a.mean()-b.mean())/pooled if pooled else float("inf")

for gap in [0, 1, 3, 5]:
    A = [r["wall_clock_latency"] for r in rows if r["condition"]=="A_no_victim" and r["gap_seconds"]==gap]
    B = [r["wall_clock_latency"] for r in rows if r["condition"]=="B_after_victim" and r["gap_seconds"]==gap]
    d = cohens_d(A, B)
    stat, p = stats.mannwhitneyu(A, B, alternative="two-sided")
    direction = "B > A (anomaly)" if np.mean(B) > np.mean(A) else "B < A (expected cache speedup)"
    print(f"gap={gap}s: A_mean={np.mean(A):.5f}s B_mean={np.mean(B):.5f}s d={d:.4f} p={p:.6g}  -> {direction}")
