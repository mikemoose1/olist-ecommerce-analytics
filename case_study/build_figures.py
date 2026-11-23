"""Draw the case study figures from the warehouse into docs/img/.

Run after `make build` and `make recommendation`:  python case_study/build_figures.py
Every plotted value comes from DuckDB. Where the analysis report holds the same number, the script
asserts that the two agree before it draws anything.
"""
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from common import ROOT, connect, facts, row  # noqa: E402

OUT = ROOT / "docs" / "img"
GRAY, DARK, ORANGE = "#9a9a9a", "#333333", "#e8710a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_pipeline():
    fig, ax = plt.subplots(figsize=(10, 2.6))
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 26)
    steps = [
        ("Raw", "9 source files,\nchecked by hash"),
        ("Staging", "typed and cleaned,\none row per raw row"),
        ("Intermediate", "business rules,\neach with one owner"),
        ("Marts", "star schema:\norders, items, reviews"),
        ("Metrics", "each number\ndefined once"),
    ]
    w, gap = 17, 3.75
    for i, (title, body) in enumerate(steps):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 5), w, 16, boxstyle="round,pad=0.2,rounding_size=1.2", fc="#f3f3f3", ec=GRAY))
        ax.text(x + w / 2, 17.2, title, ha="center", va="center", fontweight="bold", color=DARK)
        ax.text(x + w / 2, 10.6, body, ha="center", va="center", fontsize=8.6, color=DARK)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.4, 13), (x + w + gap - 0.4, 13), arrowstyle="-|>", mutation_scale=14, color=DARK))
    ax.text(50, 1.6, "Automated checks run at every step. Each check was also shown to fail on planted bad data.", ha="center", fontsize=10, color=ORANGE)
    save(fig, "pipeline.png")


def fig_ramp(con):
    rows = con.sql(
        "select days_past_promise_capped d, bad_reviews::double / reviewed_orders s, reviewed_orders "
        "from metrics.metric_bad_review_by_days_late where days_past_promise_capped between -15 and 20 order by 1"
    ).fetchall()
    on_time = row(
        con, "select 100.0 * sum(bad_reviews) / sum(reviewed_orders) from metrics.metric_bad_review_by_days_late where days_past_promise_capped <= 0"
    )[0]
    assert f"{on_time:.1f}" == facts()["c_ramp_on_time"], (on_time, facts()["c_ramp_on_time"])
    fig, ax = plt.subplots(figsize=(8, 3.8))
    xs = [r[0] for r in rows]
    ys = [100 * r[1] for r in rows]
    ax.plot(xs, ys, color=DARK, lw=2)
    ax.axvline(0, color=ORANGE, lw=1.5, ls="--")
    ax.text(0.6, 3, "promised day", color=ORANGE, fontsize=10)
    ax.set_xlabel("days after the promised delivery day")
    ax.set_ylabel("reviews with 1 or 2 stars")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_ylim(0, 100)
    ax.text(-15, 22, f"{on_time:.1f}% up to the\npromised day", fontsize=10, color=DARK)
    ax.text(13, 62, f"about {facts()['c_ramp_plateau']}%\nfrom day {facts()['c_ramp_end_day']}", fontsize=10, color=DARK, ha="center")
    ax.grid(axis="y", color="#e6e6e6")
    save(fig, "reviews_by_days_late.png")


def fig_cause(con):
    caused, = row(con, "select sum(extra_bad_reviews) from metrics.metric_review_cost_causal")
    total, = row(con, "select count(*) from metrics.metric_late_rate_orders where review_score <= 2")
    f = facts()
    assert f"{round(caused):,}" == f["c_cost_causal"] and f"{total:,}" == f["c_low_star_all"]
    lo, hi = int(f["c_cost_range_lo"].replace(",", "")), int(f["c_cost_range_hi"].replace(",", ""))
    fig, ax = plt.subplots(figsize=(8, 2.4))
    ax.barh([0], [caused], color=ORANGE, height=0.5)
    ax.barh([0], [total - caused], left=[caused], color="#d9d9d9", height=0.5)
    ax.errorbar([caused], [0.38], xerr=[[caused - lo], [hi - caused]], color=DARK, capsize=4, lw=1.5, fmt="none")
    ax.text(0, -0.33, f"about {round(caused):,} ({100 * caused / total:.0f}%) estimated to be caused by late delivery", ha="left", va="center", color=ORANGE, fontsize=10, fontweight="bold")
    ax.text(caused + (total - caused) / 2, 0, f"{total - round(caused):,}\nnot attributed to late delivery", ha="center", va="center", color=DARK, fontsize=10)
    ax.text(caused, 0.62, f"range {lo:,} to {hi:,}", ha="center", fontsize=8.6, color=DARK)
    ax.set_xlim(0, total)
    ax.set_ylim(-0.5, 0.85)
    ax.set_yticks([])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.set_xlabel(f"all {total:,} one- and two-star reviews on delivered orders")
    ax.spines["left"].set_visible(False)
    save(fig, "cause_share.png")


def fig_handoff(con):
    q = (
        "with b as (select l.is_late, o.delivered_to_carrier_at > o.last_shipping_limit_at as hl "
        "from metrics.metric_late_rate_orders l join marts.fct_orders o using (order_id) where o.delivered_to_carrier_at is not null) "
    )
    late_if_hl, late_if_ok = row(con, q + "select 100.0*avg(is_late::int) filter (where hl), 100.0*avg(is_late::int) filter (where not hl) from b")
    share_hl = row(con, q + "select 100.0*sum(hl::int) filter (where is_late)/sum(is_late::int) from b")[0]
    f = facts()
    assert (f"{late_if_hl:.1f}", f"{late_if_ok:.1f}", f"{share_hl:.1f}") == (f["late_if_handoff_late"], f["late_if_handoff_ok"], f["seller_side_pct"])
    fig, (a, b2) = plt.subplots(1, 2, figsize=(9, 3.2), gridspec_kw={"width_ratios": [1.1, 1]})
    a.bar(["Seller shipped\nafter the ship-by date", "Seller shipped\nby the ship-by date"], [late_if_hl, late_if_ok], color=[ORANGE, GRAY], width=0.55)
    for i, v in enumerate([late_if_hl, late_if_ok]):
        a.text(i, v + 0.6, f"{v:.1f}%", ha="center", fontweight="bold", color=DARK)
    a.set_ylim(0, 27)
    a.set_title("Share of orders that arrive late", fontsize=11, loc="left")
    a.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    b2.barh([0], [share_hl], color=ORANGE, height=0.5)
    b2.barh([0], [100 - share_hl], left=[share_hl], color="#d9d9d9", height=0.5)
    b2.text(share_hl / 2, 0, f"{share_hl:.1f}%\nshipped late", ha="center", va="center", color="white", fontweight="bold", fontsize=10)
    b2.text(share_hl + (100 - share_hl) / 2, 0, f"{100 - share_hl:.1f}%\nshipped on time", ha="center", va="center", color=DARK, fontsize=10)
    b2.set_xlim(0, 100)
    b2.set_yticks([])
    b2.set_xticks([])
    b2.spines["left"].set_visible(False)
    b2.spines["bottom"].set_visible(False)
    b2.set_title("Seller handoff on all late orders", fontsize=11, loc="left")
    fig.tight_layout()
    save(fig, "seller_handoff.png")


def fig_whatif(con):
    rate, = row(con, "select value from (select 100.0*sum(is_late::int)/count(*) value from metrics.metric_late_rate_orders)")
    f = facts()
    assert f"{rate:.2f}" == "6.87"
    whatif = float(f["c_whatif_rate"])
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(["Actual,\nJan 2017 to Aug 2018", "What-if: late-shipped orders\nwere as reliable as the rest"], [rate, whatif], color=[GRAY, "white"], edgecolor=[GRAY, ORANGE], hatch=["", "//"], width=0.5, lw=1.5)
    ax.text(0, rate + 0.15, f"{rate:.2f}%", ha="center", fontweight="bold", color=DARK)
    ax.text(1, whatif + 0.15, f"{whatif:.2f}%", ha="center", fontweight="bold", color=ORANGE)
    ax.text(1, whatif / 2, "not a result,\na ceiling to test", ha="center", va="center", color=ORANGE, fontsize=10, bbox=dict(fc="white", ec="none", pad=2))
    ax.set_ylim(0, 8.5)
    ax.set_ylabel("late rate")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    save(fig, "what_if.png")




def fig_promise():
    """Extra late-delivery bad reviews under Olist's promise vs the route p95 date."""
    ev = json.loads((ROOT / "recommendation" / "promise_backtest" / "expected.json").read_text())["display"]
    olist = ev["olist_extra_rounded"]
    p95 = ev["p95_extra_rounded"]
    net = ev["p95_reduction_rounded"]
    avoided = ev["newly_on_time_avoided_rounded"]
    added = ev["newly_late_added_rounded"]
    still = ev["still_late_reduction_rounded"]
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    labels = ["Olist's promise", "Per-route date\nupdated as orders arrive"]
    ax.bar(labels, [olist, p95], color=[GRAY, "white"], edgecolor=[GRAY, ORANGE], hatch=["", "//"], width=0.5, lw=1.5)
    ax.text(0, olist + 140, f"{olist:,}", ha="center", fontweight="bold", color=DARK)
    ax.text(1, p95 + 140, f"{p95:,}", ha="center", fontweight="bold", color=ORANGE)
    ax.text(
        0.5,
        -0.32,
        f"{avoided:,} avoided, {added:,} added, {still:,} fewer from orders late either way, net {net:,}",
        transform=ax.transAxes,
        ha="center",
        color=ORANGE,
        fontsize=10,
    )
    ax.set_ylim(0, 4200)
    ax.set_ylabel("extra 1-2 star reviews from late delivery")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    save(fig, "promise_date.png")


def fig_delivery_model():
    """Extra late-delivery bad reviews on the holdout under Olist's promise, the route p95 date and the per-order model."""
    d = json.loads((ROOT / "recommendation" / "delivery_date_model" / "expected.json").read_text())["display"]
    groups = ["All holdout orders\n(March to August 2018)", "March 2018\n(the spike month)"]
    vals = {
        "Olist's promise": ([d["olist_extra"], d["march_olist"]], GRAY, GRAY, ""),
        "Per-route date": ([d["route_extra"], d["march_route"]], "white", GRAY, "//"),
        "Per-order model": ([d["model_extra"], d["march_model"]], ORANGE, ORANGE, ""),
    }
    fig, ax = plt.subplots(figsize=(8.2, 3.9))
    w = 0.26
    for i, (name, (ys, face, edge, hatch)) in enumerate(vals.items()):
        xs = [g + (i - 1) * w for g in range(len(groups))]
        ax.bar(xs, ys, width=w, color=face, edgecolor=edge, hatch=hatch, lw=1.4, label=name)
        for x, y in zip(xs, ys):
            ax.text(x, y + 25, f"{y:,}", ha="center", fontsize=10, fontweight="bold", color=ORANGE if name == "Per-order model" else DARK)
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylim(0, d["olist_extra"] * 1.18)
    ax.set_ylabel("extra 1-2 star reviews from late delivery")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.legend(frameon=False, fontsize=10, loc="upper right")
    ax.text(0.5, -0.3,
            f"The model's dates were {d['model_extra_days_1dp']} days longer than Olist's on average; the per-route date's {d['route_extra_days_1dp']}. The locked cap was 1 day.",
            transform=ax.transAxes, ha="center", color=DARK, fontsize=9.5)
    save(fig, "delivery_model.png")


def fig_tradeoff():
    """Descriptive trade-off: bad reviews prevented vs Olist against average extra days vs Olist. Not a pass test.

    Left: all tuning settings on the tuning block (tune_results.json). Right: only what was already scored on the
    holdout (expected.json): the one model setting and the route p95 date. No new setting is scored on the holdout.
    """
    tune = json.loads((ROOT / "recommendation" / "delivery_date_model" / "tune_results.json").read_text())
    ev = json.loads((ROOT / "recommendation" / "delivery_date_model" / "expected.json").read_text())
    d, h = ev["display"], ev["holdout"]
    assert len(tune["results"]) == d["n_configs"]
    cap = 1.0
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    qs = sorted({r["cfg"]["quantile"] for r in tune["results"]})
    cmap = plt.get_cmap("Oranges")
    for i, q in enumerate(qs):
        pts = [r["summary"] for r in tune["results"] if r["cfg"]["quantile"] == q]
        a1.scatter([p["mean_extra_days_vs_olist"] for p in pts], [p["reduction_v2"] for p in pts],
                   s=22, color=cmap(0.3 + 0.7 * i / max(1, len(qs) - 1)), edgecolor=DARK, lw=0.3, label=f"{q:.2f}")
    rt = tune["route_p95_tune"]
    a1.scatter([rt["mean_extra_days_vs_olist"]], [rt["v2"]["reduction"]], marker="s", s=50, color="white", edgecolor=GRAY, lw=1.5, hatch="//")
    a1.annotate("per-route date", (rt["mean_extra_days_vs_olist"], rt["v2"]["reduction"]), xytext=(8, -14), textcoords="offset points", fontsize=9, color=DARK)
    a1.set_title("Tuning block, November 2017 to February 2018\nevery setting tried", fontsize=11)
    a1.legend(title="quantile", fontsize=8, title_fontsize=8, frameon=False, loc="upper left", ncol=2)
    m, r = h["model"], h["route_p95"]
    a2.scatter([m["mean_extra_days_vs_olist"]], [m["v2"]["reduction"]], s=70, color=ORANGE, edgecolor=DARK, lw=0.5, zorder=3)
    a2.annotate(f"per-order model\n{d['model_reduction']} at +{d['model_extra_days_1dp']} days", (m["mean_extra_days_vs_olist"], m["v2"]["reduction"]),
                xytext=(-120, 0), textcoords="offset points", fontsize=9, color=ORANGE, va="center")
    a2.scatter([r["mean_extra_days_vs_olist"]], [r["v2"]["reduction"]], marker="s", s=60, color="white", edgecolor=GRAY, lw=1.5, hatch="//", zorder=3)
    a2.annotate(f"per-route date\n{d['route_reduction']} at +{d['route_extra_days_1dp']} days", (r["mean_extra_days_vs_olist"], r["v2"]["reduction"]),
                xytext=(-120, -6), textcoords="offset points", fontsize=9, color=DARK, va="center")
    a2.set_title("Holdout, March to August 2018\nonly the dates already scored", fontsize=11)
    for ax in (a1, a2):
        ax.scatter([0], [0], marker="D", s=40, color=GRAY, zorder=3)
        ax.annotate("Olist's promise", (0, 0), xytext=(-8, 10), textcoords="offset points", fontsize=9, color=DARK, ha="right")
        ax.axhline(0, color=GRAY, lw=0.8)
        ax.axvline(cap, color=DARK, lw=1.2, ls="--")
        ax.text(cap, 1.0, " 1-day cap", transform=ax.get_xaxis_transform(), fontsize=9, color=DARK, va="top")
        ax.set_xlabel("average extra days vs Olist's promise")
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    a1.set_ylabel("bad reviews prevented vs Olist")
    lo = min(min(x["summary"]["reduction_v2"] for x in tune["results"]), rt["v2"]["reduction"])
    a1.set_ylim(lo * 1.1, max(m["v2"]["reduction"], max(x["summary"]["reduction_v2"] for x in tune["results"])) * 1.3)
    a2.set_xlim(-0.5, 5.3)
    fig.text(0.5, -0.04, "A trade-off, not a pass test. The pass bar and its FAIL result are unchanged.", ha="center", fontsize=9.5, color=DARK)
    fig.tight_layout()
    save(fig, "delivery_tradeoff.png")


if __name__ == "__main__":
    con = connect()
    fig_pipeline()
    fig_ramp(con)
    fig_cause(con)
    fig_handoff(con)
    fig_whatif(con)
    fig_promise()
    fig_delivery_model()
    fig_tradeoff()
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))
