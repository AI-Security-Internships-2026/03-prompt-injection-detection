"""
run_two_app_cross_tenant.py — orchestrates the two-app architecture from
the RESEARCHER'S side only. This script calls victim_app:8001 and
attacker_app:8002 as external HTTP services - it does NOT import either
app's internals, mirroring how a real external orchestrator/attacker would
only ever see HTTP responses, never process memory.

Ground truth (which secret was submitted) is known here, in the researcher
script, NOT inside attacker_app. attacker_app never receives it.
"""
import csv
import time
import os
import requests

VICTIM_URL = "http://localhost:8001"
ATTACKER_URL = "http://localhost:8002"
OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "two_app_cross_tenant.csv"))
N_TRIALS = 15
GAP = 1.0

VICTIM_SECRET = "482913"          # ground truth - known to researcher + victim app only
ATTACKER_GUESS = "unknown guess"  # attacker's own probe content, wrong on purpose

def flush_both():
    requests.post(f"{VICTIM_URL}/flush", timeout=10)

def run():
    rows = []

    print("=== CONDITION A: attacker probes, victim has NOT submitted ===")
    for i in range(N_TRIALS):
        flush_both()
        time.sleep(0.3)
        time.sleep(GAP)
        r = requests.post(f"{ATTACKER_URL}/probe", json={"guess": ATTACKER_GUESS}, timeout=30).json()
        r.update({"condition": "A_no_victim", "trial": i})
        rows.append(r)
        print(f"  A[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

    print("\n=== CONDITION B: victim submits secret via ITS OWN app, then attacker probes via ITS OWN app ===")
    for i in range(N_TRIALS):
        flush_both()
        time.sleep(0.3)
        requests.post(f"{VICTIM_URL}/submit", json={"secret": VICTIM_SECRET}, timeout=30)
        time.sleep(GAP)
        r = requests.post(f"{ATTACKER_URL}/probe", json={"guess": ATTACKER_GUESS}, timeout=30).json()
        r.update({"condition": "B_after_victim", "trial": i})
        rows.append(r)
        print(f"  B[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")

if __name__ == "__main__":
    run()
