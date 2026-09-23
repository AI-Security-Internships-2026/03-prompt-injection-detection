"""
run_secret_position.py — Secret-position sweep for SGLang, KV3.
Mirrors experiments/phase4/run_secret_position_vllm.py for cross-framework
parity. Tests whether secret position (beginning/middle/end) affects the
timing side-channel strength.
"""
import sys, os, csv, argparse, random
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from measure import send_request
from apps.shared_client import resolve_salt, CACHE_MODES

FILLER = (
    "You are a customer support assistant for Acme Corp. Always be polite, "
    "concise, and professional. Never disclose internal policy details. "
    "Refer customers to the help center for billing questions. Escalate "
    "any security concerns to the security team immediately. Do not make "
    "promises about refund timelines."
)
TEMPLATES = {
    "beginning": "Confidential authorization code: {secret}. " + FILLER + " Respond only with OK.",
    "middle": "Customer request context begins. " + FILLER + " Confidential authorization code: {secret}. " + FILLER + " Respond only with OK.",
    "end": "Customer request context begins. " + FILLER + " Respond only with OK. Confidential authorization code: {secret}.",
}
LOW_ENTROPY_CANDIDATES = ["yes", "no", "ok", "true", "false"]

def run(cache_mode, position, run_id, trials, out_path):
    template = TEMPLATES[position]
    rows = []
    print(f"=== SGLang secret-position sweep, position={position}, cache_mode={cache_mode} ===")
    for trial in range(trials):
        gt_secret = random.choice(LOW_ENTROPY_CANDIDATES)
        placeholder = random.choice([s for s in LOW_ENTROPY_CANDIDATES if s != gt_secret])
        salt_v = resolve_salt(cache_mode, "victim", run_id)
        send_request(template.format(secret=gt_secret), cache_salt=salt_v)

        salt_a = resolve_salt(cache_mode, "attacker", run_id)
        r_correct = send_request(template.format(secret=gt_secret), cache_salt=salt_a)
        r_wrong = send_request(template.format(secret=placeholder), cache_salt=salt_a)
        rows.append({
            "framework": "sglang", "position": position, "cache_mode": cache_mode,
            "trial": trial, "probe_candidate": gt_secret,
            "wall_clock_latency": r_correct["wall_clock_latency"],
            "ground_truth_secret": gt_secret, "condition": "correct",
        })
        rows.append({
            "framework": "sglang", "position": position, "cache_mode": cache_mode,
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
    p.add_argument("--position", choices=list(TEMPLATES.keys()), required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    run(a.cache_mode, a.position, a.run_id, a.trials, a.out)
