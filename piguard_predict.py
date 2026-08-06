"""
Runs the real PIGuard model (leolee99/PIGuard on Hugging Face) on an
evaluation CSV and saves predictions in the same format ml_detector.py's
`evaluate` command produces, so they can be fed straight into:

    python src/ml_detector.py mcnemar --pred-a <this output> --pred-b <your ml_detector predictions>

Usage:
    pip install transformers torch
    python piguard_predict.py --dataset datasets/eval_dataset_v2.csv --output experiments/results/piguard_eval_dataset_v2.csv
    python piguard_predict.py --dataset datasets/deepset_eval.csv --output experiments/results/piguard_deepset.csv
"""

import argparse
from pathlib import Path

import pandas as pd
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline


def build_classifier():
    print("Loading PIGuard (leolee99/PIGuard) from Hugging Face...")
    tokenizer = AutoTokenizer.from_pretrained("leolee99/PIGuard")
    model = AutoModelForSequenceClassification.from_pretrained(
        "leolee99/PIGuard", trust_remote_code=True
    )
    print(f"Model label mapping: {model.config.id2label}")

    classifier = pipeline(
        "text-classification",
        model=model,
        tokenizer=tokenizer,
        truncation=True,
        top_k=None,  # return scores for all labels so we can pick the injection one robustly
    )
    return classifier, model.config.id2label


def label_indicates_injection(label_name):
    """
    PIGuard's label names vary by checkpoint (e.g. 'INJECTION'/'BENIGN',
    'LABEL_1'/'LABEL_0', 'malicious'/'benign'). This keyword-matches the
    label string rather than assuming a fixed name.
    """
    name = str(label_name).lower()
    injection_keywords = ["inject", "malicious", "attack", "unsafe", "label_1", "1"]
    benign_keywords = ["benign", "safe", "label_0", "0"]

    if any(k in name for k in injection_keywords) and not any(k in name for k in benign_keywords):
        return True
    if any(k in name for k in benign_keywords):
        return False
    # Fall back: if truly ambiguous, treat as injection only if it's exactly "1"
    return name.strip() == "1"


def predict_batch(classifier, texts, batch_size=16):
    predictions = []
    probabilities = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        outputs = classifier(batch)  # list of list-of-dicts (all label scores) due to top_k=None

        for scores in outputs:
            # scores: [{"label": ..., "score": ...}, ...]
            injection_score = 0.0
            for entry in scores:
                if label_indicates_injection(entry["label"]):
                    injection_score += entry["score"]
            predictions.append(int(injection_score >= 0.5))
            probabilities.append(float(injection_score))

        done = min(start + batch_size, len(texts))
        print(f"  {done}/{len(texts)} predicted", end="\r")

    print()
    return predictions, probabilities


def main():
    parser = argparse.ArgumentParser(description="Run PIGuard on an eval CSV")
    parser.add_argument("--dataset", required=True, help="Path to eval CSV (needs text, label columns)")
    parser.add_argument("--output", required=True, help="Where to save the prediction CSV")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(dataset_path)
    missing = {"text", "label"} - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    df = df.dropna(subset=["text", "label"]).reset_index(drop=True)
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

    classifier, id2label = build_classifier()

    print(f"\nRunning PIGuard on {len(df)} rows from {dataset_path}...")
    predictions, probabilities = predict_batch(classifier, df["text"].tolist(), batch_size=args.batch_size)

    df["predicted_label"] = predictions
    df["attack_probability"] = probabilities
    df["correct"] = df["label"] == df["predicted_label"]

    df.to_csv(output_path, index=False)

    accuracy = (df["label"] == df["predicted_label"]).mean()
    print(f"\nPIGuard accuracy on {dataset_path.name}: {accuracy * 100:.2f}%")
    print(f"Saved predictions to:\n{output_path}")


if __name__ == "__main__":
    main()