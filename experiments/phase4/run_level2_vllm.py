"""
run_level2_vllm.py — Level 2 (candidate-ID accuracy) for vLLM, KV3.
Reuses the SAME fixed candidate sets as SGLang's config.py (CANDIDATES,
CANDIDATES_PREFIX, CANDIDATES_PIN, CANDIDATES_UUID) so both frameworks are
tested against identical secrets for a true cross-framework comparison.
Design: victim picks 1 of 4 known candidates (ground truth). Attacker probes
all 4 candidates (blind to ground truth) and guesses the one with LOWEST
latency (fastest = most likely cache hit). Records per-candidate latency,
the attacker's guess, and whether the guess was correct.
"""
import csv, os, sys, argparse, random
sys.path.insert(0, os.path.expanduser("~/promptpeek-repro"))
from experiments.phase4.harness import _timed_request, GroundTruth
from experiments.phase4.secrets import TEMPLATE
sys.path.insert(0, os.path.expanduser("~/promptpeek-repro/experiments/sglang"))
from config import CANDIDATES, CANDIDATES_PREFIX, CANDIDATES_PIN, CANDIDATES_UUID

CACHE_MODES = {"shared", "cache-disabled"}
CATEGORY_TO_CANDIDATES = {
    "low_entropy": CANDIDATES,
    "predictable_prefix": CANDIDATES_PREFIX,
    "structured": CANDIDATES_PIN,
    "high_entropy": CANDIDATES_UUID,
}
N_TRIALS = 30

def run(cache_mode, category, model, trials, out_path):
    import experiments.phase4.harness as harness
    harness.MODEL = model
    candidates = CATEGORY_TO_CANDIDATES[category]
    rows = []
    print(f"=== vLLM Level 2, cache_mode={cache_mode}, category={category}, model={model} ===")
    for trial in range(trials):
        gt_candidate = random.choice(candidates)
        gt = GroundTruth(secret=gt_candidate, category=category, template=TEMPLATE)

        # Victim populates cache with the real secret
        _timed_request(gt.full_prompt())

        # Attacker probes ALL candidates, blind to ground truth
        latencies = {}
        for cand in candidates:
            lat = _timed_request(TEMPLATE.format(secret=cand))
            latencies[cand] = lat

        guess = min(latencies, key=latencies.get)
        correct = (guess == gt_candidate)

        for cand in candidates:
            rows.append({
                "framework": "vllm", "cache_mode": cache_mode, "category": category,
                "model": model, "trial": trial, "probe_candidate": cand,
                "wall_clock_latency_ms": latencies[cand],
                "ground_truth_candidate": gt_candidate,
                "attacker_guess": guess, "guess_correct": correct,
            })
        print(f"  trial={trial} gt={gt_candidate!r} guess={guess!r} correct={correct}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows to {out_path}")
    n_correct_trials = sum(1 for t in range(trials) if rows[t*len(candidates)]["guess_correct"])
    print(f"Accuracy: {n_correct_trials}/{trials} trials correct")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cache-mode", choices=sorted(CACHE_MODES), required=True)
    p.add_argument("--category", choices=list(CATEGORY_TO_CANDIDATES.keys()), required=True)
    p.add_argument("--model", required=True, help="Model string to send in the request payload")
    p.add_argument("--trials", type=int, default=N_TRIALS)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if a.cache_mode not in CACHE_MODES:
        raise ValueError(f"unknown cache_mode {a.cache_mode!r}")
    run(a.cache_mode, a.category, a.model, a.trials, a.out)
