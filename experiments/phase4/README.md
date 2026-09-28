# Phase 4 — Information Recovery Feasibility

## Objective
Determine how much information about a victim tenant's hidden cached
prefix can be inferred by an attacker tenant using only the observable
timing/cache oracle validated in Phase 2 (d=39.7) and Phase 3 (d=0.831).

## Scope of this phase
This phase builds:
- A controlled victim/ground-truth harness (attacker never sees the secret directly)
- Candidate/probe generation across 4 entropy categories
- A timing measurement + hit/miss classification interface (built on the
  existing `timed_request()` pattern from Phase 2/3, consolidated here
  rather than duplicated again)
- Ablation experiments (trial count, entropy category, prefix length, noise)
- Oracle-accuracy vs information-recovery-accuracy evaluation (kept as
  two distinct metrics, not conflated)

## Explicitly out of scope for what's implemented here
The adaptive candidate-search/recovery algorithm (i.e. the logic that
decides which candidate to try next based on prior oracle results) is
NOT implemented in this repo. This is intentional. See
`search_strategy.py` for the interface stub and rationale. This
component must be sourced from the PROMPTPEEK paper's published
methodology directly, with supervisor guidance, and implemented
separately with that authorization.

Where this phase does NOT plug in a real search strategy, ablation and
oracle-characterization experiments still run and produce legitimate
results about oracle reliability under different conditions - they do
not depend on the search component existing.

## Directory contents (built incrementally)
- `secrets.py` — ground-truth secret generators (4 categories)
- `measure.py` — shared timing + classification interface
- `logger.py` — CSV logging schema
- `search_strategy.py` — interface stub only (see above)
- `run_phase4.py` — experiment runner
- `run_ablation.py` — ablation sweep
