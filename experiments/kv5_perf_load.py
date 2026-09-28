"""kv5_perf_load.py (V3) — measures TTFT and total generation latency separately,
plus cache-hit rate, at configurable concurrency.

V3 change: prompt selection is now DETERMINISTIC and cycles through a SMALL set
of prompts (4) per worker, so each worker reuses the same prompt ~5x within its
20-request budget. This is required to actually exercise the prefix cache: the
previous version used random.choice over 20 prompts, so cross-request reuse was
rare and cached_tokens stayed near 0 in shared mode — meaning shared vs disabled
were indistinguishable."""
import argparse, csv, time, threading, os
import requests

# 20 prompts for legitimate-workload diversity, but workers cycle over a small
# subset to force cache reuse.
ALL_QUESTIONS = [
    "What is the capital of France?",
    "Explain a for loop in Python.",
    "What is 2+2?",
    "Summarize: cats are mammals.",
    "What is the boiling point of water?",
    "Who wrote Hamlet?",
    "Translate 'hello' to Spanish.",
    "What year did WW2 end?",
    "List three primary colors.",
    "What is the square root of 144?",
    "Describe photosynthesis briefly.",
    "What language is spoken in Brazil?",
    "Define 'recursion' in one sentence.",
    "What is the largest planet?",
    "How many continents are there?",
    "What is a neural network?",
    "Convert 100 F to Celsius.",
    "Who invented the telephone?",
    "What is the speed of light?",
    "Name the first US president.",
]

# Each worker cycles through this small set repeatedly.
WORKER_PROMPT_SET = ALL_QUESTIONS[:4]
REUSE_CYCLES = 5   # 20 requests = 4 prompts x 5 cycles per worker


def worker(url, salt, n, results, lock):
    for i in range(n):
        # Deterministic cycle: prompt index = i mod len(WORKER_PROMPT_SET)
        prompt = WORKER_PROMPT_SET[i % len(WORKER_PROMPT_SET)]

        # 1) TTFT probe: max_new_tokens=1
        payload_ttft = {"text": prompt, "sampling_params": {"max_new_tokens": 1, "temperature": 0}}
        if salt:
            payload_ttft["extra_key"] = salt
        t0 = time.perf_counter()
        r = requests.post(url, json=payload_ttft, timeout=60)
        ttft_ms = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        cached = None
        try:
            cached = r.json().get("meta_info", {}).get("cached_tokens")
        except Exception:
            pass

        # 2) Total latency probe: same prompt, max_new_tokens=32
        payload_full = {"text": prompt, "sampling_params": {"max_new_tokens": 32, "temperature": 0}}
        if salt:
            payload_full["extra_key"] = salt
        t1 = time.perf_counter()
        r2 = requests.post(url, json=payload_full, timeout=120)
        total_ms = (time.perf_counter() - t1) * 1000
        r2.raise_for_status()

        with lock:
            results.append({
                "ttft_ms": ttft_ms,
                "total_latency_ms": total_ms,
                "cached_tokens_ttft_req": cached,
            })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:30010/generate")
    p.add_argument("--mode", required=True)
    p.add_argument("--concurrency", type=int, required=True)
    p.add_argument("--requests-per-worker", type=int, required=True)
    p.add_argument("--tenant-isolated", action="store_true")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    results = []
    lock = threading.Lock()
    threads = [
        threading.Thread(
            target=worker,
            args=(a.url, f"tenant-{i}" if a.tenant_isolated else None,
                  a.requests_per_worker, results, lock),
        )
        for i in range(a.concurrency)
    ]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed = time.perf_counter() - t0

    def pct(vals, p_):
        if not vals: return None
        s = sorted(vals)
        idx = min(int(len(s) * p_ / 100), len(s) - 1)
        return s[idx]

    ttfts = [r["ttft_ms"] for r in results]
    totals = [r["total_latency_ms"] for r in results]
    cached = [r["cached_tokens_ttft_req"] for r in results if r["cached_tokens_ttft_req"] is not None]
    hit_rate = (sum(1 for c in cached if c and c > 0) / len(cached)) if cached else None

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ttft_ms", "total_latency_ms", "cached_tokens_ttft_req"])
        w.writeheader()
        w.writerows(results)

    summary = a.out.replace(".csv", "_summary.txt")
    with open(summary, "w") as f:
        f.write(f"mode={a.mode} concurrency={a.concurrency} total_requests={len(results)}\n")
        f.write(f"elapsed_s={elapsed:.2f} throughput_req_s={len(results)/elapsed:.2f}\n")
        f.write(f"ttft_p50_ms={pct(ttfts,50):.2f} ttft_p95_ms={pct(ttfts,95):.2f} ttft_p99_ms={pct(ttfts,99):.2f}\n")
        f.write(f"total_p50_ms={pct(totals,50):.2f} total_p95_ms={pct(totals,95):.2f} total_p99_ms={pct(totals,99):.2f}\n")
        f.write(f"cache_hit_rate={hit_rate}\n")
    print(open(summary).read())


if __name__ == "__main__":
    main()
