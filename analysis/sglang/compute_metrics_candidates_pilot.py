import csv, os
import numpy as np

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "candidate_recovery_pilot.csv")

rows = []
with open(IN_PATH, newline="") as f:
    for r in csv.DictReader(f):
        r["cached_tokens"] = int(r["cached_tokens"])
        r["wall_clock_latency"] = float(r["wall_clock_latency"])
        r["trial"] = int(r["trial"])
        r["probe_index"] = int(r["probe_index"])
        r["ground_truth_index"] = int(r["ground_truth_index"])
        rows.append(r)

n_candidates = len(set(r["probe_index"] for r in rows))
trials = sorted(set(r["trial"] for r in rows))
chance = 1.0 / n_candidates

correct = 0
confusion = np.zeros((n_candidates, n_candidates), dtype=int)  # [gt][predicted]

print(f"{'trial':>5} {'gt':>3} | " + " ".join(f"c{i}_tok" for i in range(n_candidates)) + " | predicted")
for t in trials:
    trial_rows = sorted([r for r in rows if r["trial"] == t], key=lambda r: r["probe_index"])
    gt = trial_rows[0]["ground_truth_index"]
    cached = [r["cached_tokens"] for r in trial_rows]
    predicted = int(np.argmax(cached))
    is_correct = predicted == gt
    correct += is_correct
    confusion[gt][predicted] += 1
    print(f"{t:>5} {gt:>3} | " + " ".join(f"{c:>6}" for c in cached) + f" | {predicted} {'OK' if is_correct else ''}")

acc = correct / len(trials)
print(f"\nPilot accuracy: {correct}/{len(trials)} = {acc:.2%}  (chance = {chance:.2%})")
print("\nConfusion matrix (rows=ground truth, cols=predicted):")
print(confusion)
print("\nNOTE: This is a 5-trial pilot. Do not treat this accuracy figure as a")
print("statistically meaningful result -- it only checks the harness works.")
print("A real trial count with a significance test comes after this pilot passes.")
