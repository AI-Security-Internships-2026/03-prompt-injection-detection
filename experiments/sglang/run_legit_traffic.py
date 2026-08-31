"""
run_legit_traffic.py - Part 2 performance comparison: legitimate-traffic
cost of the cache_salt / disable-radix mitigations.

Simulates ONE legitimate tenant sending realistic, overlapping support
traffic (shared system prompt + varying customer questions), NOT an
attack. Purpose: measure whether mitigations that block cross-tenant
leakage also cost the SAME tenant's normal cache-hit rate / latency /
throughput.

Usage:
    python run_legit_traffic.py <condition> <label>
    condition: "unsalted" or "salted"
    label:     free-text run label, e.g. "baseline", "salted", "disable_radix"

Output: results/sglang/mitigation/perf_<label>.csv
"""
import csv
import os
import sys
import time
import random

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX

FLUSH_URL = "http://localhost:30001/flush_cache"
N_UNIQUE_PROMPTS = 10
REPEATS_PER_PROMPT = 6
TENANT_SALT = "tenant_legit"
GAP_SECONDS = 0.2

def flush_cache():
    import requests
    requests.post(FLUSH_URL, timeout=10)

def build_prompt_pool():
    """10 distinct, realistic support questions sharing the long public prefix."""
    questions = [
        "What is the status of ticket #{}?".format(1000 + i)
        for i in range(N_UNIQUE_PROMPTS)
    ]
    return [SHARED_PUBLIC_PREFIX + "Customer question: " + q for q in questions]

def build_request_sequence(pool):
    """60 requests: each of the 10 prompts repeated 6x, order shuffled."""
    seq = pool * REPEATS_PER_PROMPT
    random.shuffle(seq)
    return seq

def send_one(prompt: str, condition: str) -> dict:
    salt = TENANT_SALT if condition == "salted" else None
    return send_request(prompt, cache_salt=salt)

def compute_summary(rows: list) -> dict:
    latencies = sorted(r["wall_clock_latency"] for r in rows)
    n = len(latencies)
    p50 = latencies[int(n * 0.50)]
    p95 = latencies[min(int(n * 0.95), n - 1)]
    total_time = sum(latencies)
    throughput = n / total_time if total_time > 0 else 0
    cache_hits = sum(1 for r in rows if (r.get("cached_tokens") or 0) > 0)
    cache_hit_rate = cache_hits / n if n else 0
    return {
        "n_requests": n,
        "latency_p50": p50,
        "latency_p95": p95,
        "throughput_req_per_sec": throughput,
        "cache_hit_rate": cache_hit_rate,
        "avg_cached_tokens": sum((r.get("cached_tokens") or 0) for r in rows) / n if n else 0,
    }

def run(condition: str, label: str):
    assert condition in ("unsalted", "salted"), "condition must be unsalted or salted"

    flush_cache()
    time.sleep(0.5)

    pool = build_prompt_pool()
    sequence = build_request_sequence(pool)

    rows = []
    for i, prompt in enumerate(sequence):
        r = send_one(prompt, condition)
        r["request_index"] = i
        r["condition"] = condition
        r["label"] = label
        rows.append(r)
        print(f"  [{i+1}/{len(sequence)}] cached_tokens={r.get('cached_tokens')} "
              f"latency={r['wall_clock_latency']:.3f}s")
        time.sleep(GAP_SECONDS)

    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "mitigation"))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"perf_{label}.csv")
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = compute_summary(rows)
    print(f"\nSaved {len(rows)} rows to {out_path}")
    print(f"Summary: {summary}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python run_legit_traffic.py <unsalted|salted> <label>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
