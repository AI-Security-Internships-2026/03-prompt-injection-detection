# PromptPeek-Repro: KV-Cache Timing Side-Channel Research

Research into cross-tenant information leakage through shared KV/prefix-cache
mechanisms in multi-tenant LLM inference servers. Conducted as part of an
AI Security internship, using an isolated, self-controlled deployment and
synthetic secrets only.

## Research Question

> Under what conditions can shared KV/prefix-cache mechanisms expose
> information across tenants through observable cache behavior — and can
> this be extended from detecting cache activity to recovering the
> underlying private data?

## Environment

- **Hardware:** NVIDIA DGX Spark, GB10 GPU (Blackwell, sm_121), ARM64
- **Model:** deepseek-ai/DeepSeek-R1-Distill-Llama-8B
- **Frameworks tested:** vLLM, SGLang 0.5.17

## Progress Summary

### vLLM (complete, `main` branch)

| Phase | Finding |
|---|---|
| Phase 2 — KV-cache timing oracle | Cohen's d ≈ 39.7, p ≈ 2.26e-259 |
| Phase 3 — Cross-tenant timing leakage | Cohen's d ≈ 0.831, p < 0.00001 |
| Phase 4 — Information-recovery feasibility | **Negative result** (valid): no reliable secret classification under tested conditions. Secret position within the prompt strongly affects signal strength. |

Full details: `analysis/phase4/REPORT.md`

### SGLang (`week10-sglang-cross-tenant` branch)

**Stage 1-2 — Installation and single-tenant validation:**
Confirmed SGLang's radix-tree cache produces a real, significant
cold-vs-warm timing signal (d=0.839, p=0.006). An initial "no signal"
result for partial cache matches was traced to a design flaw
(insufficient divergence between test conditions) rather than a true
negative — corrected with d=-0.73, p=0.017 once fixed.

**Stage 3 — Cross-tenant cache-state leakage:**
- **Cache-hit field leakage:** 100% deterministic — `cached_tokens`
  cleanly separates victim-absent (0/188) from victim-present (181/188)
  states across all 15 trials each condition
- **Wall-clock timing leakage:** initial result showed an anomalous
  direction (victim-present condition appeared slower). Diagnosed via an
  idle-gap sweep (0s/1s/3s/5s) as **request-scheduling contention**, not
  a property of the cache mechanism. With ≥1s gap: d≈3.4-4.0, p≈0.0002,
  consistent across all non-zero gaps.

**Level 2 — Candidate identification:**
Attacker distinguishes which of 4 victim-selected synthetic candidates
was used, purely via cache observation. 100% accuracy (n=30) across all
4 entropy categories (low-entropy, predictable-prefix, structured/PIN,
high-entropy UUID), after catching and fixing a cross-probe contamination
confound in the initial design.

**Level 3-4 — Full PIN reconstruction:**
Sequential, per-digit chained recovery (each digit's probe depends on the
attacker's own previously recovered digits, since radix-tree cache
matching is sequential from the start of the string). **100% accuracy,
N=30 random 6-digit PINs.**

**Two-application architecture (realistic multi-tenant demonstration):**
Rebuilt the experiment as two genuinely separate processes:
- `apps/victim_app.py` (port 8001, "Finance Assistant") — holds a
  synthetic secret in its own process memory, exposed via login/session
- `apps/attacker_app.py` (port 8002, "Document Assistant") — zero
  code-level access to victim data (verified via source audit), only
  observes its own cache-hit counts via its own probes

Both apps have independent login systems and only interact indirectly,
through the shared SGLang backend. Full PIN reconstruction demonstrated
end-to-end through a real login → submit → logout → login → detect flow,
statistically validated at **30/30 (100%)**.

Full details: `analysis/sglang/REPORT.md`

## Key Methodology Notes

- All cross-tenant experiments use strict researcher-side separation
  between ground truth (victim's actual prompt/state) and attacker
  observations (only the attacker's own request/response data)
- Cache state is flushed (`/flush_cache`) before each independent trial
  to avoid self-priming confounds
- An idle gap (≥1s, validated) is used between victim and attacker
  requests to control for scheduler contention effects
- Two real implementation bugs were found and fixed during this work,
  documented transparently rather than hidden:
  1. A placeholder digit collided with a valid guess digit, causing it
     to spuriously "win" at every recovery position
  2. The live PIN-detection endpoint's cache-flush timing initially
     conflicted with preserving the victim's one-shot cached state
- Several other design flaws were caught and corrected during
  experimentation (self-priming, warmup requests that accidentally
  equalized test conditions) — all documented in commit history

## Repository Structure

```
apps/
    victim_app.py    — Tenant A ("Finance Assistant"), port 8001
    attacker_app.py  — Tenant B ("Document Assistant"), port 8002
    shared_client.py — shared, secret-free HTTP helper to SGLang backend

experiments/
    phase4/     — vLLM information-recovery feasibility experiments
    sglang/     — SGLang cross-tenant cache experiments

results/
    phase4/     — vLLM raw measurement data
    sglang/     — SGLang raw measurement data

analysis/
    phase4/     — vLLM statistical analysis + REPORT.md
    sglang/     — SGLang statistical analysis + REPORT.md
```

## Status

Cross-tenant KV/prefix-cache leakage has been demonstrated and
statistically validated on both vLLM and SGLang, progressing from
cache-state detection through candidate identification to full synthetic
secret (PIN) reconstruction — including a realistic two-application
architecture with genuine process-level tenant isolation.

**Current focus:** detection and mitigation research — investigating
whether this attack pattern can itself be detected by a defender
monitoring the shared backend, and testing candidate defenses
(cache partitioning, metadata restriction, rate limiting, timing jitter)
against the validated 100%-accuracy baseline.

## Research Integrity Notes

- All secrets/prompts used in leakage experiments are researcher-created
  synthetic data — no real user data at any stage
- Negative and inconclusive results are reported as such (see vLLM Phase 4)
- Design flaws and confounds are documented, not hidden, when found
- This is authorized research conducted in an isolated, self-controlled
  environment
