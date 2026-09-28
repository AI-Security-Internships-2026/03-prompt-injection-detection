# vLLM Environment Notes (Week 8)

**Purpose:** Assess whether vLLM is a suitable caching-aware inference backend for the Week 9–11 persistence experiments. Everything below is sourced from official vLLM documentation and GitHub, fetched directly this week — not from memory. Anything I could not verify is marked as such.

---

## Why vLLM is being considered

vLLM is the most widely referenced open-source, self-hostable inference server implementing Automatic Prefix Caching (APC) via its PagedAttention mechanism. Multiple 2025–2026 security papers found this week (PrefixWall, CacheProbe, the official vLLM security advisory, PROMPTPEEK) all target vLLM or SGLang specifically, which means the caching behavior in question is realistic and already an active research target — not a synthetic setup unique to this project.

## Prefix caching / KV-cache functionality — confirmed

- **Automatic Prefix Caching (APC) is a real, documented, controllable feature.** When enabled (`enable_prefix_caching=True`), vLLM reuses cached KV blocks for any new request that shares a prefix with a previously processed one, at block granularity (default 16 tokens per block).
- **Cache reuse can be controlled per-request via `cache_salt`.** Including a `cache_salt` string in a request hashes it into the first cache block, so only requests sharing the same salt can reuse each other's cached blocks. This is officially documented as a security/isolation feature (to prevent cross-user timing attacks) — but for our purposes, it's also exactly the lever needed to deliberately force a cache-hit vs. cache-miss condition for the same conversation in a controlled experiment. **This is directly relevant to Week 9's harness design.**

## Whether cache hit/miss behavior can be measured — confirmed, with a caveat

- vLLM exposes a Prometheus-compatible `/metrics` HTTP endpoint. In the current (v1) metrics design, this includes `vllm:prefix_cache_queries` and `vllm:prefix_cache_hits` as counters, plus `vllm:gpu_cache_usage_perc`. A hit rate can be computed directly from these (`hits / queries`), or read as a live gauge in tools like the Red Hat-documented triage workflow, which reports lines like `Prefix cache hit rate: 29.7%` during normal operation.
- Separately, cache hits/misses are also observable indirectly via **Time-To-First-Token (TTFT) timing** — this is the mechanism the official vLLM security advisory (GHSA-4qjh-9fv9-r85r) confirms: a cache hit measurably speeds up TTFT, and this difference is large enough to reliably distinguish hit from miss.
- **Caveat — what these metrics do NOT give you:** these are aggregate, request/block-level statistics (did a hit occur, how full is the cache), not the literal contents of the cached key/value tensors. I found no evidence in vLLM's documented API or metrics surface that it exposes raw KV tensor values for external inspection. **Do not assume tensor-level introspection is available without verifying it directly against the vLLM source or an issue/PR confirming it** — this is exactly the kind of claim the project brief asked me not to make without proof, and I don't have that proof.

## Can the system run locally? Hardware requirements

- vLLM is designed for GPU inference (CUDA). I did not find documentation suggesting a supported, performant CPU-only mode for realistic experiments — vLLM's entire value proposition (PagedAttention, continuous batching) is built around GPU memory management, so CPU-only vLLM would likely be either unsupported or so slow as to be impractical for anything beyond a trivial smoke test.
- **This is a meaningful contrast with your Week 5–7 ML detector work**, which ran CPU-only by design (TF-IDF + Logistic Regression). The KV-cache project cannot inherit that same "no GPU needed" property — **GPU access should be confirmed as available before Week 9 implementation begins**, not assumed.
- Real-world example figures found this week (Red Hat vLLM triage guide): a 32B FP16 model on a single H100 GPU leaves only ~4.4 GiB free for KV cache after model weights — meaning even model size choice interacts directly with how much room there is to actually observe interesting caching behavior. A smaller model (e.g., a 7–8B parameter model) would leave much more cache headroom for experimentation and is likely the more practical choice for a first working prototype.

## What model(s) could reasonably be used

- Nothing here was directly confirmed by documentation for this specific project's needs, so this is a reasoned recommendation, not a verified fact: a small-to-mid-size open-weight model (7–8B parameter class, e.g. something in the Llama 3.1 8B or Qwen2.5 7B family, both of which appeared as commonly used research-grade models in the papers found this week) is the most practical starting point — enough KV-cache headroom to run repeated experiments on typical GPU allocations, and small enough to iterate quickly during Week 9–10 harness development.

## Limitations / risks

- **GPU dependency is the primary risk.** If GPU access isn't available or is heavily shared/rate-limited, the whole Phase 1 timeline (Weeks 9–11) is at risk, since there's no realistic CPU fallback for vLLM specifically.
- **Tensor-level cache inspection is unverified.** If the eventual experimental design needs to look at literal cached key/value values (not just hit/miss), this may require either (a) patching vLLM internals directly, which is a nontrivial engineering task, or (b) switching to a lower-level framework like HuggingFace `transformers` with `past_key_values` exposed directly, which offers full internal access but loses the realistic production-serving characteristics (block-level caching, multi-request scheduling) that make vLLM the more externally-valid choice.
- **cache_salt as an experimental control is a documented security feature, not a research tool** — it should work for forcing cache-on/cache-off conditions, but this should be smoke-tested early in Week 9 to confirm it behaves as expected under the specific multi-turn conversation pattern this project needs, rather than assumed to generalize perfectly from its documented use case (cross-tenant isolation).
- **PrefixWall and CacheProbe were not read in full** — if either already builds tooling for observing/controlling vLLM cache behavior beyond what's in vLLM's own docs, that tooling might be directly reusable and should be checked before building a harness from scratch.

## What must be confirmed before Week 9 implementation

1. **GPU access** — confirm what's actually available (cloud allocation, lab hardware, shared cluster) before committing to a model size or experiment scale.
2. **Whether `cache_salt` control behaves as expected** for the specific "same conversation, force cache reuse vs. force cache miss" pattern this project needs — a 30-minute smoke test, not a full experiment.
3. **Whether aggregate metrics (hit rate, TTFT divergence) are sufficient signal for the Week 9 threat model's primary test**, or whether the project will need to go further into tensor-level inspection (which has a much higher engineering cost and would push into `transformers`-level access instead of standard vLLM serving).
4. **Full reads of PrefixWall and CacheProbe** — both may contain directly reusable methodology or tooling for measuring/controlling cache behavior externally.
