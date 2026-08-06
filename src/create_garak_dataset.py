import pandas as pd
from pathlib import Path
import re


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = Path(
    "experiments/results/garak_prompts.txt"
)

OUTPUT_FILE = Path(
    "datasets/garak_attacks.csv"
)


# ============================================================
# EXTRACT GARAK PROMPTS
# ============================================================

def extract_garak_prompts(file_path):

    """
    Extract attack prompts from Garak-generated prompt file.

    File format:

    --- Prompt 1 | Probe: HijackHateHumans | Triggers: [...] ---
    Actual attack prompt here

    --- Prompt 2 | Probe: ... ---
    Another attack prompt
    """

    with open(
        file_path,
        "r",
        encoding="utf-8",
        errors="replace"
    ) as f:

        content = f.read()


    # Split based on Prompt headers
    blocks = re.split(
        r"(?=--- Prompt \d+ \| Probe:)",
        content
    )


    prompts = []


    for block in blocks:

        # Skip header/comments
        if not block.startswith(
            "--- Prompt"
        ):
            continue


        # Find the end of the header
        header_match = re.match(
            r"--- Prompt \d+ \| Probe:.*?---\s*",
            block,
            re.DOTALL
        )


        if not header_match:
            continue


        # Everything after the header is the actual prompt
        prompt = block[
            header_match.end():
        ].strip()


        # Remove unnecessary whitespace
        prompt = re.sub(
            r"\s+",
            " ",
            prompt
        ).strip()


        # Ignore empty prompts
        if prompt:

            prompts.append(
                prompt
            )


    return prompts


# ============================================================
# CREATE DATASET
# ============================================================

def create_dataset(prompts):

    df = pd.DataFrame(
        {
            "text": prompts,
            "label": 1
        }
    )


    # Remove duplicate prompts
    df = df.drop_duplicates(
        subset=["text"]
    )


    # Remove empty rows
    df = df[
        df["text"].str.strip() != ""
    ]


    # Reset index
    df = df.reset_index(
        drop=True
    )


    return df


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)

    print(
        "CREATING GARAK ATTACK DATASET"
    )

    print("=" * 60)


    # Check input

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"File not found: {INPUT_FILE}"
        )


    # Extract prompts

    print(
        "\nReading Garak prompts..."
    )


    prompts = extract_garak_prompts(
        INPUT_FILE
    )


    print(
        f"Prompts extracted: {len(prompts)}"
    )


    # Create dataframe

    df = create_dataset(
        prompts
    )


    print(
        f"Unique attack prompts: {len(df)}"
    )


    # Create output directory

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    # Save CSV

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8"
    )


    print(
        f"\nSaved dataset to:"
    )

    print(
        OUTPUT_FILE
    )


    # Display statistics

    print(
        "\nDataset shape:"
    )

    print(
        df.shape
    )


    print(
        "\nFirst 5 examples:"
    )


    for i, row in df.head(5).iterrows():

        print(
            f"\n--- Attack {i + 1} ---"
        )

        print(
            row["text"][:500]
        )


if __name__ == "__main__":

    main()