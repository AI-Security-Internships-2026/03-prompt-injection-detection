"""
Downloads the deepset/prompt-injections dataset from Hugging Face and
saves it as datasets/deepset_eval.csv in the format ml_detector.py expects
(columns: text, label — 0 = benign, 1 = attack).

Usage:
    pip install datasets
    python download_deepset.py
"""

from pathlib import Path
from datasets import load_dataset, concatenate_datasets

OUTPUT_PATH = Path(__file__).resolve().parent / "datasets" / "deepset_eval.csv"
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

print("Downloading deepset/prompt-injections from Hugging Face...")
ds = load_dataset("deepset/prompt-injections")

splits = [ds[name] for name in ds.keys()]
full = concatenate_datasets(splits)

df = full.to_pandas()
print(f"Loaded {len(df)} rows. Columns: {list(df.columns)}")

if "text" not in df.columns or "label" not in df.columns:
    raise ValueError(
        f"Unexpected columns {list(df.columns)} — inspect the dataset and "
        "adjust the column names below before saving."
    )

df = df[["text", "label"]]
df.to_csv(OUTPUT_PATH, index=False)

print(f"\nSaved {len(df)} rows to:\n{OUTPUT_PATH}")
print("\nLabel distribution:")
print(df["label"].value_counts())