"""
run_candidate_recovery_pilot.py — Level 2 pilot: can the attacker identify
which of 4 same-entropy-category candidates the victim used, from cache
observations alone?

PILOT ONLY: 5 trials x 4 candidates = 20 attacker probes.
Not a full experiment. Do not draw accuracy conclusions from this run;
it is a harness smoke test before scaling up trial count.

Ground-truth isolation: the victim's selected candidate is stored ONLY in
this orchestration loop, in the `ground_truth_index` / `ground_truth_candidate`
fields written directly to the CSV. attacker_probe() never receives or reads
the victim's selection - it only receives the candidate index it is told to
probe, exactly like run_cross_tenant_gap.py's attacker_probe().
"""
import csv
import sys
import os
import time
import random
import requests

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, CANDIDATES_PREFIX as CANDIDATES

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "candidate_recovery_predictable_prefix.csv"))
FLUSH_URL = "http://localhost:30000/flush_cache"
N_TRIALS = 30
GAP_SECONDS = 1  # validated safe gap from run_cross_tenant_gap.py

def flush_cache():
    r = requests.post(FLUSH_URL, timeout=10)
    return r.text.strip()

def victim_populate(candidate: str):
    prompt = SHARED_PUBLIC_PREFIX + candidate
    return send_request(prompt)

def attacker_probe(candidate_guess: str):
    # Attacker only ever sees the candidate string it is told to probe.
    # It has no path to the victim's actual selection.
    prompt = SHARED_PUBLIC_PREFIX + candidate_guess
    return send_request(prompt)

def run():
    rows = []

    for trial in range(N_TRIALS):
        flush_cache()
        time.sleep(0.3)

        # --- victim side: ground truth lives only here ---
        gt_index = random.randrange(len(CANDIDATES))
        gt_candidate = CANDIDATES[gt_index]
        victim_populate(gt_candidate)

        time.sleep(GAP_SECONDS)

        # --- attacker side: probes every candidate, blind to gt_index ---
        for probe_index, probe_candidate in enumerate(CANDIDATES):
            r = attacker_probe(probe_candidate)
            r.update({
                "trial": trial,
                "probe_index": probe_index,
                "probe_candidate": probe_candidate,
                "ground_truth_index": gt_index,
                "ground_truth_candidate": gt_candidate,
            })
            rows.append(r)
            match = "MATCH" if probe_index == gt_index else ""
            print(f"  trial={trial} probe={probe_index} cached_tokens={r['cached_tokens']}/{r['prompt_tokens']} "
                  f"latency={r['wall_clock_latency']:.4f}s {match}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")

if __name__ == "__main__":
    run()
