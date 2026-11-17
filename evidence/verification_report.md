# Headline reconciliation

| Metric | Mart | Independent (raw CSVs) | First pass | Verdict | Note |
|---|---|---|---|---|---|
| repeat_rate_90d (headline) | 1.28 (991/77560) | 1.28 (991/77560) | 1.24 | **VERIFIED** | First pass reported 1.24% under the 'second order only' rule; the headline uses 'any_later_order_24h'. The C6 experiment reproduces 1.24% exactly under the first-pass rule. |
| repeat_rate_ever (secondary) | 3.04 (2887/94983) | 3.04 (2887/94983) | 3.04 | **VERIFIED** |  |
| late_rate | 6.79 (6531/96203) | 6.79 (6531/96203) | 6.79 | **VERIFIED** |  |
| review_score | 4.156 (397176/95560) | 4.156 (397176/95560) | 4.156 | **VERIFIED** |  |
| late_review_gap_raw | 2.021 | 2.021 | 2.021 | **VERIFIED** |  |
| late_penalty_controlled (OLS, from marts) | -1.992 CI [-2.023, -1.962] | - | -1.992 | **VERIFIED** | Recomputed with statsmodels from marts; compared to the first pass within 0.01 stars. |
