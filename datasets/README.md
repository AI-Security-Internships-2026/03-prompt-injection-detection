# Datasets

## Policy

**Do NOT commit raw datasets to this repository.**
Large files slow down Git, may violate data licences, and create GDPR risks.

## How to document your dataset

For every dataset you use, create a file `datasets/<dataset-name>.md` with the following fields:

```markdown
## Dataset Name

- **Source URL:** https://...
- **Licence:** (e.g. CC BY 4.0, MIT, custom — always verify!)
- **Version / date downloaded:** YYYY-MM-DD
- **Size:** (approximate: rows, GB)
- **Format:** (CSV, PCAP, JSON, HDF5, …)
- **Download command / script:** (e.g. `wget https://...`)
- **Preprocessing steps:**
  1. Step one
  2. Step two
- **Train / Val / Test split:**
- **Notes:**
```

## Recommended storage options

| Option | When to use |
|---|---|
| Local disk only | Small experiments (< 500 MB) |
| University NAS / HPC scratch | Medium datasets shared within the lab |
| Hugging Face Datasets | Public NLP/ML datasets |
| Zenodo | Archived research datasets with DOI |
| DVC (Data Version Control) | Any dataset tracked alongside code |

## Example: CIC-IDS-2017

- **Source URL:** https://www.unb.ca/cic/datasets/ids-2017.html
- **Licence:** Research use — see website
- **Format:** PCAP + CSV
- **Preprocessing:** Extract flow features with CICFlowMeter

---

## Required provenance schema for training data (audit B2, Step 6.4)

**BLOCKED:** the model's training files `prompt_injection_500.csv` and
`benign_500.csv` are absent from the working tree **and from all git history**,
and no generator script exists in any commit. The ML model therefore cannot be
retrained or reproduced, and train/test leakage cannot be verified
(`src/ml_detector.py train` fails with a precise restoration message). A new
synthetic dataset must **not** be substituted and called equivalent to the
original.

When the original data (or its documented generation methodology) is restored,
record it here with **every** field below before use:

```markdown
## <dataset name>  (e.g. prompt_injection_500.csv)

- **Source:** URL or generator script path + commit
- **License:**
- **Creation method:** collected | templated-synthetic | LLM-generated | mixed
- **Generator version / commit:**
- **Random seed:**
- **Record count:**
- **Class distribution:** (benign vs attack)
- **Language distribution:**
- **SHA-256:**
- **Known limitations / leakage risks:**
- **Split policy:** group-aware, template-family-held-out, language-held-out
  (must not random-row-split templated data — see src/eval_checks.py)
```

Storage: keep the CSVs out of git (see the policy above); track provenance here
and the data via DVC / NAS / Zenodo.
