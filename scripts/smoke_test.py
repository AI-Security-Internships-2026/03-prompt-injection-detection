import requests, time, statistics

URL = "http://localhost:8000/v1/completions"
MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"

PROMPT = "The quick brown fox jumps over the lazy dog. " * 20

def timed_request(prompt, max_tokens=1):
    payload = {"model": MODEL, "prompt": prompt, "max_tokens": max_tokens, "temperature": 0}
    t0 = time.perf_counter()
    r = requests.post(URL, json=payload)
    r.raise_for_status()
    return time.perf_counter() - t0

timed_request("warmup " * 5)

cold = timed_request(PROMPT)
print(f"Cold (first-time prompt) latency: {cold*1000:.1f} ms")

warm_latencies = [timed_request(PROMPT) for _ in range(10)]
print(f"Warm (cached) latencies: {[f'{x*1000:.1f}ms' for x in warm_latencies]}")
print(f"Warm mean: {statistics.mean(warm_latencies)*1000:.1f} ms, stdev: {statistics.stdev(warm_latencies)*1000:.1f} ms")
