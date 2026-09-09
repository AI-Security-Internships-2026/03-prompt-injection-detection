

# KV-Cache Security Literature Tracker

**Authors:** Ehsan Ullah Jamshaid, Rana Abu Bakar
**Last Updated:** 2026-09-09
**Status:** created/updated as part of KV1's novelty freeze (issue #22). Narrative novelty argument lives in `docs/kv-experimental-design.md` §2 — this file is the flat per-item tracking table it's built on, kept separate so it's easy to update as citations get confirmed.

Columns: **Confirmed** = located and read (at least abstract) this pass. **Relation** = same threat model as this paper (cross-tenant cache-*reuse* side channel via normal API access) vs. adjacent (different attacker model, e.g. tensor access, or different problem, e.g. compression).

---

| Name (as given in issue #22) | Confirmed this pass | Likely match found | Relation to this paper's threat model | Action before citing |
|---|---|---|---|---|
| PROMPTPEEK (NDSS'25) | Yes (already in `main.tex` as `wu2025promptpeek`, "I know what you asked: Prompt leakage via kv-cache sharing in multi-tenant LLM serving") | — | Same — direct predecessor, cross-tenant cache-reuse via API-visible signal | None — already cited correctly per the paper's own bib key |
| InputSnatch | Yes (already in `main.tex` as `zheng2024inputsnatch`) | — | Same family — timing-based input theft in LLM services | Confirm bib entry matches actual authors/venue before submission |
| PrefixWall | Yes (already in `main.tex` as `pennas2026prefixwall`) | — | Adjacent/defense — selective per-prefix isolation; explicitly excludes first-entry-of-prompt attacks, which is our PIN-position-1 case | Keep the "excludes our exact case" point in the comparison table — it's a real differentiator, not a weakness of our paper |
| SafeKV | Yes (already in `main.tex` as `chu2025safekv`) | "Selective KV-Cache Sharing to Mitigate Timing Side-Channels in LLM Inference," arXiv:2508.08438 | Adjacent/defense — system co-design of detection + isolation in the serving runtime | Double-check author list on the arXiv version matches the bib entry (title matches; did not cross-check authors). Note: SafeKV evaluates only the *performance cost* of its own isolation mechanism under load, not whether an unmitigated attack's reliability changes as background tenant count increases — this is a key gap our paper addresses. |
| KVGov | **Confirmed** — arXiv:2608.09225 ("Governing the KV Cache: Preventing Timing Side-Channel Leakage in Multi-Tenant LLM Inference"), Addagada et al., 2026 | — | Same threat model family (defense against PROMPTPEEK) | **Important gap to cite:** KVGov evaluates attack success rate against PROMPTPEEK using a **discrete-event simulation** with fixed hit/miss latencies rather than measurements under real GPU contention, and explicitly identifies field validation with real concurrent tenants as future work. Our background-load experiments (Studies 1–4) directly address this gap by measuring attack reliability under real GPU contention with concurrent background tenants. |
| Shadow-in-the-Cache (claimed NDSS'26) | Partially — found "Shadow in the Cache: Unveiling and Mitigating Privacy Risks of KV-cache in LLM Inference" (Luo et al., arXiv:2508.09442); NDSS'26 acceptance not confirmed in this pass | Same title, plausible match | **Different attacker model** — inversion/collision/injection attacks reconstruct prompt *content* from KV tensors directly; stronger assumption (tensor access) than our API-only threat model | Cite as adjacent/contrast, not as prior art for our exact attack; verify NDSS'26 venue claim separately |
| Cache-Me-Catch-You (claimed NDSS'26) | No | — | Unknown | Get source before citing |
| GeoCache | No | — | Unknown | Get source before citing |
| RobustKV (claimed ICLR'25) | No — nothing on-topic surfaced | — | Unknown (name suggests possible overlap with unrelated "robustness" work, e.g. jailbreak defense, not cache side channels — do not assume topical match from name alone) | Get source before citing; do not assume this is about cache side channels |
| Early-Bird (arXiv) | No | — | Unknown | Get source before citing |
| Key-Collision-Attack (claimed 2026) | No — note the "Collision Attack" vector inside Shadow-in-the-Cache is a *different, already-named* thing; do not conflate | — | Possibly a naming collision with Shadow-in-the-Cache's internal attack name, or a distinct paper | Confirm whether this is actually a separate citation or a mis-transcription of Shadow-in-the-Cache's attack name |

---

## Standing Rule

Any row above still marked "No" / unconfirmed stays out of `main.tex`'s bibliography and out of the novelty argument until someone supplies a verifiable link. This mirrors the paper's own Evidence Audit convention (flag, don't fabricate, don't silently drop).

**KVGov specifically:** This paper was not in the original literature tracker but is now confirmed via arXiv:2608.09225 and is directly relevant as a prior work gap that our background-load experiments address. The supervisor should review whether this citation should be added to the paper's related work section, and if so, ensure the "discrete-event simulation" characterization accurately represents the paper's methodology.