"""
run_cross_tenant.py — Stage 3 v2: cross-tenant timing leakage, flush-isolated.

Each trial is independent:
  Condition A: flush cache -> attacker probes (cold) -> record
  Condition B: flush cache -> victim populates cache -> attacker probes -> record

Attacker-side code only ever calls attacker_probe(). It never imports or
references VICTIM_SECRET_SUFFIX. Ground truth (victim's request) is logged
separately and never merged into the attacker-observation CSV.
"""
import csv
import sys
import time
import os
import argparse
import requests

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, VICTIM_SECRET_SUFFIX  # noqa
from apps.shared_client import resolve_salt, CACHE_MODES

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "cross_tenant_raw_v2.csv"))
GT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "cross_tenant_ground_truth.csv"))
FLUSH_URL = "http://localhost:30010/flush_cache"
N_TRIALS = 15

ATTACKER_GUESS_SUFFIX = "Account tier: unknown. Requesting status update."

def flush_cache():
    r = requests.post(FLUSH_URL, timeout=10)
    return r.text.strip()

def attacker_probe(cache_mode, run_id):
    prompt = SHARED_PUBLIC_PREFIX + ATTACKER_GUESS_SUFFIX
    salt = resolve_salt(cache_mode, "attacker", run_id)
    return send_request(prompt, cache_salt=salt)

def victim_populate(cache_mode, run_id):
    prompt = SHARED_PUBLIC_PREFIX + VICTIM_SECRET_SUFFIX
    salt = resolve_salt(cache_mode, "victim", run_id)
    return send_request(prompt, cache_salt=salt)

def run(cache_mode, run_id):
    attacker_rows = []
    ground_truth_rows = []

    print("=== CONDITION A: flush -> attacker probes cold (no victim activity) ===")
    for i in range(N_TRIALS):
        flush_msg = flush_cache()
        time.sleep(0.3)  # let flush settle
        r = attacker_probe(cache_mode, run_id)
        r.update({"condition": "A_no_victim", "trial": i})
        attacker_rows.append(r)
        print(f"  A[{i}] flush_ok={('lushed' in flush_msg)} wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    print("\n=== CONDITION B: flush -> victim populates -> attacker probes ===")
    for i in range(N_TRIALS):
        flush_msg = flush_cache()
        time.sleep(0.3)

        v = victim_populate(cache_mode, run_id)
        ground_truth_rows.append({**v, "trial": i})  # ground truth, kept separate

        r = attacker_probe(cache_mode, run_id)
        r.update({"condition": "B_after_victim", "trial": i})
        attacker_rows.append(r)
        print(f"  B[{i}] flush_ok={('lushed' in flush_msg)} wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}"
              f"  [ground truth: victim cached_tokens={v['cached_tokens']}/{v['prompt_tokens']}]")
        time.sleep(0.2)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    fieldnames = list(attacker_rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(attacker_rows)

    gt_fieldnames = list(ground_truth_rows[0].keys())
    with open(GT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=gt_fieldnames)
        writer.writeheader()
        writer.writerows(ground_truth_rows)

    print(f"\nSaved {len(attacker_rows)} attacker-observed rows to {OUT_PATH}")
    print(f"Saved {len(ground_truth_rows)} ground-truth rows (researcher-only) to {GT_PATH}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="Override OUT_PATH for attacker-observed CSV")
    parser.add_argument("--gt-out", default=None, help="Override GT_PATH for ground-truth CSV")
    parser.add_argument("--cache-mode", choices=sorted(CACHE_MODES), required=True, help="shared | tenant-isolated | cache-disabled")
    parser.add_argument("--run-id", default=None, help="Salt disambiguator for tenant-isolated mode")
    args = parser.parse_args()

    if args.out:
        OUT_PATH = os.path.abspath(args.out)
    if args.gt_out:
        GT_PATH = os.path.abspath(args.gt_out)

    run_id = args.run_id or str(int(time.time()))
    run(args.cache_mode, run_id)
