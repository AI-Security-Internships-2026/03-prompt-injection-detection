"""
Multilingual training augmentation for the RANA model (audit B3 fix).

Fixes the English-only training gap by machine-translating a BALANCED English
seed (benign + attack, from datasets/rana_train.csv) into the evaluation
languages. Translating BOTH classes is essential: translating only attacks would
teach the model "non-English == attack" and destroy multilingual benign
precision. Output is gitignored/regenerable; provenance is recorded.

Usage:
    python scripts/augment_multilingual.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from deep_translator import GoogleTranslator

REPO = Path(__file__).resolve().parent.parent
TRAIN_CSV = REPO / "datasets" / "rana_train.csv"
OUT_CSV = REPO / "datasets" / "rana_multilingual_aug.csv"
PROVENANCE = REPO / "datasets" / "rana_multilingual_aug.provenance.json"

# eval languages (deep-translator codes); en excluded (already covered).
LANGS = ["ar", "ur", "hi", "zh-CN", "es", "fr", "de", "pt", "ru"]
N_PER_CLASS = 55
SEED = 42
MIN_LEN, MAX_LEN = 20, 180


def _seed_frame() -> pd.DataFrame:
    df = pd.read_csv(TRAIN_CSV)
    df["text"] = df["text"].astype(str)
    df = df[(df["text"].str.len() >= MIN_LEN) & (df["text"].str.len() <= MAX_LEN)]
    parts = []
    for label in (0, 1):
        sub = df[df["label"] == label]
        parts.append(sub.sample(min(N_PER_CLASS, len(sub)), random_state=SEED))
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    seed = _seed_frame()
    print(
        f"Seed: {len(seed)} rows ({int((seed.label == 0).sum())} benign / "
        f"{int((seed.label == 1).sum())} attack) x {len(LANGS)} langs"
    )

    # Resume support: keep languages already translated in a prior (partial) run.
    rows = []
    done: set[str] = set()
    if OUT_CSV.exists():
        prev = pd.read_csv(OUT_CSV)
        rows = prev.to_dict("records")
        done = set(prev["language"].unique())
        print(f"Resuming: {len(rows)} rows already present for langs {sorted(done)}")

    for lang in LANGS:
        if lang in done:
            continue
        translator = GoogleTranslator(source="en", target=lang)
        ok = 0
        for _, r in seed.iterrows():
            try:
                out = translator.translate(r["text"])
            except Exception:  # noqa: BLE001 - skip individual translation failures
                out = None
            if out and isinstance(out, str) and out.strip():
                rows.append(
                    {
                        "text": out.strip(),
                        "label": int(r["label"]),
                        "language": lang,
                        "source": "translated_from_en",
                    }
                )
                ok += 1
        # Save incrementally so progress survives interruptions.
        pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8")
        print(f"  {lang}: {ok}/{len(seed)} translated (total {len(rows)})")

    df = pd.DataFrame(rows).drop_duplicates(subset=["text"]).reset_index(drop=True)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    sha = hashlib.sha256(OUT_CSV.read_bytes()).hexdigest()
    PROVENANCE.write_text(
        json.dumps(
            {
                "dataset name": "rana_multilingual_aug.csv",
                "creation method": "machine-translation (deep-translator/GoogleTranslator) of a "
                "balanced English seed from rana_train.csv into eval languages",
                "license": "derived from issdandavis/prompt-injection-bit-signatures (apache-2.0)",
                "languages": LANGS,
                "seed_per_class": N_PER_CLASS,
                "seed_random_state": SEED,
                "record count": int(len(df)),
                "class distribution": {
                    "benign(0)": int((df.label == 0).sum()),
                    "attack(1)": int((df.label == 1).sum()),
                },
                "sha256": sha,
                "known limitations": "machine-translated text; both classes translated to avoid a "
                "'non-English=attack' bias; small per-language counts.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(df)} rows -> {OUT_CSV}\nSHA-256: {sha}")


if __name__ == "__main__":
    main()
