"""
Prompt Injection Detection and Defence for LLM-Based Applications
CNIT/PNTLab Pisa — AI Security Internship 2026

Week 2: HackAPrompt Dataset Explorer

This script loads the HackAPrompt dataset from HuggingFace and
performs basic exploratory analysis to understand the structure
and characteristics of real-world prompt injection attacks.

Dataset source: https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset
"""

from datasets import load_dataset
import pandas as pd


def load_hackaprompt_dataset():
    """
    Loads the HackAPrompt dataset from HuggingFace.

    Returns:
        A pandas DataFrame containing the dataset.
    """
    print("Loading HackAPrompt dataset from HuggingFace...")
    dataset = load_dataset("hackaprompt/hackaprompt-dataset")

    # The dataset usually has a 'train' split by default
    df = dataset["train"].to_pandas()
    print(f"Dataset loaded successfully with {len(df)} rows.\n")
    return df


def show_basic_info(df: pd.DataFrame) -> None:
    """
    Prints basic information about the dataset structure.
    """
    print("=" * 60)
    print("BASIC DATASET INFORMATION")
    print("=" * 60)
    print(f"Total rows         : {len(df)}")
    print(f"Columns            : {list(df.columns)}")
    print()


def show_success_rate(df: pd.DataFrame) -> None:
    """
    Calculates and prints how many prompt injection attempts
    succeeded vs failed, if a relevant column exists.
    """
    print("=" * 60)
    print("ATTACK SUCCESS RATE")
    print("=" * 60)

    # HackAPrompt dataset typically has a 'completion' and
    # success-related column; we check for common column names.
    possible_success_cols = [
        col for col in df.columns
        if "success" in col.lower() or "correct" in col.lower()
    ]

    if possible_success_cols:
        col = possible_success_cols[0]
        success_count = df[col].sum()
        total = len(df)
        print(f"Using column: '{col}'")
        print(f"Successful attacks : {success_count}")
        print(f"Total attempts      : {total}")
        print(f"Success rate        : {success_count / total:.2%}")
    else:
        print("No explicit success/correct column found.")
        print("Columns available for manual inspection:")
        print(list(df.columns))
    print()


def show_sample_attacks(df: pd.DataFrame, n: int = 5) -> None:
    """
    Prints a sample of attack prompts from the dataset so we can
    visually inspect what real prompt injection attempts look like.
    """
    print("=" * 60)
    print(f"SAMPLE ATTACK PROMPTS (showing {n})")
    print("=" * 60)

    # Try to find a column that likely contains the attacker's prompt
    possible_prompt_cols = [
        col for col in df.columns
        if "prompt" in col.lower() or "user_input" in col.lower()
    ]

    if possible_prompt_cols:
        col = possible_prompt_cols[0]
        sample = df[col].dropna().sample(min(n, len(df)), random_state=42)
        for i, text in enumerate(sample, start=1):
            print(f"\n--- Example {i} ---")
            print(text[:300])  # limit to 300 characters for readability
    else:
        print("No obvious prompt column found. Columns are:")
        print(list(df.columns))
    print()


def save_summary(df: pd.DataFrame, output_path: str = "hackaprompt_summary.txt") -> None:
    """
    Saves a basic text summary of the dataset to a file.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("HackAPrompt Dataset Summary\n")
        f.write("=" * 40 + "\n")
        f.write(f"Total rows: {len(df)}\n")
        f.write(f"Columns: {list(df.columns)}\n")
    print(f"Summary saved to {output_path}\n")


def main() -> None:
    df = load_hackaprompt_dataset()
    show_basic_info(df)
    show_success_rate(df)
    show_sample_attacks(df, n=5)
    save_summary(df)


if __name__ == "__main__":
    main()