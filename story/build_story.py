"""Build the data story: charts from story/data, the KPI tree from story/kpi_tree.mmd, then one static HTML page.

  python story/build_story.py     writes story/build/story.html (self-contained, opens from disk) and the chart PNGs

Every chart number comes from story/data, which verification/verify_headlines.py Part C reconciles to the raw CSVs.
"""
import csv, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA, BUILD = ROOT / "story" / "data", ROOT / "story" / "build"
BARS = yaml.safe_load((ROOT / "story" / "kpi_tree.yml").read_text())["thresholds"]   # the one source for the bars
INK, ACCENT, MUTED, GRID, GOAL = "#1f2937", "#c2410c", "#9ca3af", "#e5e7eb", "#1d4ed8"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "figure.dpi": 110})


def rows(name):
    return list(csv.DictReader((DATA / f"{name}.csv").open()))


def save(fig, name):
    fig.tight_layout()
    fig.savefig(BUILD / name, dpi=160, facecolor="white")
    plt.close(fig)


def err(v, lo, hi):
    return [[v - lo], [hi - v]]


def fig_cost(f):
    fig = plt.figure(figsize=(9, 5.6))
    g = fig.add_gridspec(2, 2, height_ratios=[1, 1.5], hspace=0.65)
    a, b, c = fig.add_subplot(g[0, 0]), fig.add_subplot(g[0, 1]), fig.add_subplot(g[1, :])
    rc, allr = f["review_cost_causal"], f["low_star_all"]
    ex, (lo, hi) = rc["extra"], rc["range"]
    a.barh([0], [ex], color=ACCENT, xerr=err(ex, lo, hi), capsize=4, ecolor=INK)
    a.barh([0], [allr - ex], left=[ex], color=MUTED)
    a.text(0, 0.48, f"caused by lateness: about {round(ex, -1):,.0f}", ha="left", va="bottom", color=ACCENT, fontsize=9, fontweight="bold")
    a.text(ex + (allr - ex) / 2, 0, f"other {allr - ex:,.0f}", ha="center", va="center", color="white", fontsize=9)
    a.set_ylim(-0.6, 0.9)
    a.set_title(f"1-2 star reviews: about {100 * rc['share']:.0f}% caused by lateness", loc="left", fontsize=10)
    a.set_yticks([]); a.set_xlabel("reviews over 20 months (bar line: range across\nsix ways of comparing)")
    yr, late = f["total_sales_last12"] / 1e6, f["late_sales_last12"] / 1e6
    b.barh([0], [late], color=ACCENT); b.barh([0], [yr - late], left=[late], color=MUTED)
    b.text(0, 0.48, f"late orders R${late:.2f}M ({100 * late / yr:.1f}%)", ha="left", va="bottom", color=ACCENT, fontsize=9, fontweight="bold")
    b.text(late + (yr - late) / 2, 0, f"other orders R${yr - late:.1f}M", ha="center", va="center", color="white", fontsize=9)
    b.set_title("Last 12 months of sales: exposed, not lost", loc="left", fontsize=10)
    b.set_yticks([]); b.set_xlabel("R$ million, purchases 2017-09 to 2018-08"); b.set_ylim(-0.6, 0.9)
    rp = f["ramp"]
    days = [r for r in rows("bad_review_by_days_late") if -10 <= int(r["segment"]) <= 15]
    x, y = [int(r["segment"]) for r in days], [100 * float(r["bad_share"]) for r in days]
    c.plot(x, y, color=ACCENT, marker="o", ms=3, lw=1.5)
    s0, s1, top = rp["start_day"], rp["end_day"], 100 * rp["plateau_share"]
    c.hlines(100 * rp["on_time_share"], -10, s0, color=INK, lw=1, ls="--")
    c.hlines(top, s1, 15, color=INK, lw=1, ls="--")
    c.axvline(0.5, color=MUTED, lw=1)
    c.text(0.7, 96, "promised day", fontsize=8, color=INK, va="top")
    c.text(-10, 100 * rp["on_time_share"] + 3, f"{100 * rp['on_time_share']:.1f}% up to the promised day", fontsize=9, color=INK)
    c.text(3.6, 26, f"climbs about {100 * rp['slope_per_day']:.0f}\npoints a day", fontsize=9, color=ACCENT, ha="left")
    c.text(15, top - 9, f"levels near {top:.0f}% from day {s1}", fontsize=9, color=INK, ha="right")
    c.set_xlim(-10.5, 15.5); c.set_ylim(0, 100)
    c.set_xlabel("days the order arrived after the promised day (negative = early)"); c.set_ylabel("1-2 star reviews, %")
    c.set_title("A ramp, not a cliff: share of 1-2 star reviews by days late", loc="left", fontsize=10)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.93, bottom=0.1)
    fig.savefig(BUILD / "fig_cost.png", dpi=160, facecolor="white")
    plt.close(fig)


def fig_where_when(f):
    reg, mon = rows("late_by_region"), rows("late_rate_control")
    tg = f["targets"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 3.6), gridspec_kw={"width_ratios": [1, 2.6]})
    thr = BARS["segment_ratio"] * f["late_rate"] * 100
    for i, r in enumerate(reg):
        v, lo, hi = (float(r[k]) * 100 for k in ("late_rate", "ci_low", "ci_high"))
        a.bar(i, v, color=ACCENT if i == 0 else MUTED, yerr=err(v, lo, hi), capsize=4, ecolor=INK)
        a.text(i, hi + 0.4, f"{v:.1f}%", ha="center", fontsize=9)
    a.set_xticks([0, 1], ["North and\nnortheast", "Rest of\nBrazil"]); a.set_ylabel("late rate, %"); a.set_ylim(0, 22)
    a.axhline(thr, color=INK, ls="--", lw=1); a.set_title("By region", loc="left", fontsize=10)
    a.text(1.45, thr + 0.4, f"target bar {thr:.1f}%", fontsize=8, color=INK, ha="right")
    x = list(range(len(mon)))
    v = [float(r["late_rate"]) * 100 for r in mon]
    flag = [r["laney_signal"] == "True" for r in mon]
    b.step(x, [float(r["laney_ucl"]) * 100 for r in mon], where="mid", color=INK, lw=1.2)
    b.axhline(100 * tg["goal"], color=GOAL, lw=1.4)
    stretch_line = b.axhline(100 * tg["stretch"], color=GOAL, lw=1, ls="--", alpha=.55,
                             label=f"stretch {100 * tg['stretch']:.1f}%: the middle month if late seller handoffs\nran late no more often than on-time ones (a what-if)")
    b.plot(x, v, color=ACCENT, lw=1.2)
    b.scatter([i for i in x if not flag[i]], [v[i] for i in x if not flag[i]], color=ACCENT, s=12, zorder=3)
    b.scatter([i for i in x if flag[i]], [v[i] for i in x if flag[i]], facecolor="white", edgecolor=ACCENT, lw=1.5, s=40, zorder=3)
    for i in x:
        if flag[i]:
            b.text(i, v[i] + 0.9, mon[i]["segment"], ha="center", fontsize=8)
    end = len(mon) - 0.4
    b.text(end, 100 * tg["alarm_line"] + 0.5, f"alarm line ({100 * tg['alarm_line']:.2f}% at a typical month)", fontsize=8, color=INK, ha="right")
    b.text(end, 100 * tg["goal"] + 0.4, f"goal {100 * tg['goal']:.1f}%", fontsize=8, color=GOAL, ha="right")
    b.legend(handles=[stretch_line], loc="upper left", frameon=False, fontsize=8, labelcolor=GOAL)   # the label sits in empty space, not on the data
    b.set_xticks(x[::3], [mon[i]["segment"] for i in x[::3]], fontsize=8); b.set_ylim(0, 22); b.set_xlim(-0.5, len(mon) - 0.3)
    b.set_title("By purchase month (open circle: above the alarm line)", loc="left", fontsize=10)
    save(fig, "fig_where_when.png")


def fig_handoff(f):
    h = {r["segment"]: r for r in rows("late_by_handoff")}
    fig, a = plt.subplots(figsize=(6, 2.8))
    for i, (k, lab, c) in enumerate([("Handed over after ship-by", "after ship-by date", ACCENT), ("Handed over on time", "on time", MUTED)]):
        v, lo, hi = (float(h[k][c2]) * 100 for c2 in ("late_rate", "ci_low", "ci_high"))
        a.barh(i, v, color=c, xerr=err(v, lo, hi), capsize=4, ecolor=INK)
        a.text(hi + 0.4, i, f"{v:.1f}% late  ({int(h[k]['late']):,} of {int(h[k]['orders']):,} orders)", va="center", fontsize=9)
    a.set_yticks([0, 1], ["Seller handed over\nafter ship-by date", "Handed over\non time"]); a.invert_yaxis()
    a.set_xlim(0, 48); a.set_xlabel("late rate, % (bar line: 95% range)")
    a.set_title(f"Late handoffs: {f['handoff_late_share_of_late'] * 100:.1f}% of all late orders", loc="left", fontsize=10)
    save(fig, "fig_handoff.png")


def fig_comments(f):
    fig, a = plt.subplots(figsize=(6, 2.6))
    items = [("Late-order comments about delay\nor non-arrival (keyword rule)", f["comment_delay_share"], f["comment_delay_share_ci"]),
             ("Late orders surveyed before\nthe parcel arrived", f["survey_before_share"], f["survey_before_share_ci"])]
    for i, (lab, v, (lo, hi)) in enumerate(items):
        a.barh(i, v * 100, color=ACCENT if i == 0 else MUTED, xerr=err(v * 100, lo * 100, hi * 100), capsize=4, ecolor=INK)
        a.text(hi * 100 + 1, i, f"{v * 100:.1f}%", va="center", fontsize=9)
    bar = BARS["comment_share"]
    a.axvline(bar, color=INK, ls="--", lw=1); a.text(bar + 0.5, 1.45, f"threshold: {bar:g}%", fontsize=8)
    a.set_yticks([0, 1], [x[0] for x in items]); a.invert_yaxis(); a.set_xlim(0, 100)
    a.set_xlabel("% (bar line: 95% range)")
    save(fig, "fig_comments.png")


def fig_repeat(f):
    fig, a = plt.subplots(figsize=(6, 1.8))
    v, (lo, hi) = f["repeat_effect_pts"], f["repeat_effect_pts_ci"]
    a.errorbar([v], [0], xerr=err(v, lo, hi), fmt="o", color=ACCENT, ecolor=ACCENT, capsize=5, ms=7)
    a.axvline(0, color=INK, lw=1)
    a.text(v, 0.25, f"{v:+.2f} points  (range {lo:+.2f} to {hi:+.2f})", ha="center", fontsize=9)
    a.set_yticks([]); a.set_ylim(-0.5, 0.6); a.set_xlim(-1, 1)
    a.set_xlabel("change in the 90-day return rate after a late first order, percentage points")
    save(fig, "fig_repeat.png")


def tree_top(mmd):
    """The KPI tree cut to the root and its direct children, for the first view."""
    edge = re.compile(r"^\s+(\w+) \S+(?: \S+)*? (\w+)$")
    keep = {"cost"} | {m.group(2) for m in map(edge.match, mmd.splitlines()) if m and m.group(1) == "cost"}
    out = []
    for line in mmd.splitlines():
        node, e = re.match(r"\s+(\w+)\[", line), edge.match(line)
        if line.startswith("flowchart") or line.strip().startswith("classDef"):
            out.append(line)
        elif node:
            if node.group(1) in keep:
                out.append(line)
        elif line.strip().startswith("class "):
            names = [n for n in line.split()[1].split(",") if n in keep]
            if names:
                out.append(f"  class {','.join(names)} {line.split()[2]}")
        elif e and e.group(1) in keep and e.group(2) in keep:
            out.append(line)
    return "\n".join(out) + "\n"


def main():
    t0 = time.time()
    BUILD.mkdir(exist_ok=True)
    f = json.loads((DATA / "facts.json").read_text())
    fig_cost(f); fig_where_when(f); fig_handoff(f); fig_comments(f); fig_repeat(f)
    mmd = (ROOT / "story" / "kpi_tree.mmd").read_text()
    src = (ROOT / "story" / "story.qmd").read_text()
    src = src.replace("<!-- KPI_TREE_TOP -->", f"```{{mermaid}}\n{tree_top(mmd)}```")
    full = mmd.replace("flowchart TD", "flowchart LR", 1)
    src = src.replace("<!-- KPI_TREE_FULL -->", f"::: {{.column-screen-inset}}\n```{{mermaid}}\n{full}```\n:::")
    (BUILD / "story.qmd").write_text(src)
    quarto = shutil.which("quarto", path=os.path.dirname(sys.executable)) or shutil.which("quarto")
    p = subprocess.run([quarto, "render", "story.qmd", "--to", "html"], cwd=BUILD, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(p.stdout + p.stderr)
    html = BUILD / "story.html"
    print(f"built {html.relative_to(ROOT)} ({html.stat().st_size / 1e6:.1f} MB) in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
