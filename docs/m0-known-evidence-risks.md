# M0 Known Evidence Risks and Terminology Notes

This note records known evidence/provenance risks that must remain visible during the two-journal workflow. These items are preserved for traceability; they should not be silently deleted or treated as final paper evidence without verification.

## 1. Legacy / Mislabeled HardenedGuard Results

Some historical result files use labels implying that the predictions came from `HardenedGuard`, while the underlying predictions were produced by the earlier classical ML detector.

Known example:

- `mcnemar_PIGuard_raw_vs_HardenedGuard__Ours_.json`
- its compared prediction source is the classical ML detector output rather than the actual full HardenedGuard pipeline.

Action for later milestones:

- preserve these historical files;
- mark them as `legacy` / `needs-rerun` where appropriate;
- do not cite them as final HardenedGuard evidence;
- regenerate the comparison from the actual HardenedGuard implementation before manuscript freeze.

## 2. SGLang Shared-Cache vs Tenant-Isolated Reproducibility Inconsistency

Historical SGLang baseline results demonstrating cross-tenant cache leakage and chained secret/PIN recovery were generated under a shared/unsalted cache configuration.

The current victim/attacker application state uses tenant-specific cache isolation/salting, so the current code does not directly reproduce the historical unsalted baseline without configuration changes.

Action for the KV-cache track:

- provide explicit, reproducible experiment modes from the same codebase for:
  - `shared-cache`
  - `tenant-isolated`
  - `cache-disabled`
- record the selected mode in experiment metadata and result files;
- rerun the baseline and mitigation conditions from the current research code before final paper numbers are frozen.

Until this is completed, historical shared-cache results remain preserved research evidence but are not yet fully reproducible from the current application state.

## 3. Conversation-History Detection Is Not KV-Cache Security

The HardenedGuard multi-turn component analyzes conversation text/history across turns. It does not inspect KV tensors, prefix-cache entries, server-side cache state, or cache-sharing behavior.

Therefore:

- describe it as `cross-turn conversation-context detection` or `conversation-history analysis`;
- do not describe it as a `KV-cache detector`;
- keep the HardenedGuard/prompt-injection research track technically separate from the inference-system KV/prefix-cache security track.

## Status

These are M0 documentation items only. They do not require expensive reruns during M0. The corresponding fixes and final verification belong to the later KV-cache and HardenedGuard research milestones.
