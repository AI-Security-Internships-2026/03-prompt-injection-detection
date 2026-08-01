"""
Prompt Injection Detection and Defence for LLM-Based Applications
CNIT/PNTLab Pisa — AI Security Internship 2026

Week 3: Enhanced Interactive Prompt Injection Tester

Features:
- Type any prompt and test it against LLaMA 3.1 via Groq
- Keyword detector runs BEFORE sending to LLM
- Full model response shown in terminal
- All prompts and responses saved to a log file
- Session summary shown at end
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

# Shared, dependency-free detector (audit M1). Keeps this module import-safe
# without the Groq SDK and avoids a second divergent pattern list.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detection_utils import SUSPICIOUS_PATTERNS, detect_injection  # noqa: E402,F401

# ── Output file ────────────────────────────────────────────
LOG_FILE = "experiments/results/interactive_session_log.json"


# ══════════════════════════════════════════════════════════
# DETECTOR
# ══════════════════════════════════════════════════════════
# detect_injection() is imported from detection_utils (single source of truth,
# normalization- and decode-aware).


# ══════════════════════════════════════════════════════════
# LLM QUERY
# ══════════════════════════════════════════════════════════


def query_llm(client, prompt: str) -> str:
    """
    Sends prompt to LLaMA 3.1 8B via Groq and returns full response.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: {str(e)}"


# ══════════════════════════════════════════════════════════
# ATTACK CHECK
# ══════════════════════════════════════════════════════════


def check_hijacked(response: str, trigger: str) -> bool:
    """
    Checks if model response contains the trigger word.
    True = attack succeeded (model was hijacked)
    """
    if not trigger:
        return False
    return trigger.lower() in response.lower()


# ══════════════════════════════════════════════════════════
# DISPLAY
# ══════════════════════════════════════════════════════════


def print_separator() -> None:
    print("\n" + "═" * 60)


def print_detector_result(is_suspicious: bool, matched: list[str]) -> None:
    print("\n┌─────────────────────────────────────┐")
    print("│           DETECTOR RESULT           │")
    print("└─────────────────────────────────────┘")
    if is_suspicious:
        print("⚠️  STATUS   : SUSPICIOUS")
        print(f"🔍 MATCHED  : {matched}")
        print("🚫 ACTION   : Would block before reaching LLM")
    else:
        print("✅ STATUS   : SAFE")
        print("🔍 MATCHED  : None")
        print("✅ ACTION   : Would allow through to LLM")


def print_llm_response(response: str) -> None:
    print("\n┌─────────────────────────────────────┐")
    print("│         LLaMA 3.1 RESPONSE          │")
    print("└─────────────────────────────────────┘")
    print(response)


def print_attack_result(hijacked: bool, trigger: str) -> None:
    print("\n┌─────────────────────────────────────┐")
    print("│           ATTACK RESULT             │")
    print("└─────────────────────────────────────┘")
    if hijacked:
        print("🔴 ATTACK SUCCEEDED")
        print(f"   Model said the trigger word: '{trigger}'")
        print("   The LLM was successfully hijacked!")
    else:
        print("🟢 ATTACK FAILED")
        print(f"   Model did NOT say: '{trigger}'")
        print("   The LLM successfully resisted!")


def print_session_summary(session_log: list[dict]) -> None:
    total = len(session_log)
    suspicious = sum(1 for r in session_log if r["detected"])
    succeeded = sum(1 for r in session_log if r["attack_succeeded"])
    missed = sum(1 for r in session_log if r["attack_succeeded"] and not r["detected"])

    print("\n" + "═" * 60)
    print("SESSION SUMMARY")
    print("═" * 60)
    print(f"Total prompts tested    : {total}")
    print(f"Flagged by detector     : {suspicious}")
    print(f"Attacks succeeded       : {succeeded}")
    print(f"Attacks missed          : {missed}")
    if total > 0:
        print(f"Detection rate          : {suspicious / total * 100:.1f}%")
    print("═" * 60)


# ══════════════════════════════════════════════════════════
# SAVE LOG
# ══════════════════════════════════════════════════════════


def save_log(session_log: list[dict]) -> None:
    """
    Saves full session log to JSON file.
    Includes every prompt, response, detection result, and attack result.
    """
    os.makedirs("experiments/results", exist_ok=True)

    output = {
        "session_start": session_log[0]["timestamp"] if session_log else "",
        "session_end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "llama-3.1-8b-instant",
        "provider": "Groq API",
        "total_prompts": len(session_log),
        "prompts": session_log,
    }

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n💾 Session saved to: {LOG_FILE}")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════


def main() -> None:
    # Check credentials before importing the optional SDK.
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set. Export it before running the interactive tester."
        )

    from groq import Groq  # imported lazily so this module stays import-safe

    client = Groq()
    session_log: list[dict] = []

    print("═" * 60)
    print("  INTERACTIVE PROMPT INJECTION TESTER")
    print("  Model : LLaMA 3.1 8B via Groq API")
    print("  Log   : experiments/results/interactive_session_log.json")
    print("═" * 60)
    print("Commands:")
    print("  Type any prompt and press Enter to test it")
    print("  Type 'summary' to see session stats")
    print("  Type 'quit' to exit and save log\n")

    while True:
        print_separator()

        # Get prompt
        prompt = input("\n📝 YOUR PROMPT:\n> ").strip()

        if not prompt:
            continue

        if prompt.lower() == "quit":
            print_session_summary(session_log)
            if session_log:
                save_log(session_log)
            print("\nGoodbye!")
            break

        if prompt.lower() == "summary":
            print_session_summary(session_log)
            continue

        # Get trigger word
        trigger = input("\n🎯 Trigger word to watch for (Enter to skip): ").strip()

        # Step 1 — Keyword detection
        is_suspicious, matched = detect_injection(prompt)
        print_detector_result(is_suspicious, matched)

        # Step 2 — Send to LLM
        print("\n⏳ Sending to LLaMA 3.1...")
        response = query_llm(client, prompt)
        print_llm_response(response)

        # Step 3 — Check attack result
        hijacked = check_hijacked(response, trigger)
        if trigger:
            print_attack_result(hijacked, trigger)

        # Step 4 — Save to log
        session_log.append(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "prompt": prompt,
                "trigger": trigger,
                "detected": is_suspicious,
                "matched_patterns": matched,
                "response": response,
                "attack_succeeded": hijacked,
            }
        )

        print(f"\n📊 Session total: {len(session_log)} prompts tested")


if __name__ == "__main__":
    main()
