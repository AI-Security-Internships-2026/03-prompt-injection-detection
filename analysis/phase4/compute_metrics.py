import pandas as pd
df = pd.read_csv("results/phase4/ablation_results.csv")
summary = df.groupby(["secret_category", "tenant", "trial_batch"])["confidence"].mean().reset_index()
print(summary.to_string(index=False))
summary.to_csv("results/phase4/summary_metrics.csv", index=False)
