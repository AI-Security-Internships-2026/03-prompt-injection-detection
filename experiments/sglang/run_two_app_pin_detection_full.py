"""
run_two_app_pin_detection_full.py — statistically powered version of the
manual two-app PIN detection demo. Calls victim_app:8001 and
attacker_app:8002 purely via HTTP (no internal imports), same as the
manual flow, but repeated across N random PINs for real accuracy stats.
"""
import csv, time, os, random, requests

VICTIM_URL = "http://localhost:8001"
ATTACKER_URL = "http://localhost:8002"
OUT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "results", "sglang", "two_app_pin_detection_full.csv"))
N_TRIALS = 30

VICTIM_USER = {"username": "user_a", "password": "researcher-controlled-password"}
ATTACKER_USER = {"username": "user_b", "password": "researcher-controlled-password"}

def random_pin():
    return "".join(str(random.randint(0, 9)) for _ in range(6))

def flush():
    requests.post(f"{VICTIM_URL}/flush", timeout=10)

def run():
    rows = []
    correct = 0

    for trial in range(N_TRIALS):
        gt_pin = random_pin()
        flush()
        time.sleep(0.3)

        tok_a = requests.post(f"{VICTIM_URL}/login", json=VICTIM_USER, timeout=10).json()["token"]
        requests.post(f"{VICTIM_URL}/submit", json={"secret": gt_pin}, headers={"Authorization": tok_a}, timeout=30)
        requests.post(f"{VICTIM_URL}/logout", headers={"Authorization": tok_a}, timeout=10)

        time.sleep(1.0)

        tok_b = requests.post(f"{ATTACKER_URL}/login", json=ATTACKER_USER, timeout=10).json()["token"]
        result = requests.post(f"{ATTACKER_URL}/detect_pin", headers={"Authorization": tok_b}, timeout=120).json()
        requests.post(f"{ATTACKER_URL}/logout", headers={"Authorization": tok_b}, timeout=10)

        recovered = result["recovered_pin"]
        is_match = recovered == gt_pin
        correct += is_match

        rows.append({"trial": trial, "ground_truth_pin": gt_pin, "recovered_pin": recovered, "full_match": is_match})
        print(f"trial={trial} truth={gt_pin} recovered={recovered} {'MATCH' if is_match else 'MISMATCH'}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["trial", "ground_truth_pin", "recovered_pin", "full_match"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nAccuracy: {correct}/{N_TRIALS} = {correct/N_TRIALS:.2%}")
    print(f"Saved to {OUT_PATH}")

if __name__ == "__main__":
    run()
