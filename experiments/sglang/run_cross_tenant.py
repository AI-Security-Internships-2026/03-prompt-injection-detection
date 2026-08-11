"""
run_cross_tenant.py — Stage 3: basic cross-tenant timing leakage test.

Simulates two tenants sharing one SGLang server:
  VICTIM:   sends a request containing SHARED_PUBLIC_PREFIX + VICTIM_SECRET_SUFFIX,
            populating the prefix cache with victim-specific content.
  ATTACKER: sends requests containing only SHARED_PUBLIC_PREFIX + a GUESSED suffix,
            and observes ONLY its own wall-clock timing / cached_tokens — never
            the victim's actual text or ground truth.

Two conditions:
  CONDITION A: attacker probes BEFORE victim has populated the cache (baseline)
  CONDITION B: attacker probes AFTER victim has populated the cache

The attacker's guessed suffix is deliberately WRONG (does not match the real
secret) — this stage only tests whether victim cache activity is detectable
at all, not whether the secret can be recovered (that is a later stage).
"""
import csv
import sys
import time
import os

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, VICTIM_SECRET_SUFFIX  # noqa: this script plays BOTH roles for simulation

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "cross_tenant_raw.csv"))
N_TRIALS = 15

# --- ATTACKER-SIDE CODE BOUNDARY ---
# Everything below this line simulating the attacker must NOT reference
# VICTIM_SECRET_SUFFIX. It only uses SHARED_PUBLIC_PREFIX + its own guess.
ATTACKER_GUESS_SUFFIX = "Account tier: unknown. Requesting status update."

def attacker_probe():
    """Attacker sends its own prompt, observes ONLY its own response/timing."""
    prompt = SHARED_PUBLIC_PREFIX + ATTACKER_GUESS_SUFFIX
    return send_request(prompt)

def victim_populate():
    """Victim sends its private prompt, populating the cache. This function's
    return value represents data the attacker NEVER sees — used only for our
    own ground-truth logging as researchers, kept in a separate output column."""
    prompt = SHARED_PUBLIC_PREFIX + VICTIM_SECRET_SUFFIX
    return send_request(prompt)

def run():
    rows = []

    print(f"=== CONDITION A: attacker probes BEFORE victim cache population ===")
    for i in range(N_TRIALS):
        r = attacker_probe()
        r.update({"condition": "A_before_victim", "trial": i, "ground_truth_note": "N/A - victim has not run yet"})
        rows.append(r)
        print(f"  A[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    print("\n=== VICTIM populates cache (researcher ground-truth event, not attacker-visible) ===")
    victim_result = victim_populate()
    print(f"  [ground truth only] victim wall_clock={victim_result['wall_clock_latency']:.4f}s "
          f"cached_tokens={victim_result['cached_tokens']}/{victim_result['prompt_tokens']}")

    print(f"\n=== CONDITION B: attacker probes AFTER victim cache population ===")
    for i in range(N_TRIALS):
        r = attacker_probe()
        r.update({"condition": "B_after_victim", "trial": i, "ground_truth_note": "victim cache is now populated"})
        rows.append(r)
        print(f"  B[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")
        time.sleep(0.2)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} attacker-observed rows to {OUT_PATH}")
    print("(Victim ground-truth request was NOT written to attacker-observation CSV)")

if __name__ == "__main__":
    run()
