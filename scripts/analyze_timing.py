import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

df = pd.read_csv("results/timing_characterization.csv")
summary = df.groupby("match_frac")["latency_ms"].agg(["mean", "std", "count"])
print(summary)

hit = df[df.match_frac == 1.0]["latency_ms"]
miss = df[df.match_frac == 0.0]["latency_ms"]
d = (miss.mean() - hit.mean()) / ((hit.std()**2 + miss.std()**2) / 2) ** 0.5
print(f"\nCohen's d (miss vs hit): {d:.3f}")

t, p = stats.ttest_ind(miss, hit)
print(f"t-test: t={t:.3f}, p={p:.2e}")

plt.figure(figsize=(7,5))
summary["mean"].plot(marker="o", yerr=summary["std"], capsize=4)
plt.xlabel("Prefix match fraction")
plt.ylabel("TTFT (ms)")
plt.title("TTFT vs prefix-match depth (DeepSeek-R1-Distill-Llama-8B, vLLM 0.26.0)")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("results/timing_vs_match_depth.png", dpi=150)
print("\nSaved plot to results/timing_vs_match_depth.png")
