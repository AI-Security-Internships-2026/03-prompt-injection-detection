"""
measure.py — SGLang request/timing helper.
Matches vLLM Phase 2/3 methodology: non-streaming, wall-clock time.perf_counter(),
max_new_tokens=1. Also captures SGLang's native meta_info (cached_tokens, e2e_latency)
as additional ground truth not available in the vLLM experiments.
"""
import time
import requests

SGLANG_URL = "http://localhost:30001/generate"

def send_request(prompt: str, max_new_tokens: int = 1, temperature: float = 0.0, timeout: float = 60.0, cache_salt: str = None) -> dict:
    """
    Sends a single non-streaming request to SGLang and records wall-clock latency.
    Returns a flat dict suitable for writing to CSV.
    """
    payload = {
        "text": prompt,
        "sampling_params": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
        },
    }
    if cache_salt is not None:
        payload["extra_key"] = cache_salt

    t0 = time.perf_counter()
    resp = requests.post(SGLANG_URL, json=payload, timeout=timeout)
    t1 = time.perf_counter()

    wall_clock_latency = t1 - t0

    resp.raise_for_status()
    data = resp.json()
    meta = data.get("meta_info", {})

    return {
        "wall_clock_latency": wall_clock_latency,
        "server_e2e_latency": meta.get("e2e_latency"),
        "prompt_tokens": meta.get("prompt_tokens"),
        "cached_tokens": meta.get("cached_tokens"),
        "cached_tokens_device": (meta.get("cached_tokens_details") or {}).get("device"),
        "cached_tokens_host": (meta.get("cached_tokens_details") or {}).get("host"),
        "completion_tokens": meta.get("completion_tokens"),
        "request_id": meta.get("id"),
        "prompt_char_len": len(prompt),
    }
