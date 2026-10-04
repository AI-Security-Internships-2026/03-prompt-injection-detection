# KV7 — Reproducibility Checklist

## Versions

- Models: Qwen/Qwen2.5-7B-Instruct, deepseek-ai/DeepSeek-R1-Distill-Llama-8B
- SGLang: 0.5.19
- vLLM: 0.27.1 (in .venv-rana)
- PyTorch: 2.13.0+cu130
- Transformers: 5.12.1
- NumPy: 2.3.5, pandas: 3.0.5, matplotlib: 3.11.2
- Python: 3.11.16
- CUDA: 13.0, driver 580.95.05
- Hardware: NVIDIA GB10 (DGX Spark), Ubuntu 24.04.3 LTS

## Frozen tags

- Results freeze: paper-kv-results-freeze-v2
- Freeze commit: 0f538bbfe27d675f6b9999210f5ef8e350fcb8b0
- Submission freeze: kv-paper-submission-v1 (created on the KV7 commit)

## Artifact generation

    cd ~/promptpeek-repro && python3 analysis/kv6/generate_paper_artifacts.py

Produces paper-results/ with:
- paper_numbers_kv.json — every number, bootstrap 95% CI (seed 42, N_boot=2000)
- kv-paper-table-drafts.md — Tables 1-5
- environment.md — hardware/software pins
- reproducibility.md — server launch commands
- manifest.json — SHA-256 of all files
- raw/ — copies of all source CSVs

## Data availability statement

All data and code used to generate the paper results are available at
https://github.com/AI-Security-Internships-2026/03-prompt-injection-detection
frozen at tag kv-paper-submission-v1. The paper-results/ directory
contains the raw CSVs, paper_numbers_kv.json with bootstrap 95% CIs, the
SHA-256 manifest, and the exact server launch commands. Data will be
deposited at Zenodo with a DOI before camera-ready.

## Verified reproducible

- Attack success rate (KV6-frozen)
- TTFT p50/p95/p99 with bootstrap CIs (KV6-frozen)
- Cache-hit rate with bootstrap CIs (KV6-frozen)
- Throughput with bootstrap CIs (KV6-frozen)
- Welch t + Cohen d significance tests (KV6-frozen)
- Detector P/R/F1 (prior evidence, KV4 CSVs)
- Cross-framework vLLM/SGLang (prior evidence, KV3 CSVs)
- SHA-256 manifest (75 files)

## Documented gaps

- No hosted proprietary API tested
- DeepSeek-side KV5 rerun not performed (only Qwen in KV5)
- Background-load finding not replicated (issue #18, excluded)
