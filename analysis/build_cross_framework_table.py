import csv
from pathlib import Path
from statistics import mean, stdev

SGLANG_BASE = Path("results/sglang/kv2")
VLLM_BASE = Path("results/phase4/kv3")

STRATEGY_TO_CATEGORY = {
    "full": "low_entropy",
    "prefix": "predictable_prefix",
    "pin": "structured",
    "uuid": "high_entropy",
}
CATEGORIES = ["low_entropy", "predictable_prefix", "structured", "high_entropy"]
MODES = ["shared", "disabled"]

def cohens_d(correct, wrong):
    n1, n2 = len(correct), len(wrong)
    if n1 < 2 or n2 < 2:
        return float("nan")
    m1, m2 = mean(correct), mean(wrong)
    s1, s2 = stdev(correct), stdev(wrong)
    pooled = (((n1-1)*s1**2 + (n2-1)*s2**2) / (n1+n2-2)) ** 0.5
    return (m1 - m2) / pooled if pooled > 0 else float("nan")

def load_sglang_cell(strategy, mode):
    path = SGLANG_BASE / f"candidate_{strategy}_{mode}.csv"
    correct, wrong = [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            lat = float(row["wall_clock_latency"])
            (correct if row["probe_candidate"] == row["ground_truth_candidate"] else wrong).append(lat)
    return cohens_d(correct, wrong)

def load_vllm_cell(category, mode):
    path = VLLM_BASE / f"cross_tenant_vllm_{mode}_{category}.csv"
    correct, wrong = [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            lat = float(row["wall_clock_latency_ms"])
            if row["condition"] == "B_after_victim_correct":
                correct.append(lat)
            elif row["condition"] == "B_after_victim_wrong":
                wrong.append(lat)
    return cohens_d(correct, wrong)

strategy_by_category = {v: k for k, v in STRATEGY_TO_CATEGORY.items()}

print(f"{'category':<20}{'mode':<10}{'sglang_d':>10}{'vllm_d':>10}")
for category in CATEGORIES:
    strategy = strategy_by_category[category]
    for mode in MODES:
        sd = load_sglang_cell(strategy, mode)
        vd = load_vllm_cell(category, mode)
        print(f"{category:<20}{mode:<10}{sd:>10.3f}{vd:>10.3f}")
