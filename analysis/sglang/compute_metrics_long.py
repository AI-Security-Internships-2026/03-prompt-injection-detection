import csv, os
import numpy as np
from scipy import stats

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "single_tenant_long_raw.csv")

def load():
    rows = []
    with open(IN_PATH, newline="") as f:
        for r in csv.DictReader(f):
            r["wall_clock_latency"] = float(r["wall_clock_latency"])
            r["trial"] = int(r["trial"])
            rows.append(r)
    return rows

def cohens_d(a, b):
    a, b = np.array(a), np.array(b)
    pooled = np.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
    return (a.mean()-b.mean())/pooled if pooled else float("inf")

rows = load()
fresh_cold = [r["wall_clock_latency"] for r in rows if r["condition"]=="fresh" and r["trial"]==0]
fresh_warm = [r["wall_clock_latency"] for r in rows if r["condition"]=="fresh" and r["trial"]>0]
repeat = [r["wall_clock_latency"] for r in rows if r["condition"]=="repeat"]
modified = [r["wall_clock_latency"] for r in rows if r["condition"]=="modified"]

print(f"cold (n=1): {fresh_cold[0]:.4f}s")
for name, vals in [("fresh_warm", fresh_warm), ("repeat", repeat), ("modified", modified)]:
    v = np.array(vals)
    print(f"{name}: mean={v.mean():.5f}s std={v.std(ddof=1):.5f}s")

print(f"\ncold vs warm Cohen's d = {cohens_d(fresh_cold*9, fresh_warm):.4f}  (n=1 vs n=9, illustrative only)")
d_rm = cohens_d(repeat, modified)
stat, p = stats.mannwhitneyu(repeat, modified, alternative="two-sided")
print(f"repeat vs modified: Cohen's d={d_rm:.4f}, Mann-Whitney p={p:.4f}")
print("\nNOTE: modified condition only differed from repeat by ~1 cached token out of ~1211 —")
print("insufficient prefix divergence to test partial-cache-hit timing. Flag for future ablation.")
