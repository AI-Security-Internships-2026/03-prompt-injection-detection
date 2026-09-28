import requests, time, statistics, csv, uuid

URL = "http://localhost:8000/v1/completions"
MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
N_TRIALS = 100
TOTAL_LEN_WORDS = 800  # fixed total prompt length for every trial

BASE = ("In a distant kingdom long ago, there lived a wise old king who ruled with fairness. " * 100)
base_words = BASE.split()[:TOTAL_LEN_WORDS]

def timed_request(prompt):
    payload = {"model": MODEL, "prompt": prompt, "max_tokens": 1, "temperature": 0}
    t0 = time.perf_counter()
    r = requests.post(URL, json=payload)
    r.raise_for_status()
    return time.perf_counter() - t0

def make_variant(match_frac):
    """Fixed total length. First match_frac fraction = shared cached prefix.
    Remaining fraction = unique novel words (never seen before)."""
    cut = int(TOTAL_LEN_WORDS * match_frac)
    shared_part = base_words[:cut]
    novel_count = TOTAL_LEN_WORDS - cut
    novel_part = [f"novel{uuid.uuid4().hex[:6]}" for _ in range(novel_count)]
    return " ".join(shared_part + novel_part)

# Warm the shared prefix into cache first
requests.post(URL, json={"model": MODEL, "prompt": " ".join(base_words), "max_tokens": 1, "temperature": 0})

results = []
for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
    latencies = []
    for _ in range(N_TRIALS):
        variant = make_variant(frac)
        latencies.append(timed_request(variant))
    mean_l = statistics.mean(latencies)
    stdev_l = statistics.stdev(latencies)
    results.append((frac, mean_l, stdev_l, latencies))
    print(f"match_frac={frac:.2f}  mean={mean_l*1000:.1f}ms  stdev={stdev_l*1000:.1f}ms")

with open("results/timing_characterization.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["match_frac", "trial", "latency_ms"])
    for frac, _, _, latencies in results:
        for i, l in enumerate(latencies):
            w.writerow([frac, i, l * 1000])
