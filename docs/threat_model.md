# Threat Model

## Target system
- [ ] SGLang (matches original PROMPTPEEK paper)
- [ ] vLLM (APC — analogous mechanism, not the original target)

## Attacker capability
- API-level access only, co-tenant on shared inference server
- Can send arbitrary prompts, measure response latency (TTFT)
- No server-side access, no GPU-level access

## Victim capability
- Sends prompts containing secret content that becomes cached
- Normal API usage pattern

## Cached resource
- Prefix-cache / radix-tree KV cache, content-addressed, shared across tenants

## Oracle
- TTFT (time-to-first-token) as proxy for cache hit vs miss

## Attack goal
- Reconstruct victim's secret prefix via adaptive timing-based querying
