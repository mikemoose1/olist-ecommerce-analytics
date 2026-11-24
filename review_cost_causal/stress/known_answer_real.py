"""(c) Known-answer test on a copy of the REAL orders (pre-registered in docs/preregistration_v2.md).

Real lateness, sellers, categories, months, prices and promised days are kept; only the outcome is replaced by one whose
cause is known. Then the six existing fixed-effects specifications are run unchanged and we check whether they find
the planted number of extra bad reviews. Writes evidence/known_answer_real_report.json. About 15 minutes on 4 cores.
Usage: python review_cost_causal/stress/known_answer_real.py [--workers N]
"""
import json, os, sys, time
from multiprocessing import Pool
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import E, SPECS, ROOT, add_spec_columns, load, published  # noqa: E402

SEEDS = range(20)
SCENARIOS = ["S0_null", "S1_half", "S2_full", "S3_logit"]
expit = lambda z: 1 / (1 + np.exp(-z))
logit = lambda p: np.log(p / (1 - p))


def baseline_chance(R):
    """p0: linear model fitted on the real ON-TIME orders only (seller, category, month effects + price, freight,
    promised days), predicted for every order. Sellers with no on-time order get no seller effect. Clipped to [0.01, 0.95]."""
    on = R[R.late == 0]
    fe_cols = ("seller", "category", "ym"); cov = ["lprice", "lfreight", "promised_days"]
    codes = {c: pd.factorize(on[c])[0] for c in fe_cols}
    M = E.demean(np.column_stack([on.y.to_numpy(float), on[cov].to_numpy(float)]), [codes[c] for c in fe_cols])
    b = np.linalg.lstsq(M[:, 1:], M[:, 0], rcond=None)[0]
    r = on.y.to_numpy(float) - on[cov].to_numpy(float) @ b
    const = r.mean(); r = r - const
    fe = {c: np.zeros(codes[c].max() + 1) for c in fe_cols}
    for _ in range(200):   # backfitting: each effect = group mean of what the others leave
        prev = {c: v.copy() for c, v in fe.items()}
        for c in fe_cols:
            rest = r - sum(fe[o][codes[o]] for o in fe_cols if o != c)
            fe[c] = np.bincount(codes[c], rest) / np.bincount(codes[c])
        if max(np.abs(fe[c] - prev[c]).max() for c in fe_cols) < 1e-10: break
    p0 = const + R[cov].to_numpy(float) @ b
    for c in fe_cols:
        lookup = dict(zip(on[c], fe[c][codes[c]]))
        p0 = p0 + R[c].map(lookup).fillna(0.0).to_numpy(float)
    return np.clip(p0, 0.01, 0.95)


def planted_chances(R, p0, scenario, v2_bins):
    B = E.late_bins(R.x)                       # one column per days-late bin, 0 for on-time orders
    tau = np.array([v2_bins[name] for _, _, name in E.BINS])
    late = R.late.to_numpy() == 1
    if scenario == "S0_null":
        return p0.copy()
    if scenario in ("S1_half", "S2_full"):
        s = 0.5 if scenario == "S1_half" else 1.0
        return np.clip(p0 + B @ (s * tau), 0, 1)
    # S3: same bin effects on the log-odds scale; shift per bin solved so the average added chance in the bin equals tau
    p1 = p0.copy(); lp0 = logit(p0)
    for j, t in enumerate(tau):
        m = B[:, j] == 1
        lo, hi = 0.0, 20.0
        for _ in range(60):
            g = (lo + hi) / 2
            if (expit(lp0[m] + g) - p0[m]).mean() < t: lo = g
            else: hi = g
        p1[m] = expit(lp0[m] + (lo + hi) / 2)
    return p1


def task(args):
    scenario, seed, R, p0, p1 = args
    rng = np.random.default_rng(1000 * SCENARIOS.index(scenario) + seed)
    d = R.copy(); d["y"] = (rng.random(len(d)) < p1).astype(int)
    late = d.late.to_numpy() == 1
    truth = float((p1 - p0)[late].sum())
    res = {"scenario": scenario, "seed": seed, "truth": truth, "naive": E.naive_gap(d)["extra"]}
    for k, kw in SPECS.items():
        r = E.fe_lpm_att(d, **kw)
        res[k] = {"extra": r["extra"], "lo": r["lo"], "hi": r["hi"]}
    return res


def summarize(runs):
    out = {}
    for s in SCENARIOS:
        rs = [r for r in runs if r["scenario"] == s]
        truth = float(np.mean([r["truth"] for r in rs]))
        row = {"truth_mean": truth, "truth_min": min(r["truth"] for r in rs), "truth_max": max(r["truth"] for r in rs),
               "naive_mean": float(np.mean([r["naive"] for r in rs]))}
        for k in SPECS:
            est = np.array([r[k]["extra"] for r in rs]); t = np.array([r["truth"] for r in rs])
            cov = int(sum(r[k]["lo"] <= r["truth"] <= r[k]["hi"] for r in rs))
            row[k] = {"mean_estimate": float(est.mean()), "mean_bias": float((est - t).mean()),
                      "bias_pct_of_truth": float(100 * (est - t).mean() / truth) if truth else None, "covered": cov, "seeds": len(rs)}
        out[s] = row
    return out


def pass_rules(summary):
    v = lambda s: summary[s]["V2_preferred"]
    rules = []
    for s in ("S0_null", "S1_half", "S2_full"):
        ok_cov = v(s)["covered"] >= 17
        ok_bias = abs(v(s)["mean_bias"]) <= 50 if s == "S0_null" else abs(v(s)["bias_pct_of_truth"]) <= 5
        rules.append({"id": f"C-1 {s}", "pass": bool(ok_cov and ok_bias),
                      "observed": {"covered": v(s)["covered"], "mean_bias": v(s)["mean_bias"], "bias_pct": v(s)["bias_pct_of_truth"]}})
    rules.append({"id": "C-2 S3_logit", "pass": bool(abs(v("S3_logit")["bias_pct_of_truth"]) <= 10),
                  "observed": {"bias_pct": v("S3_logit")["bias_pct_of_truth"]}})
    # C-3: an estimator that always returns 0 (interval [0, 0]) must fail C-1 where the truth is not zero
    zero_fails = all(not (summary[s]["truth_min"] <= 0 <= summary[s]["truth_max"]) for s in ("S1_half", "S2_full"))
    rules.append({"id": "C-3 always-zero estimator fails S1 and S2", "pass": bool(zero_fails),
                  "observed": {s: [summary[s]["truth_min"], summary[s]["truth_max"]] for s in ("S1_half", "S2_full")}})
    return rules


if __name__ == "__main__":
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    t0 = time.time()
    R = add_spec_columns(load())
    v2_bins = published()["fe"]["V2_preferred"]["bins"]
    p0 = baseline_chance(R)
    jobs = []
    for s in SCENARIOS:
        p1 = planted_chances(R, p0, s, v2_bins)
        jobs += [(s, seed, R, p0, p1) for seed in SEEDS]
    with Pool(workers) as pool:
        runs = pool.map(task, jobs, chunksize=1)
    summary = summarize(runs)
    late = R.late.to_numpy() == 1
    out = {"what": "Planted effects in a copy of the real reviewed orders; six existing specifications run unchanged",
           "n_orders": len(R), "n_late": int(late.sum()),
           "baseline_chance": {"mean": float(p0.mean()), "mean_on_time": float(p0[~late].mean()), "mean_late": float(p0[late].mean()),
                               "clipped_low": int((p0 <= 0.01).sum()), "clipped_high": int((p0 >= 0.95).sum())},
           "summary": summary, "pass_rules": pass_rules(summary), "runs": runs, "minutes": (time.time() - t0) / 60}
    json.dump(out, open(os.path.join(ROOT, "evidence", "known_answer_real_report.json"), "w"), indent=1, default=float)
    for r in out["pass_rules"]:
        print(("PASS " if r["pass"] else "FAIL ") + r["id"], r["observed"])
