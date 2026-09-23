"""
generate_legitimate_workloads.py — KV4 Section 3: legitimate traffic
baseline for FPR measurement. Generates 4 workload profiles against
whichever server is currently live (SGLang port 30010 by default).
"""
import csv, os, sys, argparse, time, requests, random

CUM_TIME = [0.0]

def send(url, prompt, extra_key=None):
    payload = {"text": prompt, "sampling_params": {"max_new_tokens": 1, "temperature": 0}}
    if extra_key:
        payload["extra_key"] = extra_key
    t0 = time.perf_counter()
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    lat_ms = (time.perf_counter() - t0) * 1000
    CUM_TIME[0] += lat_ms / 1000.0
    return lat_ms

FACTUAL_QA = [
    "What is the capital of France?", "What is 2+2?", "Who wrote Hamlet?",
    "What is the boiling point of water?", "What year did WW2 end?",
]
CODE_TOPICS = [
    "How do I reverse a list in Python?", "Explain a for loop.",
    "What is a dictionary in Python?", "How do I read a file?",
]
DOC_SUMMARY_FILLER = "This is a sample document about business operations. " * 20

def workload_a(url, n=100):
    rows = []
    for i in range(n):
        prompt = random.choice(FACTUAL_QA)
        lat = send(url, prompt)
        rows.append({"workload": "A_factual_qa", "trial": i, "wall_clock_latency_ms": lat, "prompt": prompt, "timestamp": CUM_TIME[0]})
    return rows

def workload_b(url, n_sessions=10, turns=10):
    rows = []
    for s in range(n_sessions):
        context = ""
        for t in range(turns):
            query = random.choice(CODE_TOPICS)
            prompt = context + query
            lat = send(url, prompt)
            rows.append({"workload": "B_code_assistant", "trial": f"{s}_{t}", "wall_clock_latency_ms": lat, "prompt": prompt, "timestamp": CUM_TIME[0]})
            context = prompt + " "
    return rows

def workload_c(url, n=50):
    rows = []
    for i in range(n):
        prompt = DOC_SUMMARY_FILLER + f" Document ID {i}. Summarize in one sentence."
        lat = send(url, prompt)
        rows.append({"workload": "C_doc_summary", "trial": i, "wall_clock_latency_ms": lat, "prompt": prompt, "timestamp": CUM_TIME[0]})
    return rows

def workload_d(url, n=50):
    rows = []
    shared_prefix = "You are a helpful assistant for Acme Corp customer support. "
    for i in range(n):
        prompt = shared_prefix + f"User question {i}: how do I reset my password?"
        lat = send(url, prompt, extra_key=f"legit-user-{i}")
        rows.append({"workload": "D_shared_cache_reuse", "trial": i, "wall_clock_latency_ms": lat, "prompt": prompt, "timestamp": CUM_TIME[0]})
    return rows

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:30010/generate")
    p.add_argument("--out", required=True)
    p.add_argument("--n-a", type=int, default=100)
    p.add_argument("--n-b-sessions", type=int, default=10)
    p.add_argument("--n-b-turns", type=int, default=10)
    p.add_argument("--n-c", type=int, default=50)
    p.add_argument("--n-d", type=int, default=50)
    a = p.parse_args()

    all_rows = []
    print("=== Workload A: factual Q&A ===")
    all_rows += workload_a(a.url, a.n_a)
    print("=== Workload B: code assistant multi-turn ===")
    all_rows += workload_b(a.url, a.n_b_sessions, a.n_b_turns)
    print("=== Workload C: doc summarization ===")
    all_rows += workload_c(a.url, a.n_c)
    print("=== Workload D: shared-cache-reuse ===")
    all_rows += workload_d(a.url, a.n_d)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["workload", "trial", "wall_clock_latency_ms", "prompt", "timestamp"])
        w.writeheader()
        w.writerows(all_rows)
    print(f"Saved {len(all_rows)} rows to {a.out}")
