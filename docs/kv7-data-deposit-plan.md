# KV7 — Data Deposit Plan (DOI-ready)

## Target repository

Zenodo (CERN). Free, DOI-issuing, accepted by major security venues.

## Deposit contents

Everything in paper-results/ verbatim:
- manifest.json — SHA-256 hashes for all 75 files
- paper_numbers_kv.json — every paper number with bootstrap 95% CIs
- kv-paper-table-drafts.md — Tables 1-5
- environment.md — hardware/software pins
- reproducibility.md — exact server launch commands
- raw/kv2/ — 3 baseline CSVs
- raw/kv5_v2/ — 63 perf/security CSVs
- raw/kv4/ — detector metrics

Plus supplementary files:
- analysis/kv6/generate_paper_artifacts.py
- docs/kv-rq-evidence-audit.md
- docs/kv7-reproducibility-checklist.md
- docs/kv7-data-deposit-plan.md

## Deposit size

Approximately 2 MB. No model weights, no Docker images.

## Metadata

- Title: Cross-Tenant KV-Cache Information Leakage in Local LLM Serving: Detection and Mitigation via Native Cache Isolation — data and reproducibility artifact
- Authors: Ehsan Ullah Jamshaid, Rana Abu Bakar
- License: MIT (code) / CC-BY-4.0 (data)
- Version: 1.0.0
- Related identifier: paper DOI (add at camera-ready)
- Keywords: LLM inference security, KV cache, side channel, SGLang, vLLM, mitigation

## Provenance

Every file traces to paper-kv-results-freeze-v2. The manifest.json
inside the deposit is the same one produced by generate_paper_artifacts.py.
No re-hashing.

## Responsible disclosure record

No coordinated disclosure was filed. Rationale: the vulnerability is a
configuration trade-off already documented by SGLang (native extra_key,
--disable-radix-cache) and by prior work (PROMPTPEEK NDSS'25, SafeKV
MLArchSys'25). It is not a memory-safety issue, an unpatched code defect,
or a novel exploit class. Supervisor acknowledged this on 2026-10-04.

## Timing

Deposit paper-results/ to Zenodo with access restricted until the paper
is accepted. At acceptance, flip to open and cite the DOI in the
camera-ready.

## Pre-deposit checklist

- [ ] paper-results/manifest.json regenerated against the final freeze commit
- [ ] kv-paper-submission-v1 tag pushed to GitHub
- [ ] No private paths, keys, or credentials in any CSV
- [ ] All 75 files match their manifest SHA-256
- [ ] README.txt in deposit root explaining structure
