# KV4 — Adaptive Attacker & Detector Evaluation

**Status:** Data collection and diagnosis complete. Section 5 (central vs secondary contribution) pending author decision.

## 1. Adaptive Attacker Sweep
12 conditions: probe-order x {fixed,random,adaptive} x timing x {none,delay,benign-mix,rate-limit}. 30 trials/condition, SGLang, Qwen2.5-7B-Instruct, shared-cache mode.

| Probe order | Timing | Exact-match | Per-digit accuracy |
|---|---|---|---|
| adaptive | benign-mix | 0/30 | 33.9% |
| adaptive | delay | 0/30 | 31.7% |
| adaptive | none | 0/30 | 28.9% |
| adaptive | rate-limit | 0/30 | 27.8% |
| random | rate-limit | 0/30 | 25.0% |
| random | benign-mix | 0/30 | 21.1% |
| fixed | delay | 0/30 | 8.9% |
| fixed | none | 0/30 | 9.4% |
| fixed | benign-mix | 0/30 | 6.7% |
| random | delay | 0/30 | 5.6% |
| random | none | 0/30 | 5.6% |
| fixed | rate-limit | 0/30 | 3.9% |

No condition achieved full 6-digit reconstruction. Adaptive probe-ordering gives ~3x per-digit accuracy over fixed/random ordering.

## 2. Legitimate Traffic Baseline
300 requests, 4 profiles: factual Q&A (100), code assistant (100), doc summarization (50), shared-cache-reuse (50).

## 3. Detector Evaluation
Sliding-window LCP-ratio + mutation-density classifier, window=10, non-overlapping.
Best point (lcp_thresh=0.1): precision=0.995, recall=0.990, F1=0.992, FPR=0.333.
FPR fully attributable to 2/4 legit workloads (doc summarization, shared-cache-reuse — both prefix-repetitive by design); zero FPs on factual Q&A / code-assistant traffic.

## 4. Data-quality note
Superseded file `detector_summary_final.txt` used threshold range [0.7-0.95], too high for this prompt's PIN-near-start layout, producing all-zero TP. Corrected in `detector_summary_v2.txt` with range [0.0-0.3]. Both kept per project's document-don't-hide-discrepancies standard.

## 5. Not yet done
- Central vs secondary contribution decision
- DeepSeek-side rerun to confirm no server-config contamination
