"""
Reproducibly fetch training data for the RANA model (audit B2 fix).

Source: issdandavis/prompt-injection-bit-signatures (HuggingFace), license
apache-2.0, updated 2026-07 — a current aggregate of several public
prompt-injection datasets (SPML, jackhhao/jailbreak-classification,
neuralchemy, deepset). Columns include text, label (benign|malicious|jailbreak),
source, category. We map to binary: benign -> 0, {malicious, jailbreak} -> 1.

The dataset revision is pinned and the output CSV's SHA-256 recorded so the
training set is reproducible. Output CSV is gitignored; this script + the
provenance JSON are the committed, reproducible record.

Usage:
    python scripts/fetch_data.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from huggingface_hub import HfApi

from datasets import load_dataset

REPO = Path(__file__).resolve().parent.parent
OUT_CSV = REPO / "datasets" / "rana_train.csv"
PROVENANCE = REPO / "datasets" / "rana_train.provenance.json"
DATASET_ID = "issdandavis/prompt-injection-bit-signatures"
LICENSE = "apache-2.0"
# Splits used for training. The upstream 'test' split is deliberately left
# untouched; the project's real evaluation is datasets/eval_dataset_v2.csv.
TRAIN_SPLITS = ("train", "validation")


def _to_binary(label: object) -> int:
    return 0 if str(label).strip().lower() == "benign" else 1


def main() -> None:
    revision = HfApi().dataset_info(DATASET_ID).sha  # pin exact revision
    print(f"Fetching {DATASET_ID} @ {revision}")

    ds = load_dataset(DATASET_ID, revision=revision)
    frames = []
    for split in TRAIN_SPLITS:
        if split in ds:
            part = ds[split].to_pandas()
            part = part[["text", "label", "source"]].copy()
            frames.append(part)
    df = pd.concat(frames, ignore_index=True)

    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].map(_to_binary).astype(int)
    df["source"] = df["source"].astype(str)
    df = df[df["text"] != ""]
    before = len(df)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    sha = hashlib.sha256(OUT_CSV.read_bytes()).hexdigest()

    dist = df["label"].value_counts().sort_index().to_dict()
    src_dist = df["source"].value_counts().to_dict()
    provenance = {
        "dataset name": "rana_train.csv",
        "source": f"https://huggingface.co/datasets/{DATASET_ID}",
        "license": LICENSE,
        "creation method": (
            "downloaded public 2026 aggregate dataset (NOT the intern's original "
            "prompt_injection_500/benign_500); label mapped benign->0, "
            "malicious|jailbreak->1"
        ),
        "generator version": f"datasets load @ revision {revision}, splits={TRAIN_SPLITS}",
        "random seed": "n/a (deterministic download)",
        "record count": int(len(df)),
        "class distribution": {"benign(0)": int(dist.get(0, 0)), "attack(1)": int(dist.get(1, 0))},
        "source distribution": {k: int(v) for k, v in src_dist.items()},
        "language distribution": "predominantly en; multilingual recall stays a gap (B3)",
        "sha256": sha,
        "known limitations": (
            "Aggregate of public sources; metrics computed with it are for the RANA "
            "model only and are leakage-checked against eval_dataset_v2.csv before use."
        ),
        "revision": revision,
        "raw_rows_before_dedup": int(before),
    }
    PROVENANCE.write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    print(f"Wrote {len(df)} rows -> {OUT_CSV}")
    print(f"SHA-256: {sha}")
    print(f"Class distribution (0=benign,1=attack): {dist}")
    print(f"Provenance -> {PROVENANCE}")


if __name__ == "__main__":
    main()
