# Literature Review: Prompt Injection Detection and Defence for LLM-Based Applications

**Student:** Ehsan Ullah Jamshaid
**Updated:** 16-06-2026

---

## Instructions

For each paper or resource you read, complete one entry below.
Aim for at least **10 papers** by the end of Week 2.
Use Google Scholar, IEEE Xplore, ACM DL, arXiv, or USENIX Security.

---
# Literature Review

## Prompt Injection Detection and Defence for LLM-Based Applications

---

## 1. Paper — Prompt Injection Attacks and Defenses in LLM-Integrated Applications
- **Link:** https://arxiv.org/abs/2310.12815
- **Type:** Research Paper
- **Summary:** Comprehensive overview of all prompt injection attack types including 
  direct, indirect, multimodal, and obfuscated attacks. Also reviews defence strategies. 
  This is the most relevant paper to our project.

---

## 2. Paper — Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection
- **Link:** https://arxiv.org/abs/2302.12173
- **Type:** Research Paper
- **Summary:** First major paper specifically on indirect prompt injection. 
  Demonstrates real attacks on Bing Chat and ChatGPT plugins. 
  Very useful for understanding how indirect attacks work in practice.

---

## 3. Tool — Garak: LLM Vulnerability Scanner
- **Link:** https://github.com/leondz/garak
- **Type:** Open Source Tool
- **Summary:** Automatically tests LLMs for prompt injection and other vulnerabilities. 
  Can be used in our prototype to evaluate detection performance.

---

## 4. Dataset — HackAPrompt Dataset
- **Link:** https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset
- **Type:** Dataset
- **Summary:** Contains 600,000+ real prompt injection attempts collected from 
  a public competition. Best available dataset for training and testing 
  our detection model.

---

## 5. Benchmark — PromptBench by Microsoft
- **Link:** https://github.com/microsoft/promptbench
- **Type:** Benchmark / Tool
- **Summary:** Microsoft's benchmark for evaluating LLM robustness against 
  adversarial prompts including injection attacks. Widely used in research 
  to measure detection system performance.
## Paper Summary Template
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



---

## Reference Table (Quick Overview)

| # | Title (short) | Authors | Year | Method | Dataset | Relevance |
|---|---|---|---|---|---|---|
| 1 | Prompt Injection Attacks and Defenses | Liu et al. | 2023 | Attack taxonomy + defence review | Custom examples | High |
| 2 | Indirect Prompt Injection Real-World | Greshake et al. | 2023 | Real-world attack demos | Bing Chat, ChatGPT plugins | High |
| 3 | PromptBench | Zhu et al. | 2023 | Robustness benchmark | Multiple NLP datasets | Medium |

---

## Tools and Datasets Identified

| Name | Type | URL | Notes |
|---|---|---|---|
| HackAPrompt | Dataset | https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset | 600,000+ real prompt injection attempts from public competition |
| Garak | Library / Tool | https://github.com/leondz/garak | Automated LLM vulnerability scanner for testing injection attacks |
| PromptBench | Library / Tool | https://github.com/microsoft/promptbench | Microsoft benchmark for evaluating LLM robustness |

