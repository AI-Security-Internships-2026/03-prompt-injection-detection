"""
generate_figures.py - regenerates all 4 paper figures directly from
verified raw CSVs in results/sglang/. No manual/unsourced images used.
"""
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang"))
OUT = os.path.dirname(__file__)

def recompute_full_pin_accuracy(path):
    """Reproduces recover_pin()'s tie-break exactly: first guess (0..9 order)
    with strictly-greatest cached_tokens wins each position."""
    df = pd.read_csv(path, dtype={"ground_truth_pin": str, "guess_digit": str, "ground_truth_digit_this_position": str, "known_prefix_so_far": str})
    n_correct = 0
    n_trials = df["trial"].nunique()
    for trial, tdf in df.groupby("trial"):
        recovered = ""
        gt = None
        for position, pdf_ in tdf.groupby("position"):
            pdf_ = pdf_.sort_values("guess_digit")  # preserve 0..9 probe order
            best_row = pdf_.loc[pdf_["cached_tokens"].idxmax()]
            recovered += str(best_row["guess_digit"])
            gt = best_row["ground_truth_pin"]
        if recovered == str(gt):
            n_correct += 1
    return n_correct, n_trials

# ---------- Figure: accuracy ----------
baseline_correct, baseline_n = recompute_full_pin_accuracy(os.path.join(RESULTS, "pin_chained_recovery.csv"))
salted_correct, salted_n = recompute_full_pin_accuracy(os.path.join(RESULTS, "pin_chained_recovery_salted.csv"))
disable_radix_correct, disable_radix_n = recompute_full_pin_accuracy(os.path.join(RESULTS, "pin_chained_recovery_disable_radix.csv"))

print(f"Baseline: {baseline_correct}/{baseline_n}")
print(f"Salted: {salted_correct}/{salted_n}")
print(f"Disable-radix: {disable_radix_correct}/{disable_radix_n}")

fig, ax = plt.subplots(figsize=(6, 4))
conditions = ["Baseline", "Cache-salt", "Disable-radix"]
accs = [baseline_correct/baseline_n*100, salted_correct/salted_n*100, disable_radix_correct/disable_radix_n*100]
bars = ax.bar(conditions, accs, color=["#c0392b", "#27ae60", "#2980b9"])
for b, a in zip(bars, accs):
    ax.text(b.get_x()+b.get_width()/2, a+2, f"{a:.1f}%", ha="center")
ax.set_ylabel("Full-PIN recovery accuracy (%)")
ax.set_ylim(0, 110)
ax.set_title("Attack accuracy, baseline vs. mitigations (N=30 each, independently re-derived)")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_accuracy.pdf"))
plt.close()

# ---------- Figure: cached_tokens ----------
df_base = pd.read_csv(os.path.join(RESULTS, "pin_chained_recovery.csv"))
df_salt = pd.read_csv(os.path.join(RESULTS, "pin_chained_recovery_salted.csv"))

fig, ax = plt.subplots(figsize=(6, 4))
ax.hist(df_base["cached_tokens"], bins=30, alpha=0.6, label="Baseline", color="#c0392b")
ax.hist(df_salt["cached_tokens"], bins=30, alpha=0.6, label="Cache-salt", color="#27ae60")
ax.set_xlabel("cached_tokens per probe")
ax.set_ylabel("Count (N=1,800 each)")
ax.set_title("Observed cached_tokens, baseline vs. cache-salt isolation")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_cached_tokens.pdf"))
plt.close()

# ---------- Figure: latency ----------
fig, ax = plt.subplots(figsize=(6, 4))
ax.hist(df_base["wall_clock_latency"], bins=40, alpha=0.6, label="Baseline", color="#c0392b", density=True)
ax.hist(df_salt["wall_clock_latency"], bins=40, alpha=0.6, label="Cache-salt", color="#27ae60", density=True)
ax.set_xlabel("Per-request wall-clock latency (s)")
ax.set_ylabel("Density")
ax.set_title("Per-request latency distribution, baseline vs. salted")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_latency.pdf"))
plt.close()

# ---------- Figure: detector (baseline, Part 1) ----------
sweep = pd.read_csv(os.path.join(RESULTS, "mitigation", "detection_threshold_sweep.csv"))
latdf = pd.read_csv(os.path.join(RESULTS, "mitigation", "detection_latency.csv"))

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
axes[0].plot(sweep["precision"].values, label="Precision", marker="o", markersize=3)
axes[0].plot(sweep["recall"].values, label="Recall", marker="s", markersize=3)
axes[0].plot(sweep["f1"].values, label="F1", marker="^", markersize=3)
axes[0].plot(sweep["fpr_shared_prefix"].values, label="FPR (shared-prefix)", marker="x", markersize=3)
axes[0].set_xlabel("Threshold pair index")
axes[0].set_ylabel("Score")
axes[0].set_title("Detector P/R/F1/FPR across thresholds")
axes[0].legend(fontsize=8)

axes[1].hist(latdf["requests_to_detect"].dropna(), bins=range(1, 14))
axes[1].set_xlabel("Requests into trial before flag")
axes[1].set_ylabel("Trial count")
axes[1].set_title(f"Detection latency (N={len(latdf)} trials)")

plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_detector.pdf"))
plt.close()

print("All 4 figures saved to", OUT)
