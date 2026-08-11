"""
run_single_tenant.py — Stage 2: single-tenant prefix-cache validation.

Sends three conditions, repeated N times each, in a fixed order:
  1. FRESH   — a prompt never sent before (cache miss expected)
  2. REPEAT  — the exact same FRESH prompt sent again (cache hit expected)
  3. MODIFIED— FRESH prompt with a small suffix change (partial cache hit expected)

Saves raw per-request results to results/sglang/single_tenant_raw.csv
"""
import csv
import sys
import time
import os

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "single_tenant_raw.csv")
OUT_PATH = os.path.abspath(OUT_PATH)

N_TRIALS = 10

# A moderately long fixed prefix so cache effects are measurable
BASE_PREFIX = (
    "You are a helpful research assistant analyzing system architecture documents. "
    "Below is a technical description of a distributed caching system used in large-scale "
    "machine learning inference deployments. Please read carefully and prepare to answer "
    "questions about its design, tradeoffs, and failure modes. The system uses a radix-tree "
    "based prefix matching structure to identify shared token sequences across requests."
)

FRESH_PROMPT = BASE_PREFIX + " Summarize the key design goal in one sentence."
MODIFIED_PROMPT = BASE_PREFIX + " Summarize the key risk in one sentence."

def run():
    rows = []

    print(f"Sending {N_TRIALS} FRESH requests (first will be cold, rest establish repeat baseline)...")
    for i in range(N_TRIALS):
        r = send_request(FRESH_PROMPT)
        r.update({"condition": "fresh", "trial": i})
        rows.append(r)
        print(f"  fresh[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    print(f"Sending {N_TRIALS} REPEAT requests (identical prompt, expect cache hit)...")
    for i in range(N_TRIALS):
        r = send_request(FRESH_PROMPT)
        r.update({"condition": "repeat", "trial": i})
        rows.append(r)
        print(f"  repeat[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    print(f"Sending {N_TRIALS} MODIFIED requests (shared prefix, different suffix)...")
    for i in range(N_TRIALS):
        r = send_request(MODIFIED_PROMPT)
        r.update({"condition": "modified", "trial": i})
        rows.append(r)
        print(f"  modified[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")

if __name__ == "__main__":
    run()
