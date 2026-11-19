"""Two charts from evidence/late_rate_targets_report.json: the p-chart with its limits, and the review break point."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, GREY, RED, BLUE, GREEN = "#222222", "#9a9a9a", "#c0392b", "#1f5fa8", "#2e7d32"


def _clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GREY); ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=INK, labelsize=9)


def pchart(rep, path):
    P = rep["pchart"]; M = P["months"]; L = P["laney"]; G = P["goals"]
    x = np.arange(len(M)); rate = np.array([m["rate"] for m in M]) * 100
    ucl = np.array([m["laney_ucl"] for m in M]) * 100; lcl = np.array([m["laney_lcl"] for m in M]) * 100
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=160)
    ax.fill_between(x, lcl, ucl, step="mid", color="#e6edf5", label="Normal range (Laney p\u2032 limits, move with each month's orders)")
    ax.step(x, ucl, where="mid", color=GREY, lw=1)
    XR = len(M) - 0.4
    ax.hlines(L["stable_centre"] * 100, -0.6, XR, color=GREY, lw=1, ls=(0, (1, 2)))
    ax.hlines(L["alarm_line"] * 100, -0.6, XR, color=RED, lw=1.4, ls="--")
    ax.hlines(G["safe_25th_pct_of_stable"] * 100, -0.6, XR, color=GREEN, lw=1.4)
    ax.hlines(G["stretch_25th_pct_if_handoffs_ok"] * 100, -0.6, XR, color=GREEN, lw=1.4, ls="--")
    ax.plot(x, rate, color=INK, lw=1.2, zorder=3)
    for i, m in enumerate(M):
        face = "white" if m["thin"] else (RED if m["laney_signal"] else INK)
        ax.scatter(i, rate[i], s=46, facecolor=face, edgecolor=RED if m["laney_signal"] else INK, zorder=4, lw=1.3)
    xe = len(M) - 0.35
    ax.text(xe, L["alarm_line"] * 100, f"Alarm line {L['alarm_line'] * 100:.1f}%", color=RED, fontsize=9.5, ha="left", va="center")
    ax.text(xe, L["stable_centre"] * 100 + .5, f"Typical stable\nmonth {L['stable_centre'] * 100:.1f}%", color="#666", fontsize=8.5, ha="left", va="center")
    ax.text(xe, G["safe_25th_pct_of_stable"] * 100 + .4, f"Safe goal {G['safe_25th_pct_of_stable'] * 100:.1f}%", color=GREEN, fontsize=9.5, ha="left", va="center")
    ax.text(xe, G["stretch_25th_pct_if_handoffs_ok"] * 100 - .45, f"Stretch goal {G['stretch_25th_pct_if_handoffs_ok'] * 100:.1f}%", color=GREEN, fontsize=9.5, ha="left", va="center")
    for i, m in enumerate(M):
        if m["laney_signal"]:
            ax.annotate(f"{m['rate'] * 100:.1f}%", (i, rate[i]), textcoords="offset points", xytext=(0, 8), ha="center", color=RED, fontsize=9, fontweight="bold")
    ax.annotate("Open dots: thin months (under 2,000\norders), shown but not used for goals", (0.5, rate[0]), xytext=(2.2, 1.0), fontsize=8.5, color="#555",
                arrowprops=dict(arrowstyle="-", color=GREY), va="center")
    ax.set_xticks(x); ax.set_xticklabels([m["month"][2:] for m in M], rotation=60, fontsize=8.5)
    ax.set_ylabel("Orders that arrived late (% of delivered orders)", color=INK, fontsize=10)
    ax.set_ylim(0, 21); ax.set_xlim(-0.6, len(M) + 2.6)
    ax.set_title("Only three months were truly out of the ordinary: Nov 2017, Feb 2018 and Mar 2018", loc="left", fontsize=13, color=INK, fontweight="bold")
    fig.text(0.0, 0.005, "Monthly late rate by purchase month, 94,931 delivered single-seller orders. Red = above the normal range. Limits: 3 sigma, Laney p\u2032 (months swing "
             f"{L['sigma_z']:.1f}x more than chance alone explains).\nSafe goal = 25th percentile of the {len(P['stable_months'])} stable months; stretch goal = same, "
             "if late handoffs were late only as often as on-time handoffs.", fontsize=7.5, color="#555", va="bottom")
    _clean(ax)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path); plt.close(fig)


def breakpoint_chart(rep, path):
    D = rep["break_point"]["days"]; obs = D["observed_share_by_day"]; two = D["two_breaks_logistic"]
    xs = np.array(sorted(int(k) for k in obs)); ys = np.array([obs[str(k)] if str(k) in obs else obs[k] for k in xs]) * 100
    prob = two["model_probability_by_day"]; px = np.array(sorted(int(k) for k in prob)); py = np.array([prob[str(k)] if str(k) in prob else prob[k] for k in px]) * 100
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=160)
    ax.scatter(xs, ys, s=22, color=GREY, zorder=2, label="Observed share, each day")
    ax.plot(px, py, color=BLUE, lw=2, zorder=3, label="Two-break logistic fit")
    b1, b2 = two["first_break_day"], two["second_break_day"]
    for b in (b1, b2):
        ax.axvline(b, color=RED, lw=1, ls="--")
    ax.text(b1 - .5, 92, f"damage starts\nday {b1:+.0f}", color=RED, ha="right", fontsize=9)
    ax.text(b2 + .5, 92, f"levels off\nday {b2:+.0f}", color=RED, ha="left", fontsize=9)
    ax.axvline(0, color="#bbb", lw=.8)
    ax.set_xlabel("Days after the promised delivery day (negative = early)", fontsize=10, color=INK)
    ax.set_ylabel("Reviews that are 1-2 stars (%)", fontsize=10, color=INK)
    ax.set_ylim(0, 100); ax.set_xlim(-31, 31)
    ax.set_title("Bad reviews climb from the promised day and level off about a week later", loc="left", fontsize=13, fontweight="bold", color=INK)
    ax.legend(frameon=False, fontsize=9, loc="center left")
    _clean(ax); fig.tight_layout(); fig.savefig(path); plt.close(fig)
