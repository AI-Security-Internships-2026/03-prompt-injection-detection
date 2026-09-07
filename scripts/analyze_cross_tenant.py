import pandas as pd
from scipy import stats

df = pd.read_csv("results/cross_tenant_verification.csv")

t, p = stats.ttest_rel(df["before_ms"], df["after_ms"])
print(f"Paired t-test (before vs after): t={t:.3f}, p={p:.5f}")

mean_delta = df["delta_ms"].mean()
std_delta = df["delta_ms"].std()
d = mean_delta / std_delta
print(f"Mean delta: {mean_delta:.2f}ms, stdev: {std_delta:.2f}ms")
print(f"Cohen's d (paired): {d:.3f}")

consistent = (df["delta_ms"] > 0).sum()
print(f"Hit-consistent trials: {consistent}/{len(df)} ({100*consistent/len(df):.0f}%)")
