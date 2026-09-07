"""
run_partial_cache_test_v4.py — same as v3, but with a 1s idle gap between
the warmup request and the measured request, per the contention finding
from the gap-sweep experiment (Step 17/18).
"""
import csv, sys, time, os, requests
sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "partial_cache_raw_v4.csv"))
FLUSH_URL = "http://localhost:30000/flush_cache"
N_TRIALS = 10
GAP = 1.0  # validated in Step 17/18 to clear contention effects

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
PREFIX_ONLY_WARMUP = SHARED_PREFIX + "warmup."

def flush_cache():
    requests.post(FLUSH_URL, timeout=10)

def run():
    rows = []
    print(f"Shared prefix length (chars): {len(SHARED_PREFIX)}, gap={GAP}s")

    print(f"\nSending {N_TRIALS} REPEAT trials (gap={GAP}s after warmup)...")
    for i in range(N_TRIALS):
        flush_cache()
        time.sleep(0.3)
        send_request(FRESH_PROMPT)
        time.sleep(GAP)
        r = send_request(FRESH_PROMPT)
        r.update({"condition": "repeat", "trial": i})
        rows.append(r)
        print(f"  repeat[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

    print(f"\nSending {N_TRIALS} MODIFIED trials (gap={GAP}s after prefix-only warmup)...")
    for i in range(N_TRIALS):
        flush_cache()
        time.sleep(0.3)
        send_request(PREFIX_ONLY_WARMUP)
        time.sleep(GAP)
        r = send_request(MODIFIED_PROMPT)
        r.update({"condition": "modified", "trial": i})
        rows.append(r)
        print(f"  modified[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")

if __name__ == "__main__":
    run()
