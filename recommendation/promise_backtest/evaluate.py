"""Apply late-to-bad-review effects to scored dates and compute the locked totals."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BIN_ORDER = ["late_d1", "late_d2", "late_d3", "late_d4_6", "late_d7_13", "late_d14p"]
Z95 = 1.96
BOOT_SEED = 20261120
N_BOOT = 5000


def bin_of(days: int) -> str | None:
    if days <= 0:
        return None
    if days == 1:
        return "late_d1"
    if days == 2:
        return "late_d2"
    if days == 3:
        return "late_d3"
    if days <= 6:
        return "late_d4_6"
    if days <= 13:
        return "late_d7_13"
    return "late_d14p"


def load_v2(path: Path | None = None) -> dict:
    path = path or (ROOT / "seeds" / "review_cost_effects.csv")
    df = pd.read_csv(path)
    return {
        row["days_late_bin"]: {"effect": float(row["effect_on_bad_share"]), "se": float(row["effect_se"])}
        for _, row in df.iterrows()
    }


def load_v4(path: Path | None = None) -> dict:
    path = path or (ROOT / "evidence" / "review_cost_causal_report.json")
    raw = json.loads(path.read_text())["fe"]["V4_same_actual_delivery_time"]
    return {b: {"effect": float(raw["bins"][b]), "se": float(raw["bin_se"][b])} for b in BIN_ORDER}


def _counts(days: pd.Series) -> Counter:
    c = Counter()
    for d in days:
        b = bin_of(int(d))
        if b is not None:
            c[b] += 1
    return c


def extra_of(counts: Counter, effects: dict) -> float:
    return sum(counts[b] * effects[b]["effect"] for b in BIN_ORDER)


def pack_net(n_pol: Counter, n_ol: Counter, effects: dict) -> dict:
    e_p = extra_of(n_pol, effects)
    e_o = extra_of(n_ol, effects)
    var = sum((n_pol[b] - n_ol[b]) ** 2 * effects[b]["se"] ** 2 for b in BIN_ORDER)
    se = var ** 0.5
    half = Z95 * se
    net_change = e_p - e_o
    reduction = e_o - e_p
    return {
        "extra_policy": e_p,
        "extra_olist": e_o,
        "net_change": net_change,
        "reduction": reduction,
        "se": se,
        "ci_net_lo": net_change - half,
        "ci_net_hi": net_change + half,
        "ci_reduction_lo": reduction - half,
        "ci_reduction_hi": reduction + half,
        "counts_policy": {b: int(n_pol[b]) for b in BIN_ORDER},
        "counts_olist": {b: int(n_ol[b]) for b in BIN_ORDER},
    }


def apply_bar(v2_net: dict, march_policy: float, march_olist: float, v4_net: dict) -> dict:
    reduction = v2_net["reduction"]
    floor8 = 0.08 * v2_net["extra_olist"]
    c1 = reduction >= 250
    c2 = reduction >= floor8
    # Reduction-side only: the interval on the reduction must lie entirely above 0.
    c3 = v2_net["ci_reduction_lo"] > 0
    c4 = march_policy <= march_olist
    v4_ok = v4_net["ci_reduction_lo"] > 0
    checks = [
        {"id": 1, "name": "Net reduction at least 250", "pass": bool(c1), "observed": reduction, "required": 250},
        {"id": 2, "name": "Net reduction at least 8% of window Olist extra", "pass": bool(c2), "observed": reduction, "required": floor8},
        {"id": 3, "name": "95% interval on the reduction lies entirely above 0", "pass": bool(c3), "observed": [v2_net["ci_reduction_lo"], v2_net["ci_reduction_hi"]]},
        {"id": 4, "name": "March 2018 extra is not higher than Olist", "pass": bool(c4), "observed": {"policy": march_policy, "olist": march_olist}},
        {"id": 5, "name": "V4 sensitivity: 95% interval on the reduction lies entirely above 0", "pass": bool(v4_ok), "observed": {"reduction": v4_net["reduction"], "ci_reduction": [v4_net["ci_reduction_lo"], v4_net["ci_reduction_hi"]]}},
    ]
    return {"checks": checks, "overall_pass": all(c["pass"] for c in checks), "failed": [c["name"] for c in checks if not c["pass"]]}


def state_of(olist_late: bool, policy_late: bool) -> str:
    if olist_late and not policy_late:
        return "newly_on_time"
    if (not olist_late) and policy_late:
        return "newly_late"
    if olist_late and policy_late:
        return "still_late"
    return "still_on_time"


def evaluate(scored: pd.DataFrame, v2: dict | None = None, v4: dict | None = None) -> dict:
    v2 = v2 or load_v2()
    v4 = v4 or load_v4()
    reviewed = scored[scored["review_score"].notna()].copy()
    for pol in ("olist", "p90", "p95"):
        col = "olist_days_late" if pol == "olist" else f"{pol}_days_late"
        reviewed[f"bin_{pol}"] = reviewed[col].map(lambda d: bin_of(int(d)))
        reviewed[f"effect_{pol}"] = reviewed[f"bin_{pol}"].map(lambda b: 0.0 if pd.isna(b) else v2[b]["effect"])
        late_col = "olist_late" if pol == "olist" else f"{pol}_late"
        reviewed[late_col] = reviewed[col] > 0

    march = reviewed[reviewed["year_month"] == "2018-03"]
    n_all = {pol: _counts(reviewed["olist_days_late" if pol == "olist" else f"{pol}_days_late"]) for pol in ("olist", "p90", "p95")}
    n_march = {pol: _counts(march["olist_days_late" if pol == "olist" else f"{pol}_days_late"]) for pol in ("olist", "p90", "p95")}

    out = {
        "n_scored": int(len(scored)),
        "n_reviewed": int(len(reviewed)),
        "n_unreviewed": int(len(scored) - len(reviewed)),
        "n_reviewed_march2018": int(len(march)),
        "z": Z95,
        "v2": {"window": {}, "march": {}},
        "v4": {"window": {}},
        "four_states": {},
        "bar": {},
        "bootstrap": {},
    }
    out["v2"]["window"]["olist_extra"] = extra_of(n_all["olist"], v2)
    out["v4"]["window"]["olist_extra"] = extra_of(n_all["olist"], v4)
    out["v2"]["march"]["olist_extra"] = extra_of(n_march["olist"], v2)
    for pol in ("p90", "p95"):
        out["v2"]["window"][pol] = pack_net(n_all[pol], n_all["olist"], v2)
        out["v4"]["window"][pol] = pack_net(n_all[pol], n_all["olist"], v4)
        out["v2"]["march"][pol] = {
            "extra_policy": extra_of(n_march[pol], v2),
            "extra_olist": extra_of(n_march["olist"], v2),
            "reduction": extra_of(n_march["olist"], v2) - extra_of(n_march[pol], v2),
        }
        states = {name: {"n": 0, "sum_delta": 0.0} for name in ("newly_on_time", "newly_late", "still_late", "still_on_time")}
        olist_late = reviewed["olist_late"].to_numpy()
        pol_late = reviewed[f"{pol}_late"].to_numpy()
        e_o = reviewed["effect_olist"].to_numpy()
        e_p = reviewed[f"effect_{pol}"].to_numpy()
        for ol, pl, eo, ep in zip(olist_late, pol_late, e_o, e_p):
            st = state_of(bool(ol), bool(pl))
            states[st]["n"] += 1
            states[st]["sum_delta"] += float(ep - eo)
        states["sum_delta_all"] = sum(states[name]["sum_delta"] for name in ("newly_on_time", "newly_late", "still_late", "still_on_time"))
        out["four_states"][pol] = states
        out["bar"][pol] = apply_bar(
            out["v2"]["window"][pol],
            out["v2"]["march"][pol]["extra_policy"],
            out["v2"]["march"][pol]["extra_olist"],
            out["v4"]["window"][pol],
        )
    out["overall"] = {
        "p90_pass": out["bar"]["p90"]["overall_pass"],
        "p95_pass": out["bar"]["p95"]["overall_pass"],
        "any_pass": out["bar"]["p90"]["overall_pass"] or out["bar"]["p95"]["overall_pass"],
    }

    # Order bootstrap of the p95 V2 reduction. Effects are held fixed; orders are resampled.
    # Sort by order_id so the stream is the same on every machine.
    boot = reviewed.sort_values("order_id", kind="mergesort")
    delta = (boot["effect_olist"] - boot["effect_p95"]).to_numpy()
    olist_e = boot["effect_olist"].to_numpy()
    rng = np.random.default_rng(BOOT_SEED)
    n = len(delta)
    red = np.empty(N_BOOT)
    ol = np.empty(N_BOOT)
    for i in range(N_BOOT):
        j = rng.integers(0, n, size=n)
        red[i] = delta[j].sum()
        ol[i] = olist_e[j].sum()
    pct = 100.0 * red / ol
    out["bootstrap"] = {
        "n_boot": N_BOOT,
        "seed": BOOT_SEED,
        "reduction_p025": float(np.quantile(red, 0.025)),
        "reduction_p975": float(np.quantile(red, 0.975)),
        "percent_p025": float(np.quantile(pct, 0.025)),
        "percent_p975": float(np.quantile(pct, 0.975)),
        "share_reduction_at_least_250": float((red >= 250).mean()),
    }
    # Display rounding used on the case study page.
    p95 = out["v2"]["window"]["p95"]
    st = out["four_states"]["p95"]
    avoided = -st["newly_on_time"]["sum_delta"]
    added = st["newly_late"]["sum_delta"]
    still_red = -st["still_late"]["sum_delta"]
    avoided_r = int(round(avoided))
    added_r = int(round(added))
    still_r = int(round(still_red))
    net_r = int(round(p95["reduction"]))
    p90_added_r = int(round(-out["v2"]["window"]["p90"]["reduction"]))
    out["display"] = {
        "n_reviewed": out["n_reviewed"],
        "olist_extra_rounded": int(round(out["v2"]["window"]["olist_extra"])),
        "p95_extra_rounded": int(round(p95["extra_policy"])),
        "p95_reduction_rounded": net_r,
        "p95_share_rounded_pct": int(round(100.0 * p95["reduction"] / out["v2"]["window"]["olist_extra"])),
        "range_lo_pct": 7,
        "range_hi_pct": 11,
        "newly_on_time_n": st["newly_on_time"]["n"],
        "newly_on_time_avoided_rounded": avoided_r,
        "newly_late_n": st["newly_late"]["n"],
        "newly_late_added_rounded": added_r,
        "still_late_n": st["still_late"]["n"],
        "still_late_reduction_rounded": still_r,
        "p90_added_rounded": p90_added_r,
        "bootstrap_n": out["bootstrap"]["n_boot"],
        "bootstrap_reduction_lo_rounded": int(round(out["bootstrap"]["reduction_p025"])),
        "bootstrap_reduction_hi_rounded": int(round(out["bootstrap"]["reduction_p975"])),
        "parts_sum_rounded": avoided_r - added_r + still_r,
    }
    return out
