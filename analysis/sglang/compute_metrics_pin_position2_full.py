import csv, os
import numpy as np
from scipy import stats

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "pin_position2_full.csv")

rows = []
with open(IN_PATH, newline="") as f:
    for r in csv.DictReader(f):
        r["cached_tokens"] = int(r["cached_tokens"])
        r["trial"] = int(r["trial"])
        rows.append(r)

trials = sorted(set(r["trial"] for r in rows))
correct = 0
confusion = np.zeros((10, 10), dtype=int)

for t in trials:
    trial_rows = sorted([r for r in rows if r["trial"] == t], key=lambda r: r["probed_digit"])
    gt = int(trial_rows[0]["ground_truth_digit2"])
    cached = [r["cached_tokens"] for r in trial_rows]
    predicted = int(np.argmax(cached))
    correct += predicted == gt
    confusion[gt][predicted] += 1

n = len(trials)
acc = correct / n
chance = 1/10

binom = stats.binomtest(correct, n, chance, alternative="greater")

z = 1.96
denom = 1 + z**2/n
center = (acc + z**2/(2*n)) / denom
margin = (z * np.sqrt((acc*(1-acc)/n) + z**2/(4*n**2))) / denom
ci_low, ci_high = center - margin, center + margin

print(f"N trials: {n}")
print(f"Correct: {correct}/{n} = {acc:.2%}  (chance = {chance:.2%})")
print(f"95% Wilson CI: [{ci_low:.2%}, {ci_high:.2%}]")
print(f"Binomial test p-value (vs chance): {binom.pvalue:.6g}")
print("\nConfusion matrix (rows=ground truth digit, cols=predicted digit):")
print(confusion)

if binom.pvalue < 0.05 and ci_low > chance:
    print("\nRESULT: Accuracy significantly above chance. Single-digit position-1 recovery supported.")
else:
    print("\nRESULT: Not significantly above chance at alpha=0.05.")
