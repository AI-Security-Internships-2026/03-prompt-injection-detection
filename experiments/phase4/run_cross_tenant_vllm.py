"""
run_cross_tenant_vllm.py — vLLM port of experiments/sglang/run_cross_tenant.py
for KV3 cross-framework comparison.

Reuses REAL, existing harness.py (_timed_request, GroundTruth) and secrets.py
(TEMPLATE, SECRET_GENERATORS) from this project's Phase 4 work — not invented.

TWO CONFIRMED FRAMEWORK-CAPABILITY GAPS (document per KV3 Section 2, do not
paper over):
  1. No extra_key/cache_salt equivalent exists in this vLLM OpenAI-compatible
     harness — tenant-isolated mode is therefore NOT supported here and is
     rejected explicitly below, not faked.
  2. No /flush_cache-equivalent endpoint exists — "Condition A" below is
     best-effort (first probe of a trial, before victim activity in THIS
     trial) rather than a true cold-cache guarantee like SGLang's flush.
     This is a real methodological difference to note in the KV3 report.

Cache mode "shared" = server launched normally (--enable-prefix-caching,
per deploy/launch_vllm.sh). "cache-disabled" = server launched WITHOUT that
flag (operator must relaunch manually; this script does not control the
server process).
"""
import csv, os, sys, time, argparse, random
sys.path.insert(0, os.path.expanduser("~/promptpeek-repro"))
from experiments.phase4.harness import _timed_request, GroundTruth
from experiments.phase4.secrets import TEMPLATE, SECRET_GENERATORS

CACHE_MODES = {"shared", "cache-disabled"}  # tenant-isolated NOT supported — see module docstring
N_TRIALS = 30
OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "phase4", "kv3", "cross_tenant_vllm.csv"))


def victim_populate(gt: GroundTruth) -> float:
    return _timed_request(gt.full_prompt())


def attacker_probe(template: str, candidate: str) -> float:
    return _timed_request(template.format(secret=candidate))


def run(cache_mode: str, category: str):
    if cache_mode not in CACHE_MODES:
        raise ValueError(f"unknown cache_mode {cache_mode!r}; valid: {CACHE_MODES}")

    gen_fn = SECRET_GENERATORS[category]
    rows = []

    print(f"=== vLLM cross-tenant, cache_mode={cache_mode}, category={category} ===")
    for trial in range(N_TRIALS):
        gt = gen_fn()
        placeholder = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(len(gt.secret)))

        # Condition A: best-effort cold — probe BEFORE this trial's victim activity.
        # NOT a true flush (no such endpoint exists in this harness — see docstring).
        lat_a = attacker_probe(TEMPLATE, placeholder)
        rows.append({
            "framework": "vllm", "cache_mode": cache_mode, "condition": "A_no_victim",
            "trial": trial, "secret_category": category, "probe_candidate": placeholder,
            "wall_clock_latency_ms": lat_a, "ground_truth_secret": gt.secret,
        })

        # Victim populates (ground truth only used here + for post-hoc scoring)
        victim_populate(gt)

        # Condition B: attacker probes with the REAL secret as candidate (best case)
        # and a WRONG placeholder (control), same as SGLang's paired design.
        lat_b_correct = attacker_probe(TEMPLATE, gt.secret)
        lat_b_wrong = attacker_probe(TEMPLATE, placeholder)
        rows.append({
            "framework": "vllm", "cache_mode": cache_mode, "condition": "B_after_victim_correct",
            "trial": trial, "secret_category": category, "probe_candidate": gt.secret,
            "wall_clock_latency_ms": lat_b_correct, "ground_truth_secret": gt.secret,
        })
        rows.append({
            "framework": "vllm", "cache_mode": cache_mode, "condition": "B_after_victim_wrong",
            "trial": trial, "secret_category": category, "probe_candidate": placeholder,
            "wall_clock_latency_ms": lat_b_wrong, "ground_truth_secret": gt.secret,
        })
        print(f"  trial={trial} A={lat_a:.2f}ms B_correct={lat_b_correct:.2f}ms B_wrong={lat_b_wrong:.2f}ms")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cache-mode", choices=sorted(CACHE_MODES), required=True,
                    help="tenant-isolated NOT supported on vLLM (no salt field) — see module docstring")
    p.add_argument("--category", choices=list(SECRET_GENERATORS.keys()), default="structured")
    p.add_argument("--trials", type=int, default=None)
    p.add_argument("--out", default=None)
    a = p.parse_args()
    if a.trials:
        N_TRIALS = a.trials
    if a.out:
        OUT_PATH = os.path.abspath(a.out)
    run(a.cache_mode, a.category)
