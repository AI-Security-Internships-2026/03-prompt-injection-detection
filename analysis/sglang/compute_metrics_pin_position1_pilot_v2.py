import csv, os
import numpy as np

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "pin_position1_pilot_v2.csv")

rows = []
with open(IN_PATH, newline="") as f:
    for r in csv.DictReader(f):
        r["cached_tokens"] = int(r["cached_tokens"])
        r["trial"] = int(r["trial"])
        rows.append(r)

trials = sorted(set(r["trial"] for r in rows))
correct = 0

print(f"{'trial':>5} {'gt_digit':>8} | cached_tokens per probed digit 0-9 | predicted")
for t in trials:
    trial_rows = sorted([r for r in rows if r["trial"] == t], key=lambda r: r["probed_digit"])
    gt = trial_rows[0]["ground_truth_digit1"]
    cached = [r["cached_tokens"] for r in trial_rows]
    predicted_idx = int(np.argmax(cached))
    predicted_digit = trial_rows[predicted_idx]["probed_digit"]
    is_correct = predicted_digit == gt
    correct += is_correct
    print(f"{t:>5} {gt:>8} | " + " ".join(f"{c:>4}" for c in cached) + f" | {predicted_digit} {'OK' if is_correct else 'WRONG'}")

n = len(trials)
chance = 1/10
print(f"\nPilot accuracy: {correct}/{n} = {correct/n:.2%}  (chance = {chance:.2%})")
