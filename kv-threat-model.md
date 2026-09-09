# KV Threat Model (Frozen — KV1)

**Authors:** Ehsan Ullah Jamshaid
**Last Updated:** 2026-09-09
**Status:** DRAFT for supervisor sign-off. Once approved, this document is frozen for Paper 1 and changes require a new issue.
**Scope:** applies to both SGLang and vLLM tracks. Framework-specific mechanics are called out explicitly where they differ.

---

## 1. System and Actors

**Victim tenant/application.** An independent client process that submits prompts (some containing a secret/candidate value) to a shared inference backend. In our harness this is `apps/victim_app.py` (SGLang) / the victim role in `harness/cross_tenant_test.py` (vLLM). The victim has no attacker-facing interface and does not coordinate with the attacker process in any way; isolation of the two processes is verified by source audit (no cross-import).

**Attacker tenant/application.** An independent client process (`apps/attacker_app.py` / attacker role in the vLLM harness) that issues its own HTTP requests to the same backend and observes only its own responses.

**Shared inference server/runtime.** A single self-hosted serving instance — SGLang 0.5.17 or vLLM — that multiplexes requests from both processes onto one model instance and one cache.

**Model, tokenizer, cache-matching mechanism.**
- Model: `deepseek-ai/DeepSeek-R1-Distill-Llama-8B`, same weights for both frameworks.
- SGLang: RadixAttention — a radix tree over cached KV state, matched by longest common token prefix, subject to eviction.
- vLLM: PagedAttention prefix-cache with block-level hashing/matching (Phase 0–4 harness).
- Both expose (directly or via response metadata) some signal correlated with prefix-cache reuse; the exact signal differs by framework (Section 3, RQ3).

**Tenant/cache isolation boundary.** By default, both frameworks place all requests to a given server process in a single shared cache namespace. The isolation boundary under test is *logical* (separate client processes/API callers), not *physical* (separate GPUs/servers). This is the boundary the paper claims is insufficiently enforced by default.

---

## 2. Attacker Capabilities

**The attacker CAN:**
- Submit chosen prompts/requests to the same inference service as the victim, at times and content of its choosing.
- Control full request content, including inserting candidate tokens/digits at any position.
- Repeat probes within an explicit, logged query budget (e.g. the 10-digit sequential PIN protocol, N queries per position).
- Observe only externally available response metadata/timing/cache-related effects that the tested framework actually exposes to a normal client (e.g. SGLang's `meta_info.cached_tokens`; end-to-end request latency in both frameworks).
- Possess clearly stated prior knowledge: either a small closed candidate set (candidate-identification experiments) or knowledge of secret *structure* only (e.g. "6-digit numeric PIN") for full-reconstruction experiments — never the secret value itself.
- Chain on its own previously-recovered partial guesses (never on ground truth) when the cache-matching mechanism requires sequential prefix construction.

**The attacker CANNOT:**
- Access victim prompts directly (no shared memory, no log access, no admin API).
- Access victim process memory or raw KV tensors.
- Obtain privileged access to server internals (GPU memory inspection, server logs, admin/debug endpoints) unless a specific, separately labeled experiment explicitly models such access.
- Assume arbitrary victim compromise (no assumption the victim process itself is malicious, misconfigured beyond default settings, or colluding).
- Rely on any side channel not actually exposed by the framework's normal client-facing API/response schema in the tested version.
- Assume the device is idle or that it hosts only the victim and attacker processes. An attacker sharing a GPU with other, unrelated tenants cannot make this assumption; our background-load experiments evaluate how attack reliability changes under realistic concurrent background load from other tenants.

---

## 3. Protected Assets and Attack-Success Levels

We keep these five levels textually and statistically distinct — a result belongs to exactly one level unless explicitly stated otherwise:

| Level | Name | Definition | Example metric |
|---|---|---|---|
| 0 | No leakage | Attacker cannot distinguish cache states above chance. | Detection AUC ≈ 0.5 |
| 1 | Cache-reuse / presence detection | Attacker can tell *whether* recent cross-tenant cache activity occurred, without identifying content. | Binary detection accuracy on `cached_tokens` / timing |
| 2 | Candidate identification | Attacker distinguishes among a small, closed, attacker-known candidate set (`argmax` over probe signal). | Top-1 accuracy over k candidates |
| 3 | Partial / structural reconstruction | Attacker recovers some but not all structure of an unknown secret (e.g. length, a subset of positions) without a full closed candidate set. | Per-position accuracy, edit distance to truth |
| 4 | Full information reconstruction | Attacker recovers the complete, previously-unknown secret value via sequential/chained probing over an open alphabet at each position. | End-to-end exact-match accuracy |

**Protected asset:** the victim's request content — specifically any secret-bearing substring of the prompt (in this paper, a synthetic numeric PIN) that the shared cache mechanism causes to be observably correlated with attacker-visible signals.

---

## 4. Realistic Background Load

The baseline threat model above would implicitly assume an otherwise-idle or single-tenant GPU during each trial. This is **not** a safe assumption for a shared inference deployment: an attacker sharing a GPU with other, unrelated tenants cannot assume the device is idle or that it hosts only the victim and attacker processes.

Our background-load experiments (Studies 1–4; see experimental design and results sections) evaluate how attack reliability changes under such realistic concurrent background load. Key findings from our preliminary investigation:

**Threshold degradation pattern (not gradual):**
- Attack reliability does **not** degrade gradually with tenant count but drops sharply upon the introduction of *any* competing load.
- Primary run: Cohen's $d$ drops from 0.779 (0 workers) to 0.211 (2 workers) — a 73% reduction.
- The transition from 0 to 2 workers accounts for the large majority of the reliability loss.
- Further increases from 2 to 4 to 8 workers produce no statistically significant additional change:
  - 0 vs. 2 workers: $t=8.412$, $p<0.00001$
  - 2 vs. 4 workers: $t=0.820$, $p=0.421$
  - 4 vs. 8 workers: $t=0.652$, $p=0.521$

**Gap in prior work:**
- KVGov (Addagada et al., arXiv:2608.09225) evaluates attack success rate against PROMPTPEEK using a **discrete-event simulation** with fixed hit/miss latencies rather than measurements under real GPU contention, and explicitly identifies field validation with real concurrent tenants as future work. Real deployments exhibit variable latency from GPU scheduling and memory-bandwidth contention that its simulation does not model.
- SafeKV (Chu et al.) evaluates only the *performance cost* of its own isolation mechanism under load, not whether an unmitigated attack's reliability changes as background tenant count increases.
- **To our knowledge, no prior work measures attack reliability itself as a function of concurrent, realistic background GPU load.**

**Instrumentation:**
- Background load generator: `background_load.py` / `background_load_v3.py` — configurable number of independent synthetic worker processes issuing requests to the shared SGLang backend at a configurable maximum token length.
- Occupancy instrumentation: `compute_occupancy.py` — computes, for each attacker probe interval, the fraction of its wall-clock duration that overlapped with at least one logged background-worker request interval, yielding a per-run occupancy fraction in $[0,1]$, computed from independently logged start/end timestamps.

---

## 5. Non-Goals

The following are explicitly out of scope for Paper 1 (do not weaken without a new issue):
- No hosted proprietary model API is in scope.
- No claim of generalization beyond the tested synthetic secret structure without a dedicated generalization experiment (Future Work, not Paper 1 scope).
- No quantitative reproduction of PrefixWall or SafeKV's own reported costs beyond the qualitative comparison table already in the paper draft.

---

## Definition-of-Done Checklist (This Document)

- [x] Victim, attacker, server, model/tokenizer/cache-matching, isolation boundary all defined explicitly (§1)
- [x] Attacker capabilities and limitations frozen (§2)
- [x] Protected assets and the 5 attack-success levels (0–4) defined (§3), with detection / candidate-ID / reconstruction kept distinct
- [x] Realistic background load explicitly added as a threat-model consideration, with threshold degradation findings, prior-work gap, and instrumentation details (§4)
- [x] Non-goals explicitly stated (§5)