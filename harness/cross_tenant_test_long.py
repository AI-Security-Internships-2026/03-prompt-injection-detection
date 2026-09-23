"""
cross_tenant_test_long.py — Phase 3 cross-tenant test with LONG template.
Produces d≈0.340 (the overwritten longer template variant from commit 38ead11).
"""

import requests
import time
import csv
import uuid
import statistics
import os

URL = "http://localhost:8000/v1/completions"
MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
N_TRIALS = 50

# LONG TEMPLATE — gives d=0.340
LONG_FILLER = (
    "You are a customer support assistant for Acme Corp. Always be polite, "
    "concise, and professional. Never disclose internal policy details. "
    "Refer customers to the help center for billing questions. Escalate "
    "any security concerns to the security team immediately. Do not make "
    "promises about refund timelines. Always confirm the customer's "
    "account email before discussing account details. "
) * 8

VICTIM_SECRET_PROMPT_TEMPLATE = LONG_FILLER + "System context for user session: the confidential value is {secret}. Respond only with OK."


def timed_request(prompt):
    payload = {"model": MODEL, "prompt": prompt, "max_tokens": 1, "temperature": 0}
    t0 = time.perf_counter()
    r = requests.post(URL, json=payload)
    r.raise_for_status()
    return time.perf_counter() - t0


def victim_send(secret):
    prompt = VICTIM_SECRET_PROMPT_TEMPLATE.format(secret=secret)
    timed_request(prompt)


def attacker_probe(secret_guess):
    prompt = VICTIM_SECRET_PROMPT_TEMPLATE.format(secret=secret_guess)
    return timed_request(prompt)


def main():
    os.makedirs("results", exist_ok=True)
    
    results = []
    print("=" * 60)
    print("PHASE 3 — LONG TEMPLATE (d≈0.340)")
    print("=" * 60)

    for trial in range(N_TRIALS):
        secret = f"secret-{uuid.uuid4().hex[:12]}"

        before = attacker_probe(secret)
        victim_send(secret)
        after = attacker_probe(secret)

        results.append((trial, before * 1000, after * 1000))
        delta = (before - after) * 1000
        hit_consistent = after < before
        print(f"trial={trial:02d}  before={before*1000:.1f}ms  after={after*1000:.1f}ms  "
              f"delta={delta:.1f}ms  {'HIT' if hit_consistent else 'MISS'}")

    out_path = "results/cross_tenant_long_d340.csv"
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trial", "before_ms", "after_ms", "delta_ms"])
        for trial, before, after in results:
            w.writerow([trial, before, after, before - after])

    befores = [b for _, b, _ in results]
    afters = [a for _, _, a in results]
    hit_count = sum(1 for _, b, a in results if a < b)

    diff = [b - a for b, a in zip(befores, afters)]
    d = (sum(diff) / len(diff)) / (statistics.stdev(diff) if len(diff) > 1 else 1)

    print("\n" + "=" * 60)
    print("RESULTS — LONG TEMPLATE")
    print("=" * 60)
    print(f"Before mean: {statistics.mean(befores):.1f}ms")
    print(f"After mean:  {statistics.mean(afters):.1f}ms")
    print(f"Paired d:    {d:.4f}")
    print(f"Hit-consistent: {hit_count}/{N_TRIALS} ({hit_count/N_TRIALS*100:.1f}%)")
    print(f"Saved to: {out_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
