.venv\Scripts\activate# Prompt Injection Detection and Defence for LLM-Based Applications

> **CNIT/PNTLab Pisa · TECIP · Scuola Superiore Sant'Anna — AI Security Internship 2026**

---

## Research Problem

Investigate and build a robust detection layer that identifies prompt injection attacks against LLM-based applications, covering direct, indirect, and multi-turn injection scenarios.

---

## Objectives

1. Conduct a systematic literature review on the topic.
2. Design and implement a proof-of-concept prototype.
3. Evaluate the prototype on real or benchmark datasets.
4. Document findings in a final technical report.
5. Present results to the research group.

---

## Expected Deliverables

| Deliverable | Due |
|---|---|
| Literature review (`docs/literature-review.md`) | Week 2 |
| Architecture design document (`docs/proposal.md`) | Week 3 |
| Working prototype (`src/`) | Week 6 |
| Evaluation results (`experiments/results/`) | Week 7 |
| Final report (`docs/final-report.md`) | Week 8 |

---

## Recommended Technology Stack

```
Python, HuggingFace Transformers, scikit-learn, FastAPI, Pytest
```

See `requirements.txt` for pinned dependencies.

---

## Weekly Workflow

```
Monday     – Review weekly tasks in tasks/week-XX.md
Tue–Thu    – Implementation / experiments
Friday     – Document progress in docs/weekly-progress.md
Friday     – Open weekly Pull Request from your branch → dev
```

---

## Branching Policy

| Branch | Purpose |
|---|---|
| `main` | Stable, supervisor-reviewed code only |
| `dev` | Integration branch — merge weekly PRs here |
| `<your-name>-week-XX` | Your working branch for each week |

**Students must never push directly to `main`.**

---

## Pull Request Policy

- One PR per week, targeting the `dev` branch.
- PR title format: `[Week XX] Brief description`
- PR description must reference the weekly task file and summarise what was done.
- A supervisor or co-student must review before merging.

---

## Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/AI-Security-Internships-2026/03-prompt-injection-detection.git
cd 03-prompt-injection-detection

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your weekly branch
git checkout dev
git pull origin dev
git checkout -b your-name-week-01

# 5. Run the starter script
python src/main.py
```

---

## Roadmap to September 8, 2026

**Current state:** ML detector benchmarked against Meta's Llama Prompt Guard and Protect AI's LLM Guard (PR #10, merged) — best speed/accuracy in that comparison, but weak on multilingual (4% recall) and encoded/obfuscated attacks (62%). Stale `Dev` PR (#4) should be closed (issue #12). A Phase 2 research assignment already exists (issue #11): KV-cache persistence as a multi-turn injection vector — this is the project's real novel-contribution track.

**Novel contribution target:** the Phase 2 KV-cache work in issue #11 — most guardrails (including the ones just benchmarked) only look at a single turn. Showing an attack that persists across turns via the KV cache, and that current guardrails miss it, is a genuinely new result.

| Date | Milestone |
|---|---|
| Aug 2 | Close stale PR #4; land any remaining single-turn detector fixes (multilingual/encoded coverage) |
| Aug 9 | Phase 2 start (issue #11): reproduce basic KV-cache persistence/leakage behavior across conversation turns |
| Aug 16 | Build a detection/mitigation approach targeting the multi-turn KV-cache vector specifically |
| Aug 23 | Benchmark against the existing single-turn-only guardrails (LLM Guard, Prompt Guard) to show what they miss |
| Aug 30 | Full write-up of the multi-turn KV-cache threat + mitigation — this is the standout result |
| Sep 6 | Paper/report draft |
| **Sep 8** | **Final submission** |

---

## Supervisor Note

This repository is managed by **CNIT/PNTLab Pisa, TECIP, Scuola Superiore Sant'Anna**.
Please contact your supervisor before making architectural changes.
All code must be original or properly attributed.
Do **not** commit API keys, passwords, or large datasets — see `.gitignore`.
