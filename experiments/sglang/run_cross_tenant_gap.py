"""
run_cross_tenant_gap.py — isolate whether the inverted B>A latency result
from Stage 3 v2 is caused by back-to-back request scheduling contention.

Tests multiple idle gaps between victim's request and attacker's probe:
  0s (replicates v2 exactly), 1s, 3s, 5s

For each gap value, runs flush-isolated Condition A and Condition B trials.
"""
import csv
import sys
import time
import os
import requests

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, VICTIM_SECRET_SUFFIX  # noqa

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "cross_tenant_gap_sweep.csv"))
FLUSH_URL = "http://localhost:30000/flush_cache"
N_TRIALS = 10
GAP_VALUES = [0, 1, 3, 5]

ATTACKER_GUESS_SUFFIX = "Account tier: unknown. Requesting status update."

def flush_cache():
    r = requests.post(FLUSH_URL, timeout=10)
    return r.text.strip()

def attacker_probe():
    prompt = SHARED_PUBLIC_PREFIX + ATTACKER_GUESS_SUFFIX
    return send_request(prompt)

def victim_populate():
    prompt = SHARED_PUBLIC_PREFIX + VICTIM_SECRET_SUFFIX
    return send_request(prompt)

def run():
    rows = []

    for gap in GAP_VALUES:
        print(f"\n=== GAP = {gap}s ===")

        print(f"  Condition A (no victim, gap={gap}s)")
        for i in range(N_TRIALS):
            flush_cache()
            time.sleep(0.3)
            time.sleep(gap)
            r = attacker_probe()
            r.update({"condition": "A_no_victim", "gap_seconds": gap, "trial": i})
            rows.append(r)
            print(f"    A[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

        print(f"  Condition B (after victim, gap={gap}s)")
        for i in range(N_TRIALS):
            flush_cache()
            time.sleep(0.3)
            victim_populate()
            time.sleep(gap)
            r = attacker_probe()
            r.update({"condition": "B_after_victim", "gap_seconds": gap, "trial": i})
            rows.append(r)
            print(f"    B[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")

if __name__ == "__main__":
    run()
