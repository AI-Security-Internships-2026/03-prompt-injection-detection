# Phase 3 Cross-Tenant Data

## Two Datasets

| File | Template | Paired d | Hit Rate | Source |
|------|----------|----------|----------|--------|
| cross_tenant_verification_original_d831.csv | Short | **0.831** | 88% | Original Phase 3 (c430650) |
| cross_tenant_verification.csv | Long | 0.340 | 88% | Longer template variant (38ead11) |

**Why different d values:**
- Original: short template, secret early -> larger signal -> d=0.831
- Current: long template, secret at end -> smaller signal -> d=0.340

The d=0.831 result reported in the README comes from the original dataset.
