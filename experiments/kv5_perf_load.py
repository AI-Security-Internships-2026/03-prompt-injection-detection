import argparse, csv, time, threading, random
import requests

QUESTIONS = ["What is the capital of France?", "Explain a for loop.", "What is 2+2?", "Summarize: cats are mammals."]

def worker(url, salt, n, results):
    for i in range(n):
        payload = {"text": random.choice(QUESTIONS), "sampling_params": {"max_new_tokens": 1, "temperature": 0}}
        if salt:
            payload["extra_key"] = salt
        t0 = time.perf_counter()
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        lat = (time.perf_counter() - t0) * 1000
        data = r.json()
        cached = None
        try:
            cached = data.get("meta_info", {}).get("cached_tokens")
        except Exception:
            pass
        results.append({"latency_ms": lat, "cached_tokens": cached})

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
    threads = [threading.Thread(target=worker, args=(a.url, f"tenant-{i}" if a.tenant_isolated else None, a.requests_per_worker, results)) for i in range(a.concurrency)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed = time.perf_counter() - t0
    lats = sorted(r["latency_ms"] for r in results)
    def pct(p_):
        idx = min(int(len(lats)*p_/100), len(lats)-1)
        return lats[idx]
    hits = [r["cached_tokens"] for r in results if r["cached_tokens"] is not None]
    hit_rate = (sum(1 for h in hits if h and h > 0) / len(hits)) if hits else None
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["latency_ms", "cached_tokens"])
        w.writeheader(); w.writerows(results)
    summary = a.out.replace(".csv", "_summary.txt")
    with open(summary, "w") as f:
        f.write(f"mode={a.mode} concurrency={a.concurrency} total_requests={len(results)}\n")
        f.write(f"elapsed_s={elapsed:.2f} throughput_req_s={len(results)/elapsed:.2f}\n")
        f.write(f"p50_ms={pct(50):.2f} p95_ms={pct(95):.2f} p99_ms={pct(99):.2f}\n")
        f.write(f"cache_hit_rate={hit_rate}\n")
    print(open(summary).read())

if __name__ == "__main__":
    main()
