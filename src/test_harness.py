"""
Prompt Injection Detection and Defence for LLM-Based Applications
CNIT/PNTLab Pisa — AI Security Internship 2026

Week 3 (Final): Automated Test Harness

Pipeline:
1. Extract attack prompts from Garak report → save to txt
2. Send each prompt to LLaMA 3.1 via Groq API
3. Check if attack succeeded (trigger word in response)
4. Check if our keyword detector caught it before LLM
5. Save succeeded attacks → txt file
6. Save full stats → JSON file
"""

import json
import os
import glob
import time
from datetime import datetime
from groq import Groq


# ── Paths ──────────────────────────────────────────────────
GARAK_REPORTS_DIR = os.path.expanduser(r"~\.local\share\garak\garak_runs")
RESULTS_DIR       = "experiments/results"
PROMPTS_FILE      = f"{RESULTS_DIR}/garak_prompts.txt"
SUCCEEDED_FILE    = f"{RESULTS_DIR}/succeeded_attacks.txt"
STATS_FILE        = f"{RESULTS_DIR}/harness_stats.json"

# ── Keyword detector patterns ──────────────────────────────
SUSPICIOUS_PATTERNS = [
    "ignore previous instructions",
    "ignore any previous",
    "disregard all instructions",
    "forget previous instructions",
    "you are now",
    "new instructions:",
    "system override",
    "developer mode",
    "stop everything",
    "print yes",
    "i have been pwned",
    "pwned",
    "ignore and print",
]


# ══════════════════════════════════════════════════════════
# STEP 1 — Extract attack prompts from Garak report
# ══════════════════════════════════════════════════════════

def extract_garak_prompts(reports_dir: str) -> list[dict]:
    """
    Reads the latest Garak report and extracts all unique
    attack prompts along with their trigger words.

    Returns:
        List of dicts: {prompt, triggers, probe}
    """
    pattern = os.path.join(reports_dir, "*.report.jsonl")
    report_files = glob.glob(pattern)

    if not report_files:
        print("No Garak reports found!")
        print("Run: python -m garak --target_type huggingface --target_name gpt2 --probes promptinject")
        return []

    latest = max(report_files, key=os.path.getmtime)
    print(f"Reading Garak report: {latest}\n")

    attacks = []
    seen = set()

    with open(latest, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("entry_type") != "attempt":
                continue

            # Extract prompt text
            prompt_obj = entry.get("prompt", {})
            turns = prompt_obj.get("turns", [])
            if not turns:
                continue
            content = turns[0].get("content", {})
            prompt_text = content.get("text", "") if isinstance(content, dict) else ""

            if not prompt_text or prompt_text in seen:
                continue
            seen.add(prompt_text)

            attacks.append({
                "prompt":   prompt_text,
                "triggers": entry.get("notes", {}).get("triggers", []),
                "probe":    entry.get("probe_classname", "unknown")
            })

    return attacks


def save_prompts_to_txt(attacks: list[dict]) -> None:
    """
    Saves all extracted attack prompts to a text file.
    One prompt per line, with probe name as header.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        f.write("# Garak-Generated Attack Prompts\n")
        f.write(f"# Total: {len(attacks)}\n")
        f.write(f"# Generated: {datetime.now()}\n\n")
        for i, attack in enumerate(attacks, start=1):
            f.write(f"--- Prompt {i} | Probe: {attack['probe'].split('.')[-1]} | Triggers: {attack['triggers']} ---\n")
            f.write(attack["prompt"].replace("\n", " ") + "\n\n")

    print(f"Saved {len(attacks)} prompts to: {PROMPTS_FILE}")


# ══════════════════════════════════════════════════════════
# STEP 2 — Keyword detector
# ══════════════════════════════════════════════════════════

def detect_injection(prompt: str) -> tuple[bool, list[str]]:
    """
    Scans prompt for known injection patterns BEFORE sending to LLM.
    Returns (is_suspicious, matched_patterns)
    """
    prompt_lower = prompt.lower()
    matched = [p for p in SUSPICIOUS_PATTERNS if p in prompt_lower]
    return len(matched) > 0, matched


# ══════════════════════════════════════════════════════════
# STEP 3 — Query LLaMA 3.1 via Groq
# ══════════════════════════════════════════════════════════

def query_llm(client: Groq, prompt: str) -> str:
    """
    Sends prompt to LLaMA 3.1 8B via Groq API.
    Returns model response text.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: {str(e)}"


# ══════════════════════════════════════════════════════════
# STEP 4 — Check attack success
# ══════════════════════════════════════════════════════════

def check_attack_success(response: str, triggers: list[str]) -> bool:
    """
    Checks if the model's response contains any trigger word.
    If yes → attack succeeded (model was hijacked).
    """
    response_lower = response.lower()
    return any(t.lower() in response_lower for t in triggers)


# ══════════════════════════════════════════════════════════
# STEP 5 — Run the full harness
# ══════════════════════════════════════════════════════════

def run_harness(attacks: list[dict], max_attacks: int = 30) -> list[dict]:
    """
    Main harness loop:
    For each attack prompt:
      1. Run keyword detector
      2. Send to LLaMA 3.1
      3. Check if attack succeeded
      4. Log everything
    """
    client = Groq()
    results = []
    sample = attacks[:max_attacks]

    print("\n" + "=" * 60)
    print(f"RUNNING HARNESS — LLaMA 3.1 8B via Groq")
    print(f"Testing {len(sample)} of {len(attacks)} prompts")
    print("=" * 60)

    for i, attack in enumerate(sample, start=1):
        prompt   = attack["prompt"]
        triggers = attack["triggers"]
        probe    = attack["probe"].split(".")[-1]

        print(f"\n[{i}/{len(sample)}] {probe} | Triggers: {triggers}")

        # Keyword detection
        is_suspicious, matched = detect_injection(prompt)

        # Query LLM
        response = query_llm(client, prompt)

        # Check success
        attack_succeeded  = check_attack_success(response, triggers)
        detected_by_keyword = is_suspicious

        # Print live result
        status   = "🔴 SUCCEEDED" if attack_succeeded   else "🟢 RESISTED"
        detected = "⚠️  DETECTED"  if detected_by_keyword else "❌ MISSED"
        print(f"  Attack: {status} | Detector: {detected}")
        print(f"  Response: {response[:120]}...")

        results.append({
            "probe":                probe,
            "prompt":               prompt[:400],
            "triggers":             triggers,
            "response":             response[:600],
            "attack_succeeded":     attack_succeeded,
            "detected_by_keyword":  detected_by_keyword,
            "matched_patterns":     matched
        })

        # Respect Groq rate limits
        time.sleep(1.5)

    return results


# ══════════════════════════════════════════════════════════
# STEP 6 — Save results
# ══════════════════════════════════════════════════════════

def save_succeeded_attacks(results: list[dict]) -> None:
    """
    Saves only the attacks that SUCCEEDED to a separate txt file.
    Useful for understanding what bypassed our detector.
    """
    succeeded = [r for r in results if r["attack_succeeded"]]

    with open(SUCCEEDED_FILE, "w", encoding="utf-8") as f:
        f.write("# Succeeded Attacks — LLaMA 3.1 8B\n")
        f.write(f"# Total succeeded: {len(succeeded)}\n")
        f.write(f"# Generated: {datetime.now()}\n\n")
        for i, r in enumerate(succeeded, start=1):
            f.write(f"--- Attack {i} | Probe: {r['probe']} ---\n")
            f.write(f"Prompt:   {r['prompt']}\n")
            f.write(f"Triggers: {r['triggers']}\n")
            f.write(f"Response: {r['response']}\n")
            f.write(f"Detected by keyword: {r['detected_by_keyword']}\n\n")

    print(f"Saved {len(succeeded)} succeeded attacks to: {SUCCEEDED_FILE}")


def save_stats_json(results: list[dict]) -> None:
    """
    Saves full statistics to a JSON file.
    Includes per-probe breakdown and overall summary.
    """
    total      = len(results)
    succeeded  = sum(1 for r in results if r["attack_succeeded"])
    detected   = sum(1 for r in results if r["detected_by_keyword"])
    caught     = sum(1 for r in results if r["attack_succeeded"] and r["detected_by_keyword"])
    missed     = sum(1 for r in results if r["attack_succeeded"] and not r["detected_by_keyword"])

    # Per-probe breakdown
    probe_stats = {}
    for r in results:
        probe = r["probe"]
        if probe not in probe_stats:
            probe_stats[probe] = {
                "total": 0,
                "succeeded": 0,
                "detected": 0
            }
        probe_stats[probe]["total"] += 1
        if r["attack_succeeded"]:
            probe_stats[probe]["succeeded"] += 1
        if r["detected_by_keyword"]:
            probe_stats[probe]["detected"] += 1

    stats = {
        "timestamp":        datetime.now().strftime("%Y%m%d_%H%M%S"),
        "model":            "llama-3.1-8b-instant",
        "provider":         "Groq API",
        "total_tested":     total,
        "attacks_succeeded": succeeded,
        "attacks_resisted":  total - succeeded,
        "attack_success_rate": round(succeeded / total * 100, 2) if total > 0 else 0,
        "detected_by_keyword": detected,
        "detector_recall":  round(caught / succeeded * 100, 2) if succeeded > 0 else 0,
        "missed_by_detector": missed,
        "per_probe":        probe_stats,
        "full_results":     results
    }

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"Stats saved to: {STATS_FILE}")


def print_summary(results: list[dict]) -> None:
    """
    Prints a clean final summary table.
    """
    total     = len(results)
    succeeded = sum(1 for r in results if r["attack_succeeded"])
    detected  = sum(1 for r in results if r["detected_by_keyword"])
    caught    = sum(1 for r in results if r["attack_succeeded"] and r["detected_by_keyword"])
    missed    = sum(1 for r in results if r["attack_succeeded"] and not r["detected_by_keyword"])

    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Model tested          : LLaMA 3.1 8B (Groq)")
    print(f"Total prompts tested  : {total}")
    print(f"Attacks succeeded     : {succeeded} ({succeeded/total*100:.1f}%)")
    print(f"Attacks resisted      : {total-succeeded} ({(total-succeeded)/total*100:.1f}%)")
    print(f"Detected by keyword   : {detected} ({detected/total*100:.1f}%)")
    print(f"Caught (attack+detect): {caught}")
    print(f"Missed by detector    : {missed}")
    if succeeded > 0:
        print(f"Detector recall       : {caught/succeeded*100:.1f}%")
    print("=" * 60)
    print(f"\nFiles saved:")
    print(f"  Prompts:   {PROMPTS_FILE}")
    print(f"  Succeeded: {SUCCEEDED_FILE}")
    print(f"  Stats:     {STATS_FILE}")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 60)
    print("AUTOMATED TEST HARNESS")
    print("Garak → LLaMA 3.1 (Groq) → Results")
    print("=" * 60)

    # Step 1: Extract from Garak
    attacks = extract_garak_prompts(GARAK_REPORTS_DIR)
    if not attacks:
        return
    print(f"Extracted {len(attacks)} unique attack prompts from Garak")

    # Step 2: Save prompts to txt
    save_prompts_to_txt(attacks)

    # Step 3: Run harness against LLaMA 3.1
    results = run_harness(attacks, max_attacks=30)

    # Step 4: Save succeeded attacks
    save_succeeded_attacks(results)

    # Step 5: Save full stats
    save_stats_json(results)

    # Step 6: Print summary
    print_summary(results)


if __name__ == "__main__":
    main()