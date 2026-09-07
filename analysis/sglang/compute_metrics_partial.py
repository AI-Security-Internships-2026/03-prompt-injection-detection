import csv, os
import numpy as np
from scipy import stats

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "partial_cache_raw_v4.csv")

rows = []
with open(IN_PATH, newline="") as f:
    for r in csv.DictReader(f):
        r["wall_clock_latency"] = float(r["wall_clock_latency"])
        rows.append(r)

repeat = [r["wall_clock_latency"] for r in rows if r["condition"] == "repeat"]
modified = [r["wall_clock_latency"] for r in rows if r["condition"] == "modified"]

def cohens_d(a, b):
    a, b = np.array(a), np.array(b)
    pooled = np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
    return (a.mean()-b.mean())/pooled if pooled else float("inf")

print(f"repeat: n={len(repeat)} mean={np.mean(repeat):.5f}s std={np.std(repeat, ddof=1):.5f}s median={np.median(repeat):.5f}s")
print(f"modified: n={len(modified)} mean={np.mean(modified):.5f}s std={np.std(modified, ddof=1):.5f}s median={np.median(modified):.5f}s")

d = cohens_d(repeat, modified)
stat, p = stats.mannwhitneyu(repeat, modified, alternative="two-sided")
print(f"\nrepeat vs modified: Cohen's d={d:.4f}, Mann-Whitney p={p:.6g}")

# Also without the modified[9] outlier, to check sensitivity
modified_no_outlier = sorted(modified)[:-1]
d2 = cohens_d(repeat, modified_no_outlier)
stat2, p2 = stats.mannwhitneyu(repeat, modified_no_outlier, alternative="two-sided")
print(f"repeat vs modified (excl. top outlier): Cohen's d={d2:.4f}, Mann-Whitney p={p2:.6g}")
