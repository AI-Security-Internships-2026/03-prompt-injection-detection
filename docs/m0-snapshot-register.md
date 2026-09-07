# M0 Snapshot Register

This note records the verified research snapshots preserved before journal-oriented consolidation on `supervisor/m0-stabilization`.

| Research snapshot | Source branch/state | Git tag | Commit |
|---|---|---|---|
| HardenedGuard / RANA baseline | `RANA` / `dev` state | `m0-hardenedguard-rana` | `da2e5fab13e6e8224c9de085c2633df1847944e6` |
| Week-9 evaluation snapshot | `week9-literature-review-on-kv-cache` | `m0-week9-evaluation` | `cfa163ced1769171b999d8ad0fce2de74142481c` |
| Latest KV-cache / SGLang snapshot | `week11-sglang-reproduction` | `m0-kv-sglang-week11` | `d20d0d1c6408917c3e4594d5f58f416a7728be3f` |

## Notes

- `main` remains intentionally behind and is not part of the current journal-development workflow.
- `dev` remains the authoritative research integration branch.
- These tags are preservation points only; historical branches should not be deleted merely because their useful work is later consolidated into `dev`.
- The project is proceeding with two journal tracks: KV-cache security and HardenedGuard / prompt-injection canonicalization.
