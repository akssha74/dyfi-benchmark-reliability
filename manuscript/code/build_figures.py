"""Deterministic generator for the manuscript's figures.

Runs in the dedicated figures venv (manuscript/.venv-fig, matplotlib 3.11.1). It
consumes ONLY manuscript/derived/asset_inputs.json (frozen, verified numbers) and
renders concise, accessible vector SVG + 300-dpi PNG figures. No value is plotted
that is not already in the frozen result surface; no trend line implies a claim
the resource does not make.

Determinism: Agg backend, fixed rcParams, fixed svg.hashsalt, SOURCE_DATE_EPOCH
pinned, bundled DejaVu font. Two clean runs produce byte-identical files (checked
by the validator).
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("SOURCE_DATE_EPOCH", "1262304000")  # 2010-01-01, fixed

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "dyfi-usgs-severe-felt-intensity-v1"
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["svg.fonttype"] = "path"
matplotlib.rcParams["font.family"] = "DejaVu Sans"
matplotlib.rcParams["axes.grid"] = False
matplotlib.rcParams["figure.dpi"] = 300
matplotlib.rcParams["font.size"] = 13.0
matplotlib.rcParams["axes.titleweight"] = "normal"
matplotlib.rcParams["axes.labelweight"] = "normal"

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DERIVED = os.path.join(ROOT, "manuscript", "derived")
FIGDIR = os.path.join(ROOT, "manuscript", "figures")

# Muted, colorblind-distinguishable palette plus high-contrast text shades.
CB = {
    "blue": "#4C86B3", "orange": "#D6A24A", "green": "#4C9B82",
    "vermillion": "#C97955", "purple": "#8E7DB3", "grey": "#6B737C",
    "sky": "#79AAC6", "ink": "#2F3B45", "rule": "#65717B",
}
FILL = {
    "sky": "#D9ECF5", "blue": "#CFE5F1", "green": "#D8ECE4",
    "orange": "#F5E7C8", "vermillion": "#F1DDD4",
    "purple": "#ECE7F3", "holdout": "#F5E7E0",
}

import hashlib


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _save(fig, name, meta_title, meta_desc):
    shas = {}
    svg_meta = {"Title": meta_title, "Description": meta_desc,
                "Creator": "manuscript/code/build_figures.py", "Date": None}
    png_meta = {"Title": meta_title, "Description": meta_desc,
                "Software": "manuscript/code/build_figures.py"}
    pdf_meta = {"Title": meta_title, "Subject": meta_desc,
                "Creator": "manuscript/code/build_figures.py",
                "CreationDate": None, "ModDate": None}
    svg = os.path.join(FIGDIR, name + ".svg")
    png = os.path.join(FIGDIR, name + ".png")
    pdf = os.path.join(FIGDIR, name + ".pdf")
    fig.savefig(svg, format="svg", bbox_inches="tight", pad_inches=0.10, metadata=svg_meta)
    with open(svg, encoding="utf-8") as f:
        svg_text = f.read()
    with open(svg, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n")
    fig.savefig(png, format="png", dpi=300, bbox_inches="tight", pad_inches=0.10, metadata=png_meta)
    fig.savefig(pdf, format="pdf", bbox_inches="tight", pad_inches=0.10, metadata=pdf_meta)
    plt.close(fig)
    shas[name + ".svg"] = _sha(svg)
    shas[name + ".png"] = _sha(png)
    shas[name + ".pdf"] = _sha(pdf)
    return shas


def fig_cohort_flow(D):
    cf = D["cohort_flow"]
    roles = cf["roles"]
    tr, dv, ho = roles["train"], roles["development"], roles["external_temporal_holdout"]

    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def _node(cx, cy, w, h, title, sub, face, fg):
        patch = FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor=face, edgecolor=CB["rule"], linewidth=0.9, alpha=1.0,
            mutation_aspect=1.0,
        )
        ax.add_patch(patch)
        if sub:
            ax.text(cx, cy + 0.18, title, ha="center", va="center",
                    fontsize=10.8, fontweight="normal", color=fg)
            ax.text(cx, cy - 0.20, sub, ha="center", va="center",
                    fontsize=10.5, color=fg)
        else:
            ax.text(cx, cy, title, ha="center", va="center",
                    fontsize=10.8, fontweight="normal", color=fg)

    def vfeed(x, y0, y1):
        ax.annotate("", xy=(x, y1), xytext=(x, y0),
                    arrowprops=dict(arrowstyle="-|>", color=CB["rule"], lw=1.15,
                                    shrinkA=0, shrinkB=0))

    # --- Top: source -> eligible ---
    _node(5.0, 9.10, 5.6, 1.05,
          "USGS DYFI records with M$\\geq$5",
          f"frozen snapshot: {cf['fdsn_features_pinned_snapshot']:,}",
          FILL["sky"], CB["ink"])
    vfeed(5.0, 8.57, 7.63)
    ax.text(5.24, 8.10, "eligibility:\nat least 10 felt reports",
            ha="left", va="center", fontsize=10.5, color=CB["rule"], fontweight="normal")

    _node(5.0, 7.10, 5.6, 1.05,
          f"Eligible events: {cf['n_eligible_events']:,}",
          f"{cf['sequences']['all_eligible']:,} sequences · {cf['n_eligible_severe']:,} severe",
          FILL["blue"], CB["ink"])

    # --- Distributor bus (clean orthogonal routing, no crossing) ---
    xs = [1.85, 5.0, 8.15]
    bus_y = 6.05
    ax.plot([5.0, 5.0], [6.57, bus_y], color=CB["rule"], lw=1.15)
    ax.plot([xs[0], xs[2]], [bus_y, bus_y], color=CB["rule"], lw=1.15)
    for x in xs:
        vfeed(x, bus_y, 5.55)

    # --- Role boxes ---
    rw, rcy, rh = 2.85, 5.00, 1.22
    _node(xs[0], rcy, rw, rh, "Train",
          f"{tr['n']:,} · {100 * tr['prevalence']:.1f}% severe", FILL["green"], CB["ink"])
    _node(xs[1], rcy, rw, rh, "Development",
          f"{dv['n']:,} · {100 * dv['prevalence']:.1f}% severe", FILL["orange"], CB["ink"])
    _node(xs[2], rcy, rw, rh, "Temporal holdout",
          f"{ho['n']:,} · {100 * ho['prevalence']:.1f}% severe", FILL["vermillion"], CB["ink"])

    # --- Construction pool bracket under train + dev ---
    lft, rgt, by = xs[0] - rw / 2, xs[1] + rw / 2, 4.30
    ax.plot([lft, lft, rgt, rgt], [4.47, by, by, 4.47], color=CB["purple"], lw=1.1)
    mid = (lft + rgt) / 2
    ax.plot([mid, mid], [by, 4.12], color=CB["purple"], lw=1.1)
    _node(mid, 3.60, rgt - lft, 1.00,
          f"Construction pool: {cf['construction_total']['n']:,} events",
          f"train + dev · {cf['sequences']['construction']:,} sequences",
          FILL["purple"], CB["ink"])

    # --- Holdout sequences box ---
    ax.plot([xs[2], xs[2]], [4.47, 4.12], color=CB["vermillion"], lw=1.1)
    _node(xs[2], 3.60, rw + 0.05, 1.00,
          "Holdout",
          f"{cf['sequences']['holdout']:,} sequences", FILL["holdout"], CB["ink"])

    # --- Footnotes ---
    nq = len(cf["quarantine_inspected_ids"])
    ax.text(2.75, 2.40,
            f"Prelisted quarantine IDs: {nq}\nabsent from frozen snapshot",
            ha="center", va="center", fontsize=10.5, color=CB["rule"])
    ax.text(7.25, 2.40,
            f"Straddle events: {cf['temporal_straddle_excluded']}\nincluded in eligible cohort",
            ha="center", va="center", fontsize=10.5, color=CB["rule"])
    accounting = FancyBboxPatch(
        (2.0, 1.48), 6.0, 0.62,
        boxstyle="round,pad=0.02,rounding_size=0.10",
        facecolor="#F7F8F9", edgecolor="#AAB2B8", linewidth=0.7,
    )
    ax.add_patch(accounting)
    ax.text(5.0, 1.79,
            f"Role counts:  {tr['n']:,} + {dv['n']:,} + {ho['n']:,} + "
            f"{cf['temporal_straddle_excluded']} = {cf['n_eligible_events']:,} eligible events",
            ha="center", va="center", fontsize=10.5, color=CB["ink"], fontweight="normal")

    return _save(fig, "fig_cohort_flow",
                 "Cohort construction and role assignment flow",
                 "Flow diagram: frozen USGS DYFI records to eligible events to train, development, and holdout roles with counts and severe-event rates.")


def fig_baseline_scores(D):
    pb = D["per_baseline"]
    order = ["B0_no_skill", "B1_magnitude_only_logit", "B2_source_only_logit", "B4_random_forest", "B5_xgboost"]
    labels = [
        "B0  No-skill",
        "B1  Magnitude-only logistic",
        "B2  Source-only logistic",
        "B4  Random forest",
        "B5  XGBoost",
    ]
    briers = [pb[b]["brier"] for b in order]
    ci_lo = [pb[b]["brier_ci"][0] for b in order]
    ci_hi = [pb[b]["brier_ci"][1] for b in order]
    err_lo = [briers[i] - ci_lo[i] for i in range(len(order))]
    err_hi = [ci_hi[i] - briers[i] for i in range(len(order))]

    # A horizontal interval plot remains legible when scaled to journal width
    # and avoids the visual weight and label crowding of a multi-panel bar chart.
    fig, ax = plt.subplots(figsize=(8.6, 4.1))
    y = list(reversed(range(len(order))))
    colors = [CB["grey"], CB["blue"], CB["green"], CB["orange"], CB["vermillion"]]
    for i, (yy, value, lo, hi, color) in enumerate(zip(y, briers, ci_lo, ci_hi, colors)):
        ax.errorbar(
            value, yy, xerr=[[err_lo[i]], [err_hi[i]]], fmt="o",
            markersize=7.5, capsize=4, color=color, ecolor=color,
            markeredgecolor=CB["ink"], markeredgewidth=0.7, elinewidth=1.7, zorder=3,
        )
        ax.text(hi + 0.004, yy, f"{value:.3f}  [{lo:.3f}, {hi:.3f}]",
                ha="left", va="center", fontsize=11.2, fontweight="normal")
    ax.axvline(pb["B0_no_skill"]["brier"], color=CB["grey"], linestyle="--",
               linewidth=1.3, alpha=0.8, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11.2)
    ax.set_xlabel("Brier score (lower is better)", fontsize=11.5)
    ax.set_xlim(min(ci_lo) - 0.012, max(ci_hi) + 0.047)
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_title("Baseline performance on the temporal holdout (95% CI)",
                 fontsize=11.5, pad=8)
    ax.grid(axis="x", linestyle=":", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return _save(fig, "fig_baseline_scores",
                 "Baseline Brier scores with uncertainty",
                 "Brier score and 95 percent sequence-cluster bootstrap confidence interval for each baseline on the temporal holdout. Lower values are better.")


def fig_leakage_split(D):
    lk = D["leakage_inflation_headline"]
    ps = lk["per_scheme"]
    schemes = ["random_event", "event_grouped", "sequence_grouped"]
    labels = ["Random\n(naive)", "Event\n(control)", "Sequence\n(primary)"]
    brier = [ps[s]["brier"] for s in schemes]
    auroc = [ps[s]["auroc"] for s in schemes]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.0), constrained_layout=True)
    fig.set_constrained_layout_pads(wspace=0.08)
    x = list(range(3))
    colors = [CB["vermillion"], CB["orange"], CB["green"]]

    bars1 = ax1.bar(x, brier, color=colors, edgecolor=CB["rule"], linewidth=0.7, alpha=0.82)
    for bar, hatch in zip(bars1, ("///", "...", "xxx")):
        bar.set_hatch(hatch)
    ax1.axhline(brier[0], color=CB["vermillion"], linestyle="--", linewidth=0.9, alpha=0.7)
    for i, v in enumerate(brier):
        ax1.text(i, v + 0.0018, f"{v:.3f}", ha="center", va="bottom", fontsize=13.0, fontweight="normal")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=13.0, fontweight="normal")
    ax1.set_ylabel("Brier score (lower is better)", fontsize=13.5)
    ax1.set_ylim(min(brier) - 0.012, max(brier) + 0.016)
    ax1.set_title(f"(a) Brier difference: sequence $-$ random = {lk['brier_inflation_seq_minus_random']:+.4f}", fontsize=13.0, pad=7)
    ax1.grid(axis="y", linestyle=":", alpha=0.22)

    bars2 = ax2.bar(x, auroc, color=colors, edgecolor=CB["rule"], linewidth=0.7, alpha=0.82)
    for bar, hatch in zip(bars2, ("///", "...", "xxx")):
        bar.set_hatch(hatch)
    ax2.axhline(auroc[0], color=CB["vermillion"], linestyle="--", linewidth=0.9, alpha=0.7)
    for i, v in enumerate(auroc):
        ax2.text(i, v + 0.0015, f"{v:.3f}", ha="center", va="bottom", fontsize=13.0, fontweight="normal")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=13.0, fontweight="normal")
    ax2.set_ylabel("AUROC (higher is better)", fontsize=13.5)
    ax2.set_ylim(min(auroc) - 0.012, max(auroc) + 0.016)
    ax2.set_title(f"(b) AUROC difference: random $-$ sequence = {lk['auroc_inflation_random_minus_seq']:+.4f}", fontsize=13.0, pad=7)
    ax2.grid(axis="y", linestyle=":", alpha=0.22)

    return _save(fig, "fig_leakage_split",
                 "Leakage inflation across split schemes",
                 "Brier and AUROC of a fixed diagnostic model under random, event-grouped, and sequence-grouped cross-validation; the observed differences are small and reported descriptively.")


def fig_threshold_slice(D):
    ts = D["endpoint"]["threshold_sensitivity"]
    thr = [5.5, 6.0, 6.5]
    brier = [ts[f"{t}"]["brier"] for t in thr]
    auroc = [ts[f"{t}"]["auroc"] for t in thr]
    prev = [ts[f"{t}"]["prevalence"] for t in thr]

    tslice = D["slices"]["temporal"]
    years = sorted(tslice)
    yb = [tslice[y]["brier"] for y in years]
    ya = [tslice[y].get("auroc") for y in years]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.0, 4.0), constrained_layout=True)
    ax1.plot(thr, brier, "-o", color=CB["blue"], label="Brier", linewidth=1.8, markersize=7)
    ax1.plot(thr, auroc, "-s", color=CB["green"], label="AUROC", linewidth=1.8, markersize=7)
    ax1.plot(thr, prev, "--^", color=CB["grey"], label="Prevalence", linewidth=1.4, markersize=6.5)
    for t, b in zip(thr, brier):
        dx = -0.04 if t == 6.0 else 0.0
        ax1.text(t + dx, b + 0.016, f"{b:.3f}",
                 ha=("right" if t == 6.0 else "center"),
                 fontsize=13.0, fontweight="normal")
    for t, a in zip(thr, auroc):
        dx = 0.04 if t == 6.0 else 0.0
        ax1.text(t + dx, a + 0.016, f"{a:.3f}",
                 ha=("left" if t == 6.0 else "center"),
                 fontsize=13.0, fontweight="normal")
    for t, p in zip(thr, prev):
        dx = -0.04 if t == 6.0 else 0.0
        ax1.text(t + dx, p - 0.040, f"{p:.3f}",
                 ha=("right" if t == 6.0 else "center"),
                 fontsize=13.0, color=CB["grey"], fontweight="normal")

    ax1.set_ylim(0.08, 0.92)
    ax1.axvline(6.0, color=CB["vermillion"], linestyle=":", linewidth=1.2)
    ax1.text(6.0, 0.88, "protocol-defined cutoff (6.0)", color=CB["vermillion"], fontsize=13.0,
             fontweight="normal", ha="center",
             bbox=dict(boxstyle="round,pad=0.25", facecolor=FILL["vermillion"], edgecolor=CB["vermillion"], alpha=0.9))
    ax1.set_xlabel("Severe cutoff (maximum CDI)", fontsize=13.5)
    ax1.set_ylabel("Metric value", fontsize=13.5)
    ax1.set_xticks(thr)
    ax1.set_xticklabels([f"{t:.1f}" for t in thr], fontsize=13.0)
    ax1.set_title("(a) Sensitivity to the severe-intensity cutoff", fontsize=13.0, pad=7)
    ax1.legend(fontsize=13.0, loc="center right", framealpha=0.95, edgecolor="0.6")
    ax1.grid(True, linestyle=":", alpha=0.22)

    x = list(range(len(years)))
    width = 0.36
    ax2.bar([i - width / 2 for i in x], yb, width, color=CB["blue"],
            edgecolor=CB["rule"], linewidth=0.7, hatch="//", alpha=0.82, label="Brier")
    ax2.bar([i + width / 2 for i in x], ya, width, color=CB["green"],
            edgecolor=CB["rule"], linewidth=0.7, hatch="..", alpha=0.82, label="AUROC")
    for i in x:
        ax2.text(i - width / 2, yb[i] + 0.015, f"{yb[i]:.3f}", ha="center", fontsize=13.0, fontweight="normal")
        ax2.text(i + width / 2, ya[i] + 0.015, f"{ya[i]:.3f}", ha="center", fontsize=13.0, fontweight="normal")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{y}\n({tslice[y]['n']} events)" for y in years], fontsize=13.0, fontweight="normal")
    ax2.set_ylabel("Metric value", fontsize=13.5)
    ax2.set_ylim(0, 1.08)
    ax2.set_title("(b) Performance by holdout year", fontsize=13.0, pad=7)
    ax2.legend(fontsize=13.0, loc="upper center", framealpha=0.95, edgecolor="0.6")
    ax2.grid(axis="y", linestyle=":", alpha=0.22)

    return _save(fig, "fig_threshold_slice",
                 "Threshold and temporal-slice sensitivity",
                 "Left: probe Brier, AUROC, and prevalence across maxCDI thresholds 5.5/6.0/6.5. Right: probe Brier and AUROC in the two holdout years.")


def build():
    with open(os.path.join(DERIVED, "asset_inputs.json")) as f:
        D = json.load(f)
    os.makedirs(FIGDIR, exist_ok=True)
    shas = {}
    shas.update(fig_cohort_flow(D))
    shas.update(fig_baseline_scores(D))
    shas.update(fig_leakage_split(D))
    shas.update(fig_threshold_slice(D))
    return shas


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
