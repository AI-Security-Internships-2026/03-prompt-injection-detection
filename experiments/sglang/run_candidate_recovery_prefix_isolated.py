"""
run_candidate_recovery_prefix_isolated.py — corrected version of
run_candidate_recovery_prefix.py that removes cross-probe cache
contamination.

Fix: in the original script, all 4 attacker probes within a trial ran
sequentially against the same (unflushed) cache, so probe N could
partially hit cache residue left by probe N-1's own request rather than
purely the victim's request. This is especially significant when
candidates share a sub-prefix with EACH OTHER (e.g. "SK-"), not just
with the shared public prefix.

Fix: each probe now gets its own independent flush -> victim_populate ->
gap -> single probe cycle. All 4 cycles within a trial share the same
ground-truth candidate selection, so it is still one logical trial, but
no probe can see cache residue from a previous probe.
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

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "candidate_recovery_predictable_prefix_isolated.csv"))
FLUSH_URL = "http://localhost:30000/flush_cache"
N_TRIALS = 30
GAP_SECONDS = 1

def flush_cache():
    r = requests.post(FLUSH_URL, timeout=10)
    return r.text.strip()

def victim_populate(candidate: str):
    prompt = SHARED_PUBLIC_PREFIX + candidate
    return send_request(prompt)

def attacker_probe(candidate_guess: str):
    prompt = SHARED_PUBLIC_PREFIX + candidate_guess
    return send_request(prompt)

def run():
    rows = []

    for trial in range(N_TRIALS):
        # Ground truth chosen once per trial, used consistently across
        # all 4 isolated probe cycles below.
        gt_index = random.randrange(len(CANDIDATES))
        gt_candidate = CANDIDATES[gt_index]

        for probe_index, probe_candidate in enumerate(CANDIDATES):
            flush_cache()
            time.sleep(0.3)

            victim_populate(gt_candidate)
            time.sleep(GAP_SECONDS)

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
