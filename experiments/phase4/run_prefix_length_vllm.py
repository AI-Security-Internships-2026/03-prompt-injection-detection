"""
run_prefix_length_vllm.py — Prefix-length sweep for vLLM, KV3.
Tests whether the length of shared prefix before the secret affects the
timing side-channel strength, at 16/64/256/1024 filler tokens. Same
paired correct/wrong design as Level 1 and the position sweep.
"""
import csv, os, sys, argparse, random
sys.path.insert(0, os.path.expanduser("~/promptpeek-repro"))
from experiments.phase4.harness import _timed_request, GroundTruth
import experiments.phase4.harness as harness
from experiments.phase4.secrets import low_entropy_secret

CACHE_MODES = {"shared", "cache-disabled"}
PREFIX_LENGTHS = [16, 64, 256, 1024]
FILLER_WORD = "context "  # ~1 token per repeat, approximate

def build_template(n_tokens):
    filler = FILLER_WORD * n_tokens
    return filler + "Confidential authorization code: {secret}. Respond only with OK."

def run(cache_mode, prefix_len, model, trials, out_path):
    harness.MODEL = model
    template = build_template(prefix_len)
    rows = []
    print(f"=== vLLM prefix-length sweep, prefix_len={prefix_len}, cache_mode={cache_mode} ===")
    for trial in range(trials):
        base_gt = low_entropy_secret()
        gt = GroundTruth(secret=base_gt.secret, category="low_entropy", template=template)
        placeholder = random.choice([s for s in ["yes", "no", "ok", "true", "false"] if s != gt.secret])

        _timed_request(template.format(secret=gt.secret))  # victim populate

        lat_correct = _timed_request(template.format(secret=gt.secret))
        lat_wrong = _timed_request(template.format(secret=placeholder))
        rows.append({
            "framework": "vllm", "prefix_len": prefix_len, "cache_mode": cache_mode,
            "model": model, "trial": trial, "probe_candidate": gt.secret,
            "wall_clock_latency_ms": lat_correct, "ground_truth_secret": gt.secret,
            "condition": "correct",
        })
        rows.append({
            "framework": "vllm", "prefix_len": prefix_len, "cache_mode": cache_mode,
            "model": model, "trial": trial, "probe_candidate": placeholder,
            "wall_clock_latency_ms": lat_wrong, "ground_truth_secret": gt.secret,
            "condition": "wrong",
        })
        print(f"  trial={trial} gt={gt.secret!r} correct={lat_correct:.2f}ms wrong={lat_wrong:.2f}ms")

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
    p.add_argument("--model", required=True)
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if a.cache_mode not in CACHE_MODES:
        raise ValueError(f"unknown cache_mode {a.cache_mode!r}")
    run(a.cache_mode, a.prefix_len, a.model, a.trials, a.out)
