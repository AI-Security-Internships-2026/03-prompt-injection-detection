"""
run_two_app_login_experiment.py — orchestrates the full login-based
two-app cross-tenant experiment. This script only calls HTTP endpoints
on victim_app:8001 and attacker_app:8002 - it has no import of either
app's internals. Ground truth (the PIN) is known here, in the researcher
script only; attacker_app never receives it.
"""
import csv, time, os, requests

VICTIM_URL = "http://localhost:8001"
ATTACKER_URL = "http://localhost:8002"
OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "two_app_login_experiment.csv"))
N_TRIALS = 15
GAP = 1.0

VICTIM_USER = {"username": "user_a", "password": "researcher-controlled-password"}
ATTACKER_USER = {"username": "user_b", "password": "researcher-controlled-password"}
VICTIM_SECRET = "482913"           # ground truth - researcher + victim app only
ATTACKER_GUESS = "unknown guess"   # deliberately wrong probe content

def victim_login():
    return requests.post(f"{VICTIM_URL}/login", json=VICTIM_USER, timeout=10).json()["token"]

def attacker_login():
    return requests.post(f"{ATTACKER_URL}/login", json=ATTACKER_USER, timeout=10).json()["token"]

def flush_both():
    requests.post(f"{VICTIM_URL}/flush", timeout=10)

def run():
    rows = []

    print("=== CONDITION A: User B probes, User A has NOT logged in / submitted ===")
    for i in range(N_TRIALS):
        flush_both()
        time.sleep(0.3)
        time.sleep(GAP)
        tok_b = attacker_login()
        r = requests.post(f"{ATTACKER_URL}/probe", json={"guess": ATTACKER_GUESS},
                           headers={"Authorization": tok_b}, timeout=30).json()
        requests.post(f"{ATTACKER_URL}/logout", headers={"Authorization": tok_b}, timeout=10)
        r.update({"condition": "A_no_victim", "trial": i})
        rows.append(r)
        print(f"  A[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

    print("\n=== CONDITION B: User A logs in, submits PIN, logs out -> then User B probes ===")
    for i in range(N_TRIALS):
        flush_both()
        time.sleep(0.3)

        tok_a = victim_login()
        requests.post(f"{VICTIM_URL}/submit", json={"secret": VICTIM_SECRET},
                       headers={"Authorization": tok_a}, timeout=30)
        requests.post(f"{VICTIM_URL}/logout", headers={"Authorization": tok_a}, timeout=10)

        time.sleep(GAP)

        tok_b = attacker_login()
        r = requests.post(f"{ATTACKER_URL}/probe", json={"guess": ATTACKER_GUESS},
                           headers={"Authorization": tok_b}, timeout=30).json()
        requests.post(f"{ATTACKER_URL}/logout", headers={"Authorization": tok_b}, timeout=10)
        r.update({"condition": "B_after_victim", "trial": i})
        rows.append(r)
        print(f"  B[{i}] wall_clock={r['wall_clock_latency']:.4f}s cached_tokens={r['cached_tokens']}/{r['prompt_tokens']}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {len(rows)} rows to {OUT_PATH}")

if __name__ == "__main__":
    run()
