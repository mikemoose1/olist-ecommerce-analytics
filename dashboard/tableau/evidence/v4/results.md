# Click test, six-chart page (`out_v4_six_chart.twb`)

Tableau Desktop 2026.3 (macOS), 2026-11-20. Real mouse clicks in Presentation Mode (`harness/click_probe4.py`, `harness/mclick.js`), then Dashboard > Export Image.
Expected values come from the DuckDB warehouse, not from `orders.csv`: `click_expect.py`, output in `expected.md`.
Images here are downscaled to 1366 x 768; the md5 of each full-size export is in the table. The page itself is `../../v4_six_chart.png` (full size, md5 `3132ed48...`, the same as the baseline export).

| step | image | shipped-late chart (by ship-by date / shipped late) | region chart (N/NE / rest) | months labels Nov / Feb / Mar / Aug | sellers chart | full-size md5 | vs DuckDB |
|---|---|---|---|---|---|---|---|
| baseline | `baseline.png` | 5.4% / 21.2% | 12.2% / 6.2% | 902 / 925 / 1,324 / 393 | 1,018 / 791 | `3132ed48...` | match |
| click seller bar "3 or more months" | `click_seller_3plus.png` | 6.1% / 23.5% | 13.6% / 7.8% | 461 / 381 / 555 / 99 | 1,018 only | `721c4f2c...` | match |
| click it again | (same as baseline) | back to baseline | | | | `3132ed48...` | cleared |
| click region bar "North and northeast" | `click_region.png` | 11.0% / 24.5% | 12.2% / rest greyed | 161 / 147 / 252 / 11 | 139 / 94 | `d0553bd1...` | match |
| click it again | (same as baseline) | back to baseline | | | | `3132ed48...` | cleared |
| click month bar Nov 2017 | `click_month.png` | 9.3% / 34.0% | 20.3% / 11.6% | 902 (other bars greyed) | 203 / 114 | `81a3eacf...` | match |
| click it again | (same as baseline) | back to baseline | | | | `3132ed48...` | cleared |

Not clicked: the "1 to 2 months" seller bar. Expected from the warehouse: 5.7% / 29.3%, 13.1% / 7.2%, 276 / 315 / 436 / 196, 791 (in `expected.md`).

Method: Presentation Mode centres the 1366 x 768 dashboard on the 1728 x 1117 pt screen (offset 181, 174.5). Clicks were at screen points (474, 724.5) for the seller bar, (908, 697.5) for the region bar and (1334, 794.5) for the Nov 2017 bar. A second click on the same mark came 2.5 s later, so it is not read as a double-click. Each of the three tests was a separate Presentation Mode session.
