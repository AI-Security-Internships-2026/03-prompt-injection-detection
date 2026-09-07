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
