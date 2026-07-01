# Literature Review: Prompt Injection Detection and Defence for LLM-Based Applications

**Student:** Ehsan Ullah Jamshaid
**GitHub:** ejamshaidbese24seecs-glitch
**Updated:** 01-07-2026

---

## Instructions

For each paper or resource you read, complete one entry below.
Aim for at least **10 papers** by the end of Week 2.
Use Google Scholar, IEEE Xplore, ACM DL, arXiv, or USENIX Security.

---

### Paper 1 — Prompt Injection Attacks and Defenses

| Field | Content |
|---|---|
| **Full title** | Prompt Injection Attacks and Defenses in LLM-Integrated Applications |
| **Authors** | Yupei Liu, Yuqi Jia, Runpeng Geng, Jinyuan Jia, Neil Gong |
| **Year** | 2023 |
| **Venue** | arXiv |
| **URL / DOI** | https://arxiv.org/abs/2310.12815 |
| **Method** | Systematic framework to classify all prompt injection attacks and defences |
| **Dataset** | Custom examples tested across 10 LLMs and 7 tasks |
| **Key result** | Identified and categorised 9 major prompt injection attack types |
| **Limitation** | Does not provide a ready-to-use real-time detection tool |
| **Relevance to our project** | Directly relevant — covers all attack types we need to detect |

**Notes / Quotes:**
> Most comprehensive paper on prompt injection. Best starting point for our project.
> Tests 5 attacks and 10 defences across 10 LLMs and 7 tasks.
> Key finding: no existing defence is sufficient — all have weaknesses.
> Combined Attack (mixing escape characters + context ignoring + fake completion) is the most powerful attack found.
> Defines target task vs injected task formally — gives us a clear framework to design our detector around.
> Practical connection: the Context Ignoring attack described here matches exactly what we found in real Garak-generated attacks during Week 2 exploration.

---

### Paper 2 — Indirect Prompt Injection in Real-World LLMs

| Field | Content |
|---|---|
| **Full title** | Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection |
| **Authors** | Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, Mario Fritz |
| **Year** | 2023 |
| **Venue** | arXiv |
| **URL / DOI** | https://arxiv.org/abs/2302.12173 |
| **Method** | Demonstrated indirect injection attacks on real deployed LLM applications |
| **Dataset** | Real-world LLM apps including Bing Chat and ChatGPT plugins |
| **Key result** | Successfully exfiltrated private data via indirect injection attacks |
| **Limitation** | Focuses on demonstrating attacks only — limited defence recommendations |
| **Relevance to our project** | Very relevant — shows exactly what our detection layer needs to catch |

**Notes / Quotes:**
> First major paper on indirect prompt injection in real systems.
> Demonstrated first ever AI worm that spreads itself via email.
> Base64 encoded attacks successfully bypassed Bing Chat safety filters.
> Six categories of threats: information gathering, fraud, malware, intrusion, manipulated content, availability.
> Key insight: our detector must scan external content (emails, webpages, documents) not just user input.

---

### Paper 3 — PromptBench: Robustness Evaluation of LLMs

| Field | Content |
|---|---|
| **Full title** | PromptBench: Towards Evaluating the Robustness of Large Language Models on Adversarial Prompts |
| **Authors** | Zhu et al., Microsoft Research |
| **Year** | 2023 |
| **Venue** | arXiv |
| **URL / DOI** | https://arxiv.org/abs/2306.04528 |
| **Method** | Benchmark framework for testing LLM robustness against adversarial inputs |
| **Dataset** | Multiple NLP datasets with adversarial prompt variations |
| **Key result** | LLMs are highly vulnerable to adversarial prompts across all tested models |
| **Limitation** | Focuses on evaluation only — not real-time detection |
| **Relevance to our project** | Useful for evaluating our detection system performance |

**Notes / Quotes:**
> Can be used as evaluation framework for our prototype. Maintained by Microsoft.
> Focuses on adversarial robustness broadly — includes typos, synonym swaps, and distribution shifts.
> Useful baseline for stress-testing our future detector against many types of input perturbation.
> Limitation: does not specifically focus on prompt injection taxonomy like Paper 1.

---

### Resource 4 — HackAPrompt Dataset

| Field | Content |
|---|---|
| **Full title** | HackAPrompt: Exposing the Prompt Injection Attack Surface in Aligned Large Language Models |
| **Authors** | Sander Schulhoff et al. |
| **Year** | 2023 |
| **Venue** | NeurIPS / HuggingFace |
| **URL / DOI** | https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset |
| **Method** | Crowdsourced competition where 2,800+ participants tried to break LLM applications across 10 challenge levels |
| **Dataset** | 600,000+ real human-written prompt injection attempts with labelled success/failure |
| **Key result** | Identified novel attack types not seen in academic literature |
| **Limitation** | Mostly direct injection attacks — limited indirect or multimodal coverage |
| **Relevance to our project** | Primary training and evaluation dataset for our detection model |

**Notes / Quotes:**
> Largest real-world human-generated prompt injection dataset publicly available.
> Practically tested: loaded the full dataset (601,757 rows) using HuggingFace datasets library in src/explore_hackaprompt.py.
> Found 13 columns including level, prompt, user_input, completion, correct, and score.
> Measured actual success rate: 77,936 out of 601,757 attempts succeeded (12.95%).
> Found recurring attack signature: many attacks try to make AI say "I have been PWNED" as proof of successful jailbreak.

---

### Resource 5 — Garak: LLM Vulnerability Scanner

| Field | Content |
|---|---|
| **Full title** | garak: A Framework for Security Probing Large Language Models |
| **Authors** | Leon Derczynski et al. |
| **Year** | 2023 |
| **Venue** | GitHub / Open Source (NVIDIA) |
| **URL / DOI** | https://github.com/leondz/garak |
| **Method** | Automated probe-based scanning tool that sends crafted adversarial inputs to a target LLM |
| **Dataset** | Built-in probe library including promptinject, dan, encoding attacks |
| **Key result** | Can systematically test an LLM against dozens of known vulnerability categories |
| **Limitation** | Designed for attacking/testing LLMs — no built-in real-time detection layer |
| **Relevance to our project** | Used to generate attack test cases and benchmark our detector |

**Notes / Quotes:**
> Installed and ran Garak v0.15.1 locally using promptinject probe module.
> Generated 1,280 test attempts across 3 attack templates: HijackHateHumans, HijackKillHumans, HijackLongPrompt.
> Extracted 446 unique attack prompts from the report for further analysis.
> Week 3: ran against