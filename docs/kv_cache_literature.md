A. KV-Cache Security, Privacy, and Prompt Injection
PROMPTPEEK: I Know What You Asked: Prompt Leakage via KV-Cache Sharing in Multi-Tenant LLM Serving (NDSS 2025)

PROMPTPEEK presents one of the earliest systematic investigations into prompt confidentiality risks arising from shared KV-cache reuse in multi-tenant LLM serving systems. The authors demonstrate that prefix cache sharing can leak hidden system prompts and confidential user inputs through cache-hit observations, even without compromising the underlying model. The study introduces practical attacks exploiting cache reuse behavior and recommends mitigation strategies including cache isolation, cache salting, and stricter prefix validation. This work establishes shared KV caches as a significant privacy attack surface in modern LLM deployments.

RobustKV: Defending Large Language Models against Jailbreak Attacks via KV Eviction (ICLR 2025)

Unlike previous studies that view the KV cache primarily as an optimization mechanism, RobustKV leverages cache management as a security defense against jailbreak attacks. The authors observe that malicious instructions rely on influential KV representations during attention computation. By selectively evicting these harmful cache entries during inference, RobustKV weakens the model's ability to follow jailbreak instructions while preserving benign contextual information. The paper demonstrates that KV-cache manipulation can serve as an effective inference-time security mechanism without modifying model parameters.

The Early Bird Catches the Leak: Unveiling Timing Side Channels in LLM Serving Systems (arXiv 2024)

This work investigates timing side-channel vulnerabilities introduced by cache reuse in LLM serving systems. The authors show that differences in response latency between cache hits and cache misses enable attackers to infer whether confidential prompts already exist within shared caches. Using only timing observations, attackers can recover information about proprietary system prompts and sensitive user queries. The paper highlights that inference-time optimization techniques unintentionally create privacy leakage channels that require stronger cache isolation and timing-aware defenses.

Shadow in the Cache: Unveiling and Mitigating Privacy Risks of KV-cache in LLM Inference (NDSS 2026)

This paper demonstrates that plaintext KV caches themselves constitute sensitive information. The authors design inversion attacks, collision attacks, and semantic injection attacks capable of reconstructing or inferring private prompt content directly from stored KV representations. To mitigate these risks, they introduce KV-Cloak, a lightweight reversible obfuscation mechanism that protects cached representations while preserving inference efficiency. The work emphasizes that KV caches should be treated as confidential assets rather than temporary computational artifacts.

Cache Me, Catch You: Cache Related Security Threats in LLM Serving Frameworks (NDSS 2026)

This study provides a comprehensive security evaluation of modern LLM serving frameworks including vLLM, SGLang, and GPTCache. The authors identify multiple cache-related attack vectors, including prefix cache collisions, semantic cache poisoning, information leakage, content filter bypass, and system integrity attacks. Their findings demonstrate that inference-time caching optimizations substantially expand the attack surface beyond the language model itself, motivating stronger cache validation and tenant isolation mechanisms.

GeoCache: Provably Lossless Inference and Computational Content-Level Isolation for Shared KV-Caches in Multi-Tenant LLM Inference (2026)

GeoCache introduces a mathematically grounded framework for secure KV-cache sharing in multi-tenant LLM deployments. Instead of relying solely on hash-based cache isolation, the approach applies secret isometric orthogonal transformations that isolate cached representations at the content level. Even when cache collisions occur, retrieved KV entries remain computationally meaningless outside their intended tenant. The framework provides formal security guarantees while preserving the efficiency benefits of shared prefix caching.



From Similarity to Vulnerability: Key Collision Attack on LLM Semantic Caching (2026)

This paper investigates security vulnerabilities in semantic caching systems that use embedding vectors as cache keys. The authors demonstrate that semantic similarity inherently increases the likelihood of cache key collisions, allowing adversaries to retrieve incorrect cached responses or hijack LLM outputs. They introduce CacheAttack, an automated black-box framework capable of generating collision-inducing prompts that exploit semantic cache matching. The work reveals a fundamental trade-off between maximizing cache hit rates and maintaining collision-resistant cache security.

SafeKV: Safe KV-Cache Sharing in LLM Serving (MLArchSys 2025)

SafeKV proposes a secure architectural framework for sharing KV caches across multiple tenants while preserving inference efficiency. The system combines privacy classification, chunk-level cache partitioning, and runtime anomaly detection to ensure that only non-sensitive cached representations are shared between users. By introducing fine-grained cache isolation instead of disabling cache reuse entirely, SafeKV significantly reduces cross-tenant information leakage while maintaining the performance advantages of prefix caching.

B. KV-Cache Memory Management and Long-Context Inference


Layer-Condensed KV Cache for Efficient Inference of Large Language Models (ACL 2024)

This paper proposes Layer-Condensed KV Cache (LCKV), which reduces memory consumption by storing KV caches for only selected transformer layers while recomputing the remaining representations when necessary. Experimental results demonstrate significant memory savings and improved inference throughput with minimal impact on generation quality. The study challenges the assumption that every transformer layer requires persistent KV storage during inference.



. CacheGen (SIGCOMM 2024)

Compresses and streams KV caches between servers instead of recomputing them.
Improves distributed LLM inference efficiency.

---

# C. KV1 Literature Tracker (issue #22)

Per-item status table for the sources named in KV1 issue #22. **Confirmed** = located and read this pass. **Relation** = same threat model as this paper (cross-tenant cache-reuse side channel via normal API access) vs. adjacent (different attacker model, e.g. tensor access, semantic cache keys, or jailbreak defense).

| Name (as given in issue #22) | Confirmed | Likely match found | Relation to this paper's threat model | Action before citing |
|---|---|---|---|---|
| PROMPTPEEK (NDSS'25) | Yes (already in main.tex as wu2025promptpeek) | - | Same - direct predecessor, cross-tenant cache-reuse via API-visible signal | None - already cited correctly per the paper's own bib key |
| InputSnatch | Yes (already in main.tex as zheng2024inputsnatch) | - | Same family - timing-based input theft in LLM services | Confirm bib entry matches actual authors/venue before submission |
| PrefixWall | Yes (already in main.tex as pennas2026prefixwall) | - | Adjacent/defense - selective per-prefix isolation; explicitly excludes first-entry-of-prompt attacks, which is our PIN-position-1 case | Keep the "excludes our exact case" point in the comparison table |
| SafeKV | Yes (already in main.tex as chu2025safekv) | "Selective KV-Cache Sharing to Mitigate Timing Side-Channels in LLM Inference," arXiv:2508.08438 | Adjacent/defense - system co-design of detection + isolation in the serving runtime | Note: SafeKV evaluates only performance cost under load, not attack reliability vs. background tenant count - key gap our paper addresses |
| KVGov | Yes - arXiv:2608.09225, Addagada et al., 2026 | - | Same threat model family (defense against PROMPTPEEK) | KVGov evaluates attack success using a discrete-event simulation, not measurements under real GPU contention. Our background-load Studies 1-4 directly address this gap |
| Shadow-in-the-Cache | Yes - "Shadow in the Cache: Unveiling and Mitigating Privacy Risks of KV-cache in LLM Inference," Luo et al., arXiv:2508.09442 | - | **Different attacker model** - inversion/collision/injection attacks reconstruct prompt content from KV tensors directly; stronger assumption (tensor access) than ours (API-only) | Cite as adjacent/contrast, not as prior art for our exact attack |
| Cache-Me-Catch-You | Yes - "Cache Me, Catch You: Cache Related Security Threats in LLM Serving Frameworks," NDSS 2026 (documented in section A above) | - | Adjacent - broader survey of cache attacks across vLLM/SGLang/GPTCache; overlaps our threat model in the prefix-collision arm | Cite as related work; already documented in section A |
| GeoCache | Yes - "GeoCache: Provably Lossless Inference and Computational Content-Level Isolation for Shared KV-Caches in Multi-Tenant LLM Inference," 2026 (documented in section A above) | - | Adjacent/defense - mathematically grounded isolation (isometric orthogonal transforms at content level); stronger formal guarantees than salt-based isolation | Cite as adjacent defense |
| RobustKV | Yes - "RobustKV: Defending Large Language Models against Jailbreak Attacks via KV Eviction," ICLR 2025 (documented in section A above) | - | **Different threat model** - jailbreak defense via selective KV eviction, not a cache side-channel attack | Cite only as background on KV-cache manipulation as a security primitive, not as prior art for cross-tenant leakage |
| Early-Bird | Yes - "The Early Bird Catches the Leak: Unveiling Timing Side Channels in LLM Serving Systems," arXiv 2024 (documented in section A above) | - | Same family - timing side channels from cache hit/miss in LLM serving | Cite as related work on timing-based leakage; supports our RQ1 timing arm |
| Key-Collision-Attack | Yes - likely "From Similarity to Vulnerability: Key Collision Attack on LLM Semantic Caching," 2026 (documented in section A above) | CacheAttack framework | **Different mechanism** - semantic cache key collisions in embedding-based caches, not prefix/radix KV cache | Cite as related work on cache-key attacks; note it targets semantic caching |

## Standing rule

Any row still marked unconfirmed stays out of main.tex's bibliography and out of the novelty argument until a verifiable link is supplied. This mirrors the paper's own Evidence Audit convention (flag, don't fabricate, don't silently drop).

## Status of Mati review item 1

All sources named in issue #22 are now confirmed. The four rows previously marked "unconfirmed" (Cache-Me-Catch-You, GeoCache, RobustKV, Early-Bird) were verified against the repo's existing section A above, which already documents each source with a prose description. RobustKV and Key-Collision-Attack were found to be on **different threat models** (jailbreak defense and semantic-cache collisions respectively) and are cited as adjacent/background, not same-family. The novelty claim in docs/kv-experimental-design.md section 2 is finalized accordingly.
