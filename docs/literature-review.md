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

---

### Paper 4 — InjecAgent: Benchmark for Indirect Prompt Injection

| Field | Content |
|---|---|
| **Full title** | InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents |
| **Authors** | Qiusi Zhan, Zhixiang Fang, Rohan Bindu, Anay Parekh, Tatsunori Hashimoto, Daniel Kang |
| **Year** | 2024 |
| **Venue** | ACL 2024 |
| **URL / DOI** | https://arxiv.org/abs/2403.02691 |
| **Method** | Benchmark of 1,054 test cases targeting indirect prompt injection in tool-integrated LLM agents |
| **Dataset** | 1,054 test cases across 17 user tasks and 36 attacker objectives |
| **Key result** | Leading LLM agents vulnerable to indirect injection — GPT-4 attacked successfully in 24% of cases |
| **Limitation** | Only covers tool-integrated agents, not general LLM applications |
| **Relevance to our project** | Directly relevant — provides a ready-made benchmark we can use to evaluate our detector on indirect injection |

**Notes / Quotes:**
> First systematic benchmark specifically for indirect prompt injection in agentic settings.
> Tests 17 real user tasks including web search, email, and calendar operations.
> Found that even the strongest models (GPT-4) are significantly vulnerable to indirect injection.
> The 1,054 test cases complement our HackAPrompt dataset which is mostly direct injection.
> Key insight: indirect injection in tool-use settings is harder to detect than direct injection.

---

### Paper 5 — PromptShield: Microsoft Azure Prompt Injection Detection

| Field | Content |
|---|---|
| **Full title** | PromptShield — Azure AI Content Safety Jailbreak Detection API |
| **Authors** | Microsoft Azure AI |
| **Year** | 2025 |
| **Venue** | Microsoft Azure Documentation |
| **URL / DOI** | https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection |
| **Method** | Production API that classifies prompts as attack or safe using a trained ML model deployed at scale |
| **Dataset** | Microsoft internal dataset of real-world prompt injection attempts |
| **Key result** | Production-grade detection deployed at Azure scale — industry standard approach |
| **Limitation** | Closed source — exact model architecture and training data not disclosed |
| **Relevance to our project** | Shows what a production-grade detector looks like — our project aims to build an open-source equivalent |

**Notes / Quotes:**
> Industry benchmark for what a real deployed detector looks like.
> Microsoft deployed this at Azure scale — shows prompt injection is a real production problem.
> Closed source, so we cannot replicate it exactly, but it validates our research direction.
> Our open-source detector could serve as a free alternative to PromptShield for researchers.
> Key insight: production detectors use ML models, not keyword matching — confirms our Week 4 plan.

---

### Paper 6 — Llama Guard 3: Safety Classifier for LLM I/O

| Field | Content |
|---|---|
| **Full title** | Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations |
| **Authors** | Inan et al., Meta AI |
| **Year** | 2024 |
| **Venue** | arXiv |
| **URL / DOI** | https://arxiv.org/abs/2312.06674 |
| **Method** | Fine-tuned LLaMA model used as a safety classifier that checks both inputs and outputs of LLM conversations |
| **Dataset** | Custom safety dataset with human-annotated examples across 14 harm categories |
| **Key result** | LLM-based safety classifier outperforms rule-based approaches on novel and unseen attack types |
| **Limitation** | Computationally expensive — requires running a full LLM for every input/output check |
| **Relevance to our project** | Directly relevant — this is the approach we plan to implement in Week 6 as our LLM-based detection layer |

**Notes / Quotes:**
> Meta's production safety system for LLaMA models.
> Uses an LLM itself to detect harmful inputs — same approach we plan for Week 6.
> Covers 14 harm categories including prompt injection and jailbreaks.
> Key finding: LLM-based detection catches attacks that keyword and ML detectors miss.
> This validates our 3-layer detector plan: keyword → ML → LLM.

---

### Paper 7 — AgentDojo: Agentic Prompt Injection Benchmark

| Field | Content |
|---|---|
| **Full title** | AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents |
| **Authors** | Edoardo Debenedetti, Jie Zhang, Mislav Balunovic, Luca Beurer-Kellner, Marc Fischer, Florian Tramèr |
| **Year** | 2024 |
| **Venue** | arXiv |
| **URL / DOI** | https://arxiv.org/abs/2406.13352 |
| **Method** | Dynamic benchmark with 97 tasks across 5 real-world agentic environments testing both attacks and defences |
| **Dataset** | 97 user tasks, 629 security test cases across email, travel, banking, and workspace environments |
| **Key result** | All tested defences reduce attack success but also hurt task performance — no perfect defence exists |
| **Limitation** | Only tests agentic settings — results may not fully generalise to simpler LLM applications |
| **Relevance to our project** | Provides realistic test scenarios for evaluating our detector in agentic settings |

**Notes / Quotes:**
> Tests prompt injection in realistic agentic environments like email clients and banking apps.
> 629 security test cases make it one of the largest agentic injection benchmarks available.
> Key finding: no existing defence achieves both high security and high utility simultaneously.
> Directly relevant to our project's goal of building a detection layer that doesn't break normal functionality.
> Complements InjecAgent (Paper 6) — both focus on agentic indirect injection scenarios.

---

### Paper 8 — JailbreakBench: Standardized Jailbreak Benchmark

| Field | Content |
|---|---|
| **Full title** | JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models |
| **Authors** | Patrick Chao, Edoardo Debenedetti, Alexander Robey, et al. |
| **Year** | 2024 |
| **Venue** | NeurIPS 2024 |
| **URL / DOI** | https://jailbreakbench.github.io |
| **Method** | Standardized benchmark with 100 harmful behaviors, leaderboard for tracking attack and defence progress |
| **Dataset** | 100 standardized harmful behaviors, multiple LLM targets including GPT-4 and Claude |
| **Key result** | Provides first standardized comparison framework for jailbreak attacks and defences |
| **Limitation** | Focuses on jailbreaking rather than prompt injection specifically — partial overlap with our scope |
| **Relevance to our project** | Useful for comparing our detector against standardized benchmarks at NeurIPS level |

**Notes / Quotes:**
> NeurIPS 2024 — top tier venue, highly credible benchmark.
> First standardized leaderboard for jailbreak attacks and defences.
> Jailbreaking and prompt injection overlap significantly — many techniques apply to both.
> We can use JailbreakBench to evaluate our detector against standardized test cases.
> Key insight: standardization is important — our project should also report results on standard benchmarks.

### Resource 9 — HackAPrompt Dataset

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

### Resource 10 — Garak: LLM Vulnerability Scanner

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

**Notes / Quotes:**
> Installed and ran Garak v0.15.1 locally using promptinject probe module.
> Generated 1,280 test attempts across 3 attack templates: HijackHateHumans, HijackKillHumans, HijackLongPrompt.
> Extracted 446 unique attack prompts from the report for further analysis.
> Week 3: ran against real LLaMA 3.1 via Groq — confirmed model is vulnerable to prompt injection.
> Common pattern: attacks combine benign task + separator + Context Ignoring instruction.

---

## Tools and Datasets Identified

| Name | Type | URL | Notes |
|---|---|---|---|
| HackAPrompt | Dataset | https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset | 600,000+ real prompt injection attempts |
| Garak | Library / Tool | https://github.com/leondz/garak | Automated LLM vulnerability scanner |
| PromptBench | Library / Tool | https://github.com/microsoft/promptbench | Microsoft benchmark for LLM robustness |
| PromptShield | API / Tool | https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection | Microsoft production detection API |
| JailbreakBench | Benchmark | https://jailbreakbench.github.io | NeurIPS 2024 standardized benchmark |


## Reference Table (Quick Overview)

| # | Title (short) | Authors | Year | Method | Dataset | Relevance |
|---|---|---|---|---|---|---|
| 1 | Prompt Injection Attacks and Defenses | Liu et al. | 2023 | Attack taxonomy + defence review | Custom examples | High |
| 2 | Indirect Prompt Injection Real-World | Greshake et al. | 2023 | Real-world attack demos | Bing Chat, ChatGPT plugins | High |
| 3 | PromptBench | Zhu et al. | 2023 | Robustness benchmark | Multiple NLP datasets | Medium |
| 4 | HackAPrompt Dataset | Schulhoff et al. | 2023 | Crowdsourced competition | 600,000+ injections | High |
| 5 | Garak Tool | Derczynski et al. | 2023 | Automated red teaming | Built-in probe library | High |
| 6 | InjecAgent | Zhan et al. | 2024 | Indirect injection benchmark | 1,054 test cases | High |
| 7 | PromptShield | Microsoft Azure | 2025 | Production detection API | Internal Microsoft data | High |
| 8 | Llama Guard 3 | Meta AI | 2024 | LLM-based safety classifier | 14 harm categories | High |
| 9 | AgentDojo | Debenedetti et al. | 2024 | Agentic injection benchmark | 629 security test cases | High |
| 10 | JailbreakBench | Chao et al. | 2024 | Standardized jailbreak benchmark | 100 harmful behaviors | Medium |