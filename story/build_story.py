"""Build the data story: charts from story/data, the KPI tree from story/kpi_tree.mmd, then one static HTML page.

  python story/build_story.py     writes story/build/story.html (self-contained, opens from disk) and the chart PNGs

Every chart number comes from story/data, which verification/verify_headlines.py Part C reconciles to the raw CSVs.
"""
import csv, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA, BUILD = ROOT / "story" / "data", ROOT / "story" / "build"
INK, ACCENT, MUTED, GRID = "#1f2937", "#c2410c", "#9ca3af", "#e5e7eb"
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


def fig_cost(f, rep):
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 2.8), gridspec_kw={"width_ratios": [1, 1]})
    ex, lo, hi, allr = f["low_star_excess"], *f["low_star_excess_ci"], f["low_star_all"]
    a.barh([0], [ex], color=ACCENT, xerr=err(ex, lo, hi), capsize=4, ecolor=INK)
    a.barh([0], [allr - ex], left=[ex], color=MUTED)
    a.text(0, 0.48, f"linked to lateness: {ex:,.0f}", ha="left", va="bottom", color=ACCENT, fontsize=9, fontweight="bold")
    a.text(ex + (allr - ex) / 2, 0, f"other {allr - ex:,.0f}", ha="center", va="center", color="white", fontsize=9)
    a.set_ylim(-0.6, 0.9)
    a.set_title(f"1-2 star reviews, {f['low_star_excess_share'] * 100:.1f}% linked to lateness", loc="left", fontsize=10)
    a.set_yticks([]); a.set_xlabel("reviews over 20 months (bar line: 95% range)")
    yr = rep["money"]["total_gmv_window"] * 12 / 20 / 1e6
    late = f["late_sales_per_year"] / 1e6
    b.barh([0], [late], color=ACCENT); b.barh([0], [yr - late], left=[late], color=MUTED)
    b.text(late + 0.1, 0.48, f"late orders R${late:.2f}M", ha="left", va="bottom", color=ACCENT, fontsize=9, fontweight="bold")
    b.text(late + (yr - late) / 2, 0, f"on-time orders R${yr - late:.1f}M", ha="center", va="center", color="white", fontsize=9)
    b.set_title("Sales a year: exposed to a late delivery, not lost", loc="left", fontsize=10)
    b.set_yticks([]); b.set_xlabel("R$ million a year"); b.set_ylim(-0.6, 0.9)
    save(fig, "fig_cost.png")


def fig_where_when(f):
    reg, mon = rows("late_by_region"), rows("late_by_month")
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 3.2), gridspec_kw={"width_ratios": [1, 2.4]})
    thr = 1.75 * f["late_rate"] * 100
    for i, r in enumerate(reg):
        v, lo, hi = (float(r[k]) * 100 for k in ("late_rate", "ci_low", "ci_high"))
        a.bar(i, v, color=ACCENT if i == 0 else MUTED, yerr=err(v, lo, hi), capsize=4, ecolor=INK)
        a.text(i, hi + 0.4, f"{v:.1f}%", ha="center", fontsize=9)
    a.set_xticks([0, 1], ["North and\nnortheast", "Rest of\nBrazil"]); a.set_ylabel("late rate, %"); a.set_ylim(0, 22)
    a.axhline(thr, color=INK, ls="--", lw=1); a.set_title("By region", loc="left", fontsize=10)
    x = list(range(len(mon)))
    v = [float(r["late_rate"]) * 100 for r in mon]
    b.fill_between(x, [float(r["ci_low"]) * 100 for r in mon], [float(r["ci_high"]) * 100 for r in mon], color=ACCENT, alpha=.18, lw=0)
    b.plot(x, v, color=ACCENT, marker="o", ms=3)
    b.axhline(thr, color=INK, ls="--", lw=1)
    b.text(0, thr + 0.4, f"target bar: 1.75 x overall = {thr:.1f}%", fontsize=8, color=INK)
    for i, r in enumerate(mon):
        if r["segment"] in f["top3_months"]:
            b.text(i, v[i] + 0.9, r["segment"], ha="center", fontsize=8)
    b.set_xticks(x[::3], [mon[i]["segment"] for i in x[::3]], fontsize=8); b.set_ylim(0, 22)
    b.set_title("By purchase month (band: 95% range)", loc="left", fontsize=10)
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
    items = [("Late-order comments about\ndelay or non-arrival", f["comment_delay_share"], f["comment_delay_share_ci"]),
             ("Late orders surveyed before\nthe parcel arrived", f["survey_before_share"], f["survey_before_share_ci"])]
    for i, (lab, v, (lo, hi)) in enumerate(items):
        a.barh(i, v * 100, color=ACCENT if i == 0 else MUTED, xerr=err(v * 100, lo * 100, hi * 100), capsize=4, ecolor=INK)
        a.text(hi * 100 + 1, i, f"{v * 100:.1f}%", va="center", fontsize=9)
    a.axvline(50, color=INK, ls="--", lw=1); a.text(50.5, 1.45, "threshold: half", fontsize=8)
    a.set_yticks([0, 1], [x[0] for x in items]); a.invert_yaxis(); a.set_xlim(0, 100)
    a.set_xlabel("% (bar line: 95% range; the comment share is a floor)")
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
    rep = json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())
    fig_cost(f, rep); fig_where_when(f); fig_handoff(f); fig_comments(f); fig_repeat(f)
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
