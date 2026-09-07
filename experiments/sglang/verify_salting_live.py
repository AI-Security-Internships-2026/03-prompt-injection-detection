import requests
import time
import hashlib

API_URL = "http://localhost:30000/generate"

def generate_tenant_salt(tenant_id: str) -> str:
    hashed = hashlib.sha256(tenant_id.encode()).hexdigest()
    return f"<|tenant_{hashed[:12]}|>\n"

def send_request(prompt: str, label: str):
    start = time.time()
    response = requests.post(API_URL, json={
        "text": prompt,
        "sampling_params": {"max_new_tokens": 5, "temperature": 0}
    })
    latency = (time.time() - start) * 1000 # in ms
    
    # Try to extract cache hit metrics if SGLang returns them
    usage = response.json().get("meta_info", {}).get("usage", {})
    cached_tokens = usage.get("prompt_tokens_cached", 0) if isinstance(usage, dict) else "Unknown"
    
    print(f"[{label}] Latency: {latency:.2f} ms | Cached Tokens: {cached_tokens}")
    return latency

def run_live_test():
    shared_prefix = "System: You are an AI. " * 50 # Make it long enough to notice a latency drop
    victim_secret = "The PIN is 492015."
    attacker_guess = "The PIN is 4"
    
    print("=== TEST 1: UNMITIGATED (GLOBAL CACHE) ===")
    v_raw = shared_prefix + victim_secret
    a_raw = shared_prefix + attacker_guess
    
    # 1. Warm up the victim
    send_request(v_raw, "Victim (Raw)")
    
    # 2. Attacker probes - should be VERY fast (Cache Hit)
    send_request(a_raw, "Attacker (Raw)")
    
    print("\n=== TEST 2: MITIGATED (PREFIXWALL SALTING) ===")
    v_salt = generate_tenant_salt("tenant_A_victim") + shared_prefix + victim_secret
    a_salt = generate_tenant_salt("tenant_B_attacker") + shared_prefix + attacker_guess
    
    # 1. Warm up the victim (isolated branch)
    send_request(v_salt, "Victim (Salted)")
    
    # 2. Attacker probes - should be SLOW (Cache Miss)
    send_request(a_salt, "Attacker (Salted)")

if __name__ == "__main__":
    try:
        run_live_test()
    except requests.exceptions.ConnectionError:
        print("Error: SGLang server is not running on http://localhost:30000")
