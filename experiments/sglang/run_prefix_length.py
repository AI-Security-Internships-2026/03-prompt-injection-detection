"""
run_prefix_length.py — Prefix-length sweep for SGLang, KV3.
Mirrors experiments/phase4/run_prefix_length_vllm.py for cross-framework
parity. Tests whether prefix length (16/64/256/1024 filler tokens)
affects the timing side-channel strength.
"""
import sys, os, csv, argparse, random
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from measure import send_request
from apps.shared_client import resolve_salt, CACHE_MODES

PREFIX_LENGTHS = [16, 64, 256, 1024]
FILLER_WORD = "context "
LOW_ENTROPY_CANDIDATES = ["yes", "no", "ok", "true", "false"]

def build_template(n_tokens):
    filler = FILLER_WORD * n_tokens
    return filler + "Confidential authorization code: {secret}. Respond only with OK."

def run(cache_mode, prefix_len, run_id, trials, out_path):
    template = build_template(prefix_len)
    rows = []
    print(f"=== SGLang prefix-length sweep, prefix_len={prefix_len}, cache_mode={cache_mode} ===")
    for trial in range(trials):
        gt_secret = random.choice(LOW_ENTROPY_CANDIDATES)
        placeholder = random.choice([s for s in LOW_ENTROPY_CANDIDATES if s != gt_secret])
        salt_v = resolve_salt(cache_mode, "victim", run_id)
        send_request(template.format(secret=gt_secret), cache_salt=salt_v)

        salt_a = resolve_salt(cache_mode, "attacker", run_id)
        r_correct = send_request(template.format(secret=gt_secret), cache_salt=salt_a)
        r_wrong = send_request(template.format(secret=placeholder), cache_salt=salt_a)
        rows.append({
            "framework": "sglang", "prefix_len": prefix_len, "cache_mode": cache_mode,
            "trial": trial, "probe_candidate": gt_secret,
            "wall_clock_latency": r_correct["wall_clock_latency"],
            "ground_truth_secret": gt_secret, "condition": "correct",
        })
        rows.append({
            "framework": "sglang", "prefix_len": prefix_len, "cache_mode": cache_mode,
            "trial": trial, "probe_candidate": placeholder,
            "wall_clock_latency": r_wrong["wall_clock_latency"],
            "ground_truth_secret": gt_secret, "condition": "wrong",
        })
        print(f"  trial={trial} gt={gt_secret!r} correct={r_correct['wall_clock_latency']:.4f}s wrong={r_wrong['wall_clock_latency']:.4f}s")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows to {out_path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cache-mode", choices=sorted(CACHE_MODES), required=True)
    p.add_argument("--prefix-len", type=int, choices=PREFIX_LENGTHS, required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    run(a.cache_mode, a.prefix_len, a.run_id, a.trials, a.out)
