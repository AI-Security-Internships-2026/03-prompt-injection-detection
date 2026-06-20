# Weekly Progress Log: Prompt Injection Detection and Defence for LLM-Based Applications

**Student:**Ehsan Ullah Jamshaid
**GitHub username:** ejamshaidbese24seecs-glitch

---

## How to Use This File

Add a new section every Friday before opening your weekly Pull Request.
Be honest — problems and blockers are normal and help your supervisor support you.

---

## Week 1

**Branch:** `ehsanullah-week-01`
**PR link:** [_\[Add link after opening PR\]_](https://github.com/AI-Security-Internships-2026/03-prompt-injection-detection/pull/1)

### Completed this week


- [X] Read README and proposal
- [X] Set up local environment (Python venv, dependencies)
- [X] Ran `src/main.py` successfully
- [X] Wrote personal introduction (below)
- [X] Identified 5 related papers / tools / datasets

### Personal Introduction
My name is Ehsan Ullah and I am a Software Engineering student interested in AI and cybersecurity. 
I have basic experience with Python and machine learning concepts. 
I joined this internship to gain hands-on experience in AI security, specifically around 
prompt injection attacks and how to defend against them. 
I hope to build practical skills in LLM security and contribute meaningful research to the team.

### Problems / Blockers
_Describe any issues you faced. Did you solve them? How?_

### Next week plan
- Read the 5 papers identified this week
- Complete `docs/proposal.md` draft
- Set up dataset download / preprocessing pipeline

---


## Week 2

**Branch:** `ehsanullah-week-02`
**PR link:** _[Add link after opening PR]_

### Completed this week
- [x] Read Paper 1, 2, and 3 in full depth
- [x] Added detailed notes for HackAPrompt dataset and Garak tool
- [x] Built src/explore_hackaprompt.py — loaded and analyzed full HackAPrompt dataset (601,757 rows)
- [x] Installed and ran Garak v0.15.1 with promptinject probes
- [x] Built src/read_garak_report.py — extracted 446 unique real attack prompts

### Key findings
- HackAPrompt real-world attack success rate: 12.95% (77,936 out of 601,757 attempts)
- Garak generated 1,280 test attempts across 3 attack templates (HijackHateHumans, HijackKillHumans, HijackLongPrompt)
- Confirmed the "Context Ignoring" attack pattern (from Paper 1) is the most common real-world attack strategy, appearing consistently in both HackAPrompt and Garak-generated attacks
- Tested Garak against its dummy "test" model only; real LLM testing requires an API key



### Problems / Blockers
- HackAPrompt dataset is gated on HuggingFace — required creating an account, requesting access, and authenticating via `hf auth login`
- Garak's newer CLI syntax changed from older documentation (`--target_type` instead of `--model_type`)

### Next week plan
- Request access to an LLM API (OpenAI or HuggingFace Inference) to run Garak against a real model instead of the dummy test model
- Begin designing the detection system architecture for docs/proposal.md
- Read 2 more related papers to reach the 10-paper target by end of Week 

----
_(Add a new section each week)_
