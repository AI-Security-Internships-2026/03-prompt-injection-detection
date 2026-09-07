"""
run_partial_cache_test.py — Stage 2c: proper partial-cache-hit test.
Uses a long, fully divergent suffix (not a few changed words) so cached_tokens
differs by a large, controlled amount between REPEAT and MODIFIED conditions.
"""
import csv
import sys
import time
import os
import requests

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "partial_cache_raw.csv"))
N_TRIALS = 10

SHARED_PREFIX = (
    "The distributed inference system under study employs a radix-tree based prefix "
    "cache to identify and reuse overlapping token sequences across concurrent requests "
    "from multiple tenants. This design choice trades additional memory overhead for "
    "reduced redundant computation during the prefill phase. "
) * 6

SAME_SUFFIX = (
    "Given this context, summarize the primary architectural tradeoff in two "
    "sentences, focusing specifically on memory overhead versus compute savings "
    "and how this applies to multi-tenant deployment scenarios in production."
)

DIFFERENT_SUFFIX = (
    "Now consider a completely different scenario: a single-tenant deployment "
    "with no cache sharing requirements whatsoever, running on dedicated hardware "
    "with no memory constraints, and describe what design choices would change "
    "under these very different assumptions about the deployment environment."
)

FRESH_PROMPT = SHARED_PREFIX + SAME_SUFFIX
MODIFIED_PROMPT = SHARED_PREFIX + DIFFERENT_SUFFIX

def run():
    rows = []
    print(f"Shared prefix length (chars): {len(SHARED_PREFIX)}")

    print(f"Sending {N_TRIALS} FRESH requests...")
    for i in range(N_TRIALS):
        r = send_request(FRESH_PROMPT)
        r.update({"condition": "fresh", "trial": i})
        rows.append(r)
        print(f"  fresh[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    print(f"Sending {N_TRIALS} REPEAT requests...")
    for i in range(N_TRIALS):
        r = send_request(FRESH_PROMPT)
        r.update({"condition": "repeat", "trial": i})
        rows.append(r)
        print(f"  repeat[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    print(f"Sending {N_TRIALS} MODIFIED requests (large divergent suffix)...")
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
