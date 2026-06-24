"""
HackAPrompt Dataset Loader - Week 2 Task
ONT Lab, SEECS NUST

Loading the HackAPrompt dataset from HuggingFace and doing some basic
exploration to understand what real prompt injection attempts look like.
This is to get a feel for the data before we start building the detector.

Dataset: https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset
"""

from datasets import load_dataset
import pandas as pd


def load_hackaprompt():
   
    dataset = load_dataset("hackaprompt/hackaprompt-dataset")

    # dataset comes with a 'train' split
    df = dataset["train"].to_pandas()
    print(f"Done. Loaded {len(df)} rows.\n")
    return df


def show_basic_info(df):
    print("=" * 60)
    print("Dataset Overview")
    print("=" * 60)
    print(f"Rows    : {len(df)}")
    print(f"Columns : {list(df.columns)}")
    print()


def show_success_rate(df):
    """
    Checking how many attacks actually succeeded vs failed.
    HackAPrompt has some kind of success/correct column - need to find it.
    """
    print("=" * 60)
    print("Attack Success Rate")
    print("=" * 60)

    # searching for a column that looks like it tracks success
    success_cols = [
        col for col in df.columns
        if "success" in col.lower() or "correct" in col.lower()
    ]

    if success_cols:
        col = success_cols[0]
        successes = df[col].sum()
        total = len(df)
        print(f"Column used : '{col}'")
        print(f"Successful  : {successes}")
        print(f"Total       : {total}")
        print(f"Rate        : {successes / total:.2%}")
    else:
        # no obvious column, just printing what we have
        print("Couldn't find a clear success/fail column.")
        print("Available columns:", list(df.columns))

    print()


def show_sample_attacks(df, n=5):
    """prints a few attack prompts so we can see what they look like"""
    print("=" * 60)
    print(f"Sample Attack Prompts (top {n})")
    print("=" * 60)

    # looking for a column with the actual prompt text
    prompt_cols = [
        col for col in df.columns
        if "prompt" in col.lower() or "user_input" in col.lower()
    ]

    if prompt_cols:
        col = prompt_cols[0]
        sample = df[col].dropna().sample(min(n, len(df)), random_state=42)
        for idx, text in enumerate(sample, start=1):
            print(f"\n--- Sample {idx} ---")
            print(text[:300])  # cutting off really long ones
    else:
        print("No prompt column found. Columns are:")
        print(list(df.columns))

    print()


def save_summary(df, out_path="hackaprompt_summary.txt"):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("HackAPrompt Dataset - Quick Summary\n")
        f.write("=" * 40 + "\n")
        f.write(f"Total rows : {len(df)}\n")
        f.write(f"Columns    : {list(df.columns)}\n")

    print(f"Summary written to '{out_path}'\n")


def main():
    df = load_hackaprompt()
    show_basic_info(df)
    show_success_rate(df)
    show_sample_attacks(df, n=5)
    save_summary(df)


if __name__ == "__main__":
    main()



# ---------------------------------------------------------------
# HACKAPROMPT DATASET EXPLORER - Week 2 Summary
#
# Dataset: hackaprompt/hackaprompt-dataset (HuggingFace)
# Source:  https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset
#
# What this script does:
#   1. load_hackaprompt()     - downloads the dataset from HuggingFace
#                               and loads the 'train' split into a DataFrame
#   2. show_basic_info()      - prints total row count and column names
#                               to understand the dataset structure
#   3. show_success_rate()    - searches for any column containing 'success'
#                               or 'correct' and calculates the attack
#                               success rate across all attempts
#   4. show_sample_attacks()  - finds the prompt/user_input column and
#                               prints 5 random examples (300 chars each)
#   5. save_summary()         - writes row count and column names to
#                               hackaprompt_summary.txt for later reference
#
# Results:
#   - 601,757 real-world attack attempts loaded
#   - Attack success rate: 12.95%
#   - Common attacker objective: manipulate the model into
#     outputting the string "I have been PWNED"
# ---------------------------------------------------------------