import sys
sys.path.insert(0, "/home/rana/promptpeek-repro/apps")
from shared_client import send_to_sglang, flush_cache

SHARED_PREFIX = "System: You are a helpful assistant. " * 50
PROMPT = SHARED_PREFIX + "The secret code is 492015."

print(flush_cache())

print("\n=== TEST 1: cross-tenant, different salts (expect LOW/ZERO cached_tokens on 2nd) ===")
r1 = send_to_sglang(PROMPT, cache_salt="tenant_victim")
print("Victim  (salt=tenant_victim):", r1["cached_tokens"], "/", r1["prompt_tokens"])
r2 = send_to_sglang(PROMPT, cache_salt="tenant_attacker")
print("Attacker(salt=tenant_attacker):", r2["cached_tokens"], "/", r2["prompt_tokens"])

print("\n=== TEST 2: same-tenant repeat (expect HIGH cached_tokens) ===")
r3 = send_to_sglang(PROMPT, cache_salt="tenant_victim")
print("Victim  (salt=tenant_victim again):", r3["cached_tokens"], "/", r3["prompt_tokens"])
