"""
shared_client.py — thin, side-effect-free helper reused by BOTH apps to talk
to the shared SGLang backend. Contains NO secrets and NO victim/attacker
specific logic. Both victim_app.py and attacker_app.py import this file
independently; neither imports from the other.
"""
import time
import requests

SGLANG_GENERATE_URL = "http://localhost:30001/generate"
SGLANG_FLUSH_URL = "http://localhost:30001/flush_cache"

def send_to_sglang(prompt: str, max_new_tokens: int = 1, temperature: float = 0.0, timeout: float = 60.0, cache_salt: str = None) -> dict:
    payload = {
        "text": prompt,
        "sampling_params": {"max_new_tokens": max_new_tokens, "temperature": temperature},
    }
    if cache_salt is not None:
        payload["extra_key"] = cache_salt
    t0 = time.perf_counter()
    resp = requests.post(SGLANG_GENERATE_URL, json=payload, timeout=timeout)
    t1 = time.perf_counter()
    resp.raise_for_status()
    data = resp.json()
    meta = data.get("meta_info", {})
    return {
        "wall_clock_latency": t1 - t0,
        "server_e2e_latency": meta.get("e2e_latency"),
        "prompt_tokens": meta.get("prompt_tokens"),
        "cached_tokens": meta.get("cached_tokens"),
        "cached_tokens_device": (meta.get("cached_tokens_details") or {}).get("device"),
        "cached_tokens_host": (meta.get("cached_tokens_details") or {}).get("host"),
        "completion_tokens": meta.get("completion_tokens"),
        "request_id": meta.get("id"),
    }

def flush_cache() -> str:
    r = requests.post(SGLANG_FLUSH_URL, timeout=10)
    r.raise_for_status()
    return r.text.strip()
