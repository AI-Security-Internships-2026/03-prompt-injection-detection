"""
Prompt Injection Detection and Defence for LLM-Based Applications
CNIT/PNTLab Pisa — AI Security Internship 2026

Week 2: Garak Report Reader

This script reads a Garak .report.jsonl file and extracts the
actual attack prompts that were generated, so we can:
1. See real examples of prompt injection attacks
2. Use them as additional test cases for our own detector
   (src/detector.py)

Garak report format reference:
https://github.com/NVIDIA/garak
"""

import json
import glob
import os


def find_latest_report(reports_dir: str) -> str | None:
    """
    Finds the most recently created Garak report file in the
    given directory.

    Args:
        reports_dir: Path to garak's report output directory.

    Returns:
        Path to the most recent .report.jsonl file, or None if
        no reports are found.
    """
    pattern = os.path.join(reports_dir, "*.report.jsonl")
    report_files = glob.glob(pattern)

    if not report_files:
        return None

    # Pick the most recently modified file
    latest = max(report_files, key=os.path.getmtime)
    return latest


def load_report_entries(report_path: str) -> list[dict]:
    """
    Loads all JSON entries from a Garak .jsonl report file.

    Each line in a .jsonl file is its own independent JSON object.

    Args:
        report_path: Path to the report file.

    Returns:
        A list of dictionaries, one per line in the report.
    """
    entries = []
    with open(report_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                # Some lines may be metadata/config, not attempts; skip those
                continue
    return entries


def extract_attack_prompts(entries: list[dict]) -> list[str]:
    """
    Extracts the actual attack prompt text from report entries.

    Garak attempt entries typically have an 'entry_type' of 'attempt'
    and a 'prompt' field containing the text sent to the target model.

    Args:
        entries: List of parsed JSON report entries.

    Returns:
        A list of unique attack prompt strings.
    """
    prompts = []
    for entry in entries:
        if entry.get("entry_type") == "attempt":
            prompt = entry.get("prompt")
            if isinstance(prompt, dict):
                # Newer garak versions store prompt as a dict with 'turns'
                # Try to extract text from the first turn
                turns = prompt.get("turns", [])
                if turns:
                    content = turns[0].get("content", {})
                    text = content.get("text") if isinstance(content, dict) else None
                    if text:
                        prompts.append(text)
            elif isinstance(prompt, str):
                prompts.append(prompt)

    # Remove duplicates while preserving order
    seen = set()
    unique_prompts = []
    for p in prompts:
        if p not in seen:
            seen.add(p)
            unique_prompts.append(p)

    return unique_prompts


def main() -> None:
    reports_dir = os.path.expanduser(
        r"~\.local\share\garak\garak_runs"
    )

    report_path = find_latest_report(reports_dir)
    if not report_path:
        print(f"No Garak reports found in {reports_dir}")
        print("Run a Garak scan first, e.g.:")
        print("  python -m garak --target_type test --probes promptinject")
        return

    print(f"Reading report: {report_path}\n")
    entries = load_report_entries(report_path)
    print(f"Loaded {len(entries)} total entries from the report.\n")

    prompts = extract_attack_prompts(entries)
    print(f"Found {len(prompts)} unique attack prompts.\n")

    print("=" * 60)
    print("SAMPLE GARAK-GENERATED ATTACK PROMPTS")
    print("=" * 60)
    for i, prompt in enumerate(prompts[:5], start=1):
        print(f"\n--- Example {i} ---")
        print(prompt[:300])

    # Save all extracted prompts to a file for later use in testing
    # our own detector against them.
    output_path = "garak_attack_prompts.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        for prompt in prompts:
            f.write(prompt.replace("\n", " ") + "\n")
    print(f"\nAll {len(prompts)} prompts saved to {output_path}")


if __name__ == "__main__":
    main()