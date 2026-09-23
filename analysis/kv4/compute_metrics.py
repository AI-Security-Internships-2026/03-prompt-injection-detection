"""
compute_metrics.py — KV4 Section 4. Consumes run_level3.py-style OR
adaptive_attacker.py-style CSVs (shared core columns: trial, position,
probe_digit, wall_clock_latency, ground_truth_digit, position_guess,
position_correct; adaptive CSVs add role/prompt/timestamp, used if present).
Outputs exact-match rate, per-digit accuracy, query-count stats, latency
stats, and >=5 concrete failure cases per file.
UNVERIFIED — smoke test against an existing small CSV first.
"""
import argparse, os
import pandas as pd

def summarize_file(path):
    df = pd.read_csv(path)
    attacker_rows = df[df["role"] == "attacker"].copy() if "role" in df.columns else df.copy()
    per_trial_acc = attacker_rows.groupby("trial")["position_correct"].mean()
    exact_match = (per_trial_acc == 1.0)
    query_counts = attacker_rows.groupby("trial").size()
    lat = attacker_rows["wall_clock_latency"].describe()

    failures = []
    for trial_id, is_exact in exact_match.items():
        if not is_exact and len(failures) < 5:
            tr = attacker_rows[attacker_rows["trial"] == trial_id].drop_duplicates("position").sort_values("position")
            gt = "".join(str(int(float(x))) for x in tr["ground_truth_digit"])
            guess = "".join(str(int(float(x))) for x in tr["position_guess"])
            failures.append((trial_id, gt, guess))

    return {"path": path, "n_trials": per_trial_acc.shape[0],
            "exact_match_rate": exact_match.mean(),
            "overall_digit_accuracy": attacker_rows["position_correct"].mean(),
            "mean_queries_per_trial": query_counts.mean(),
            "latency_mean_ms": lat.get("mean", float("nan")) * 1000,
            "latency_std_ms": lat.get("std", float("nan")) * 1000,
            "failures": failures}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csvs", nargs="+", required=True)
    p.add_argument("--out-summary", required=True)
    a = p.parse_args()
    os.makedirs(os.path.dirname(a.out_summary), exist_ok=True)
    with open(a.out_summary, "w") as f:
        for c in a.csvs:
            r = summarize_file(c)
            f.write(f"=== {r['path']} ===\n")
            f.write(f"  n_trials: {r['n_trials']}\n")
            f.write(f"  exact_match_rate: {r['exact_match_rate']:.4f}\n")
            f.write(f"  overall_digit_accuracy: {r['overall_digit_accuracy']:.4f}\n")
            f.write(f"  mean_queries_per_trial: {r['mean_queries_per_trial']:.2f}\n")
            f.write(f"  latency_mean_ms: {r['latency_mean_ms']:.2f}\n")
            f.write(f"  latency_std_ms: {r['latency_std_ms']:.2f}\n")
            f.write("  failure cases (trial, ground_truth, inferred):\n")
            for tid, gt, guess in r["failures"]:
                f.write(f"    trial={tid} gt={gt} inferred={guess}\n")
            f.write("\n")
    print(f"Wrote summary to {a.out_summary}")

if __name__ == "__main__":
    main()
