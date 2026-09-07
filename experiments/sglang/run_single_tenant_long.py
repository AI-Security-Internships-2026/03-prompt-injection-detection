"""
run_single_tenant_long.py — Stage 2b: same fresh/repeat/modified design as
run_single_tenant.py, but with a long (~900 token) shared prefix to test
whether cache-hit fraction produces a detectable timing signal at scale.
"""
import csv
import sys
import time
import os

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "single_tenant_long_raw.csv"))
N_TRIALS = 10

PARAGRAPH = (
    "The distributed inference system under study employs a radix-tree based prefix "
    "cache to identify and reuse overlapping token sequences across concurrent requests "
    "from multiple tenants. This design choice trades additional memory overhead for "
    "reduced redundant computation during the prefill phase, particularly beneficial "
    "when many requests share a common system prompt or few-shot context. However, this "
    "sharing mechanism introduces a potential side channel: if cache state is observable "
    "indirectly through request timing, an adversarial tenant could in principle infer "
    "information about another tenant's private prompt content without direct access. "
)
BASE_PREFIX = (PARAGRAPH * 12).strip()

FRESH_PROMPT = BASE_PREFIX + " Summarize the key design goal in one sentence."
MODIFIED_PROMPT = BASE_PREFIX + " Summarize the key risk in one sentence."

def run():
    rows = []
    print(f"Prefix length (chars): {len(BASE_PREFIX)}")

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

    print(f"Sending {N_TRIALS} MODIFIED requests...")
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
