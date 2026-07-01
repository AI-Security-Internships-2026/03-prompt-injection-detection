# Weekly Progress Log: Prompt Injection Detection and Defence for LLM-Based Applications

**Student:** Ehsan Ullah Jamshaid
**GitHub username:** ejamshaidbese24seecs-glitch

---

## How to Use This File

Add a new section every Friday before opening your weekly Pull Request.
Be honest — problems and blockers are normal and help your supervisor support you.

---

## Week 1

**Branch:** `ehsanullah-week-01`
**PR link:** https://github.com/AI-Security-Internships-2026/03-prompt-injection-detection/pull/1

### Completed this week
- [x] Read README and proposal
- [x] Set up local environment (Python venv, dependencies)
- [x] Ran `src/main.py` successfully
- [x] Wrote personal introduction (below)
- [x] Identified 5 related papers / tools / datasets

### Personal Introduction
My name is Ehsan Ullah Jamshaid and I am a Software Engineering student at NUST interested in AI and cybersecurity.
I have experience with Python and machine learning concepts.
I joined this internship to gain hands-on experience in AI security, specifically around
prompt injection attacks and how to defend against them.
I hope to build practical skills in LLM security and contribute meaningful research to the team.

### Problems / Blockers
- Windows blocked the virtual environment activation script due to execution policy restrictions.
- Solved it by running `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` in PowerShell.

### Next week plan
- Read the 5 papers identified this week
- Complete `docs/proposal.md` draft
- Set up dataset download / preprocessing pipeline

---

## Week 2

**Branch:** `ehsanullah-week-02`
**PR link:** https://github.com/AI-Security-Internships-2026/03-prompt-injection-detection/pull/2

### Completed this week
- [x] Read Paper 1, 2, and 3 in full depth
- [x] Added detailed notes for HackAPrompt dataset and Garak tool
- [x] Built src/explore_hackaprompt.py — loaded and analyzed full HackAPrompt dataset (601,757 rows)
- [x] Installed and ran Garak v0.15.1 with promptinject probes
- [x] Built src/read_garak_report.py — extracted 446 unique real attack prompts from Garak report

### Key findings
- HackAPrompt real-world attack success rate: 12.95%
- Confirmed Context Ignoring attack pattern is most common real-world strategy
- Tested against Garak dummy model — real LLM testing moved to Week 3

### Problems / Blockers
- HackAPrompt dataset is gated on HuggingFace — required authenticating via `hf auth login`
- Garak newer CLI syntax changed from older documentation

### Next week plan
- Run Garak against a real LLM
- Build automated test harness to log results systematically
- Write docs/proposal.md architecture document

---

## Week 3

**Branch:** `ehsanullah-week-03`
**PR link:** _[Add link after opening PR]_

### Completed this week
- [x] Ran Garak against real GPT-2 model via HuggingFace
- [x] Built src/test_harness.py — automated test harness
- [x] Fixed results parsing — Garak v0.15.1 has no passed field, manually checked trigger words
- [x] Saved structured results to experiments/results/ as JSON files

### Key findings
- GPT-2 real vulnerability results:
  - HijackHateHumans: 18.75% attack success rate
  - HijackKillHumans: 28.36% attack success rate (most vulnerable)
  - HijackLongPrompt: 11.48% attack success rate (most resistant)
- Average 19.5% of attacks successfully hijacked GPT-2
- Results match Garak terminal output exactly

### Problems / Blockers
- Garak v0.15.1 report format changed — no passed field exists
- Fixed by checking if model output contained the trigger word directly
- Garak failed when called as subprocess — solved by using existing report file

### Next week plan
- Write docs/proposal.md detection architecture document
- Build ML-based detector using HackAPrompt dataset
- Test detector against Garak-generated attack prompts