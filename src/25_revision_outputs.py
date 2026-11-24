"""Figures and manuscript-ready supplementary tables for RS-D29 to RS-D33 (from existing outputs).

Figures (outputs/figures/supplementary/, PDF, 300-dpi PNG and <name>_data.csv; RS-D28 lettering
audit and the plain-text check of figstyle.audit):
- sfig_like_for_like: gross gains, gross losses and net excess (S1 bars, robust part hatched; S2
  diamonds) for RES_TOTAL, RES_INT, TER_INT and TER_TOT, in the style of fig_principles.
- sfig_container_event: container ships, pre-crisis gamma_h with 95% intervals (RS-D30 (a)1) and
  the monthly S1 excess % from 2023-12 (RS-D2 main run, fig_world_container_data.csv).

Tables: outputs/manuscript_tables/supplementary/stab_rev_*.csv (full precision), notes in
outputs/manuscript_tables/table_notes_revision.md and outputs/figures/figure_notes_revision.md.
Existing figures, tables and notes are not rewritten.

Checks: outputs/checks/revision_checks.csv (rows starting with 'revfig_' and 'revtab_').
"""

import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import config as C
import figstyle as fs
from common import rel, update_checks

T = C.OUTPUTS / "tables"
SUPP_TABLES = C.OUTPUTS / "manuscript_tables" / "supplementary"
MT = 1e6
CHECKS_FILE = C.CHECKS / "revision_checks.csv"
SERIES = ["RES_TOTAL", "RES_INT", "TER_INT", "TER_TOT"]
SERIES_LABEL = {"RES_TOTAL": "Residence,\nall voyages", "RES_INT": "Residence,\ninternational",
                "TER_INT": "Departure,\ninternational", "TER_TOT": "Departure,\nall voyages"}
CHECKS, FIG_NOTES, TAB_NOTES = [], {}, []


def check(name, definition, expected, obtained, ok):
    CHECKS.append({"check": name, "definition": definition, "expected": str(expected), "obtained": str(obtained),
                   "abs_diff": "", "pass": bool(ok)})


def check_close(name, definition, a, b, tol=1e-9):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    diff = float(np.nanmax(np.abs(a - b))) if a.size else 0.0
    ok = diff <= tol and np.array_equal(np.isnan(a), np.isnan(b))
    CHECKS.append({"check": name, "definition": definition + f" (max |diff| <= {tol:g})", "expected": "agree",
                   "obtained": f"max |diff| = {diff:.3g}", "abs_diff": f"{diff:.3g}", "pass": bool(ok)})


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def units_of(series):
    if series == "RES_TOTAL":
        return pd.read_csv(T / "rsd4_residence_units.csv")
    if series == "TER_INT":
        return pd.read_csv(T / "rsd4_departure_units.csv")
    u = pd.read_csv(T / "like_for_like_units.csv")
    return u[u["series"] == series].drop(columns="series")


def sfig_like_for_like():
    name = "sfig_like_for_like"
    s = pd.read_csv(T / "like_for_like_summary.csv").set_index("series")
    rows = []
    for ser in SERIES:
        u = units_of(ser)
        nc = u[~u["control"].astype(bool)]
        rob = nc["robust"].astype(bool)
        for spec in ("S1", "S2"):
            e = nc[f"excess_total_t_{spec}"]
            rows.append({"series": ser, "spec": spec, "gross_gains_Mt": e[e > 0].sum() / MT,
                         "gross_losses_Mt": e[e < 0].sum() / MT, "net_Mt": e.sum() / MT,
                         "robust_gains_Mt": e[(e > 0) & rob].sum() / MT, "robust_losses_Mt": e[(e < 0) & rob].sum() / MT})
    d = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(fs.FULL, 85 * fs.MM))
    xs, labels = [], []
    for i, ser in enumerate(SERIES):
        r1 = d[(d["series"] == ser) & (d["spec"] == "S1")].iloc[0]
        r2 = d[(d["series"] == ser) & (d["spec"] == "S2")].iloc[0]
        base = i * 4
        for k, (col, rcol, colour) in enumerate((("gross_gains_Mt", "robust_gains_Mt", fs.OI["blue"]),
                                                  ("gross_losses_Mt", "robust_losses_Mt", fs.OI["vermillion"]),
                                                  ("net_Mt", None, fs.OI["black"]))):
            x = base + k
            ax.bar(x, r1[col], width=0.7, color=colour, alpha=0.35 if rcol else 0.8, edgecolor=colour, lw=0.6)
            if rcol:
                ax.bar(x, r1[rcol], width=0.7, color="none", edgecolor=colour, hatch="////", lw=0.6)
            ax.plot(x, r2[col], ls="none", marker="D", ms=3.5, color=fs.OI["black"], mfc="white", mew=0.8)
            xs.append(x)
            labels.append(["Gains", "Losses", "Net"][k])
        ax.text(base + 1, 1.02, SERIES_LABEL[ser], transform=ax.get_xaxis_transform(), ha="center", va="bottom")
    ax.axhline(0, color=fs.OI["black"], lw=0.6)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_ylabel(f"Excess, December 2023 to\nOctober 2025 (Mt {fs.CO2})")
    handles = [Patch(facecolor=fs.OI["grey"], alpha=0.35, edgecolor=fs.OI["grey"], label="S1, all economies"),
               Patch(facecolor="none", edgecolor=fs.OI["grey"], hatch="////", label="S1, robust economies"),
               Line2D([], [], ls="none", marker="D", ms=3.5, color=fs.OI["black"], mfc="white", label="S2")]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 7 / 85, 1, 0.93))
    paths = fs.save(fig, name, d, supplementary=True)
    back = pd.read_csv(paths[2]).set_index(["series", "spec"])
    b1 = back.xs("S1", level="spec").loc[SERIES]
    for col, scol in (("gross_gains_Mt", "gross_gains_all_Mt"), ("gross_losses_Mt", "gross_losses_all_Mt"),
                      ("robust_gains_Mt", "gross_gains_robust_Mt"), ("robust_losses_Mt", "gross_losses_robust_Mt"),
                      ("net_Mt", "excess_Mt_S1")):
        check_close(f"revfig_{name}_{col}", f"{name}: S1 {col} equals like_for_like_summary.csv {scol}", b1[col],
                    s.loc[SERIES, scol], tol=1e-6)
    b2 = back.xs("S2", level="spec").loc[SERIES]
    check_close(f"revfig_{name}_net_S2", f"{name}: S2 net equals like_for_like_summary.csv excess_Mt_S2", b2["net_Mt"],
                s.loc[SERIES, "excess_Mt_S2"], tol=1e-6)
    ref = pd.read_csv(T / "rsd4_summary.csv").set_index(["principle", "spec"])
    for ser, pr in (("RES_TOTAL", "residence"), ("TER_INT", "departure")):
        for spec in ("S1", "S2"):
            for col, scol in (("gross_gains_Mt", "gross_gains_all_Mt"), ("gross_losses_Mt", "gross_losses_all_Mt")):
                check_close(f"revfig_{name}_{ser}_{spec}_{col}", f"{name}: {ser} {spec} {col} equals rsd4_summary.csv",
                            [back.loc[(ser, spec), col]], [ref.loc[(pr, spec), scol]], tol=1e-6)
    FIG_NOTES[name] = dict(
        data=paths[2], sources="outputs/tables/like_for_like_units.csv, like_for_like_summary.csv (RES_INT, TER_TOT); "
        "outputs/tables/rsd4_residence_units.csv, rsd4_departure_units.csv (RES_TOTAL, TER_INT)",
        specification="RS-D29; main estimates of each series, window 2023-12..2025-10; bars S1, diamonds S2.",
        definitions="Panels from left: residence, all voyages (RES_TOTAL = A+B+D+E+F); residence, international voyages "
        "(RES_INT = D+E+F); departure, international voyages (TER_INT); departure, all voyages (TER_TOT = TER_DOM + "
        "TER_INT, domestic voyages counted in the economy where they take place). Gross gains = sum of positive economy "
        "totals; gross losses = sum of negative economy totals (non-control economies); net = total excess. Hatched part "
        "= contribution of the economies robust under RS-D16 in that series (S1).")
    return paths


def sfig_container_event():
    name = "sfig_container_event"
    a = pd.read_csv(T / "pretrend_aggregate.csv")
    a = a[(a["test"] == "container") & (a["row"] == "h")].sort_values("period")
    j = pd.read_csv(T / "pretrend_aggregate.csv")
    j = j[(j["test"] == "container") & (j["row"] == "joint")].iloc[0]
    cm = pd.read_csv(T / "container_monthly.csv")
    cm = cm[cm["row"] == "month"].sort_values("period")
    d = pd.concat([
        pd.DataFrame({"period": a["period"], "part": "pre-crisis difference (RS-D30 a1)", "pct": a["pct"],
                      "ci95_lo_pct": a["ci95_lo_pct"], "ci95_hi_pct": a["ci95_hi_pct"]}),
        pd.DataFrame({"period": cm["period"], "part": "excess S1 (RS-D2 main run)", "pct": cm["pct_S1"],
                      "ci95_lo_pct": np.nan, "ci95_hi_pct": np.nan})], ignore_index=True)
    fig, ax = plt.subplots(figsize=(fs.FULL, 80 * fs.MM))
    pre = d[d["part"].str.startswith("pre")]
    post = d[d["part"].str.startswith("excess")]
    xp, xq = fs.to_dt(pre["period"]), fs.to_dt(post["period"])
    ax.axhline(0, color=fs.OI["grey"], lw=0.6, zorder=0)
    ax.errorbar(xp, pre["pct"], yerr=[pre["pct"] - pre["ci95_lo_pct"], pre["ci95_hi_pct"] - pre["pct"]], fmt="o",
                ms=3.5, color=fs.OI["blue"], ecolor=fs.OI["blue"], elinewidth=0.8, capsize=0,
                label="Before the crisis: difference from the fitted path, container ships against the "
                      "eight non-transit types (95% interval)")
    ax.plot(xq, post["pct"], color=fs.OI["vermillion"], lw=1.0, marker="o", ms=3.0,
            label="From December 2023: excess of container ships, S1 (% of counterfactual)")
    fs.shock_line(ax)
    ax.xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator(bymonth=(1, 7)))
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b %Y"))
    ax.set_ylabel("Difference or excess\n(% of the fitted or counterfactual value)")
    handles, labels = ax.get_legend_handles_labels()
    order = sorted(range(len(labels)), key=lambda i: not labels[i].startswith("Before"))
    fig.legend([handles[i] for i in order], [labels[i] for i in order], loc="lower center", ncol=1,
               bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.17, 1, 1))
    paths = fs.save(fig, name, d, supplementary=True)
    back = pd.read_csv(paths[2])
    bp = back[back["part"].str.startswith("pre")].sort_values("period")
    for c in ("pct", "ci95_lo_pct", "ci95_hi_pct"):
        check_close(f"revfig_{name}_{c}", f"{name}: pre-crisis {c} equals pretrend_aggregate.csv (container)",
                    bp[c], a[c])
    bq = back[back["part"].str.startswith("excess")].sort_values("period")
    check_close(f"revfig_{name}_excess", f"{name}: monthly S1 % equals container_monthly.csv", bq["pct"], cm["pct_S1"])
    w = pd.read_csv(C.OUTPUTS / "figures" / "fig_world_container_data.csv")
    w = w[w["period"] >= C.SHOCK_START].sort_values("period")
    check_close(f"revfig_{name}_excess_source", f"{name}: monthly S1 % equals (observed / S1 - 1) x 100 from "
                "fig_world_container_data.csv", bq["pct"],
                100 * (w["observed_kt_per_day"] / w["s1_kt_per_day"] - 1), tol=1e-9)
    check(f"revfig_{name}_n", f"{name}: points (12 pre-crisis months, 23 crisis months)", "12; 23",
          f"{len(bp)}; {len(bq)}", len(bp) == 12 and len(bq) == 23)
    FIG_NOTES[name] = dict(
        data=paths[2], sources="outputs/tables/pretrend_aggregate.csv (test container); outputs/tables/"
        "container_monthly.csv (from outputs/figures/fig_world_container_data.csv)",
        specification="Pre-crisis points: RS-D30 (a)1, S1 model on untreated observations, CONTAINER treated, the eight "
        "non-transit types as controls, W_h for h = 1..12 (2022-12..2023-11), RS-D15 weights. Crisis months: RS-D2 main "
        "run (W0), S1.",
        definitions="Pre-crisis points: exp(gamma_h) - 1 in %, with 95% intervals exp(gamma_h +- 1.96 se) - 1, se "
        f"cluster-robust by ship type ({int(j['n_clusters'])} clusters; the covariance of the 12 terms has rank "
        f"{int(j['rank_V'])}, so the joint Wald test uses its Moore-Penrose inverse). Crisis months: (observed - S1 "
        "counterfactual) / S1 counterfactual x 100. The two parts come from different samples (pre-crisis: CONTAINER and "
        "eight non-transit types; crisis months: the main run with ten transit types treated).")
    return paths


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
STAB = [
    ("like_for_like_summary", "T", "RS-D29 like-for-like comparison: panel and pool sizes, totals S1/S2 (Mt, %), "
     "placebo band, gross gains and losses (S1, all and robust), robust list, for RES_TOTAL and TER_INT (reference rows "
     "read from the main outputs) and RES_INT and TER_TOT (estimated)."),
    ("like_for_like_units", "T", "RS-D29: all economy results for RES_INT and TER_TOT (columns as the main units files)."),
    ("like_for_like_pairs", "T", "RS-D29: S1 % side by side for economies in both series of a pair (RES_INT vs TER_INT; "
     "RES_TOTAL vs TER_TOT)."),
    ("like_for_like_pairs_summary", "T", "RS-D29: per pair, economies in both, correlations of S1 % over economies that "
     "are non-control in both, robust overlaps and the five largest differences."),
    ("like_for_like_exposure", "K", "RS-D29: exposure (e_int, x_tot), Panama share, international share and control "
     "pool per economy of the RES_INT and TER_TOT panels."),
    ("pretrend_aggregate", "T", "RS-D30 (a): gamma_h as % with 95% intervals and the cluster-robust Wald test (chi-squared "
     "and F forms), for container ships, the ten cargo types, residence and departure economies."),
    ("pretrend_units", "T", "RS-D30 (b): per-unit pre-trend test over the last 12 pre-crisis months (departure 11), "
     "Newey-West (3 lags) standard errors, flag = p < 0.05."),
    ("rolling_placebo_units", "T", "RS-D31: equal-length rule (max |placebo %| over the rolling runs, robust flag) and "
     "unit p-values (sigma, z, p per specification, p_u, sign agreement, BH candidate) for the non-control economies "
     "of RES_TOTAL, TER_INT and RES_INT."),
    ("rolling_placebo_system", "T", "RS-D31: equal-length rule for ship types and totals (world main run and B1) and for "
     "the economy totals."),
    ("rolling_placebo_bh", "T", "RS-D31: Benjamini-Hochberg candidates (q = 0.10) with the expected number of false "
     "discoveries, null sizes, and equal-length robust lists against the RS-D16 lists."),
    ("rolling_placebo_gross", "T", "RS-D32: gross gains and losses (S1) as % of the summed counterfactual, per rolling "
     "placebo date and actual, with the placebo maxima and the rank of the actual value."),
    ("revision_variants_economies", "T", "RS-D33: R15 (2024-01..2025-10 re-sum of R0) and R16 (stricter control pools), "
     "both principles, S1 and S2: totals, placebo bands, robust lists and changes against R0, pool members."),
    ("revision_variants_units", "T", "RS-D33: per-economy results of R15 and R16."),
    ("revision_variants_world", "T", "RS-D33: W5 (2024-01..2025-10 re-sum of W0), main run and B1, totals and ship types, "
     "robust flags against the W0 placebo maxima."),
    ("rq3_leave_one_out", "T", "RS-D33: RQ3 weighted regressions (S1, S2) with each RSL economy left out in turn: RSL "
     "coefficient, HC3 standard error and 95% interval. Descriptive."),
    ("ppml_world", "T", "RS-D33: PPML at system level, main run and B1, S1 and S2: totals, placebo band, robust flags."),
    ("ppml_world_types", "T", "RS-D33: PPML per treated ship type with the 10 placebo % and the RS-D16 rule."),
    ("ppml_simulation", "T", "RS-D33: PPML on simulated panels with no effect (one noise-free panel; 50 panels with "
     "multiplicative noise, sd 0.05)."),
    ("container_monthly", "T", "RS-D33: monthly container excess (Mt, %), S1 and S2, 2023-12..2025-10, and means for "
     "2023-12..2024-07 and 2024-08..2025-10."),
]


def tables():
    for name, where, note in STAB:
        src = (T if where == "T" else C.CHECKS) / f"{name}.csv"
        df = pd.read_csv(src, keep_default_na=False, dtype=str)
        out = SUPP_TABLES / f"stab_rev_{name}.csv"
        df.to_csv(out, index=False)
        same = pd.read_csv(out, keep_default_na=False, dtype=str).equals(df)
        check(f"revtab_{name}", f"stab_rev_{name}.csv: same cells as {rel(src)}", "identical", f"{len(df)} rows",
              same)
        TAB_NOTES.append((f"stab_rev_{name}", len(df), note + f" Source: {rel(src)}."))
        print(f"{rel(out)}: {len(df)} rows")


def write_notes():
    lines = ["# Table notes: analyses added after the pre-submission review (RS-D29 to RS-D33)", "",
             "Supplementary tables prefixed `stab_rev_`; final numbers are assigned when the text is written. Values at "
             "full precision. Excess is in Mt CO2 over 2023-12..2025-10 unless stated.", ""]
    lines += [f"- `{n}.csv` ({k} rows): {note}" for n, k, note in TAB_NOTES]
    lines += ["", "## Additions to existing tables", "",
              "- `tab_system.csv`: the S2 rows of container ships (main run and B1) now hold the yearly excess "
              "(2023 = December, 2024, 2025 = January-October) from the W0 S2 estimates in "
              "`outputs/tables/robustness_world_container.csv` (src/13_robustness_world.py); the yearly sums add up to "
              "the window total. No other cell changed.",
              "- `supplementary/stab_robustness_world.csv`: new column `container_max_abs_placebo_pct`, the maximum "
              "|placebo %| of container ships over the placebo runs of each estimated variant (W0, W1: 10 runs; W2: 4 "
              "runs), from `outputs/tables/robustness_world_container.csv`. Empty for W3 and W4, which re-sum W0 and "
              "have no placebo runs of their own. No other cell changed.", ""]
    (C.OUTPUTS / "manuscript_tables" / "table_notes_revision.md").write_text("\n".join(lines), encoding="utf-8")
    fl = ["# Figure notes: analyses added after the pre-submission review (RS-D29 to RS-D33)", "",
          "Each figure is saved as PDF (vector) and PNG (300 dpi), with a data file holding the plotted numbers. The "
          "dashed vertical line on time axes marks 2023-12, the first crisis month.", "",
          "No separate figure of the container monthly path (RS-D33): its S1 % is drawn in sfig_container_event; the "
          "numbers are in outputs/tables/container_monthly.csv.", ""]
    for name, n in FIG_NOTES.items():
        fl += [f"### {name}", "", f"- Files: `outputs/figures/supplementary/{name}.pdf`, "
               f"`outputs/figures/supplementary/{name}.png`", f"- Data file: `{rel(n['data'])}`",
               f"- Source tables: {n['sources']}", f"- Specification: {n['specification']}",
               f"- Definitions: {n['definitions']}", ""]
    (fs.FIG_DIR / "figure_notes_revision.md").write_text("\n".join(fl), encoding="utf-8")


def main():
    t0 = time.perf_counter()
    fs.setup()
    for f in (sfig_like_for_like, sfig_container_event):
        p = f()
        print(f"{f.__name__}: {rel(p[0])}")
    for name, a in fs.AUDIT.items():
        check(f"revfig_{name}_min_font", f"{name}: smallest rendered font size of any text, pt", f">= {fs.MIN_FONT:.1f}",
              f"{a['min_font']:.1f}", a["min_font"] >= fs.MIN_FONT)
        check(f"revfig_{name}_text_inside", f"{name}: texts drawn wholly inside the figure (of {a['n_texts']} texts)", 0,
              len(a["outside"]), not a["outside"])
        check(f"revfig_{name}_text_overlap", f"{name}: pairs of overlapping text boxes", 0, len(a["overlaps"]),
              not a["overlaps"])
        check(f"revfig_{name}_plain_text", f"{name}: drawn texts containing an underscore, RS-D, RQ followed by a digit "
              "or a date written as YYYY-MM", 0, len(a["codes"]), not a["codes"])
        if a["outside"] or a["overlaps"] or a["codes"]:
            print(f"{name}: outside {a['outside']}; overlaps {a['overlaps']}; codes {a['codes']}")
    SUPP_TABLES.mkdir(parents=True, exist_ok=True)
    tables()
    write_notes()
    update_checks([c for c in CHECKS if c["check"].startswith("revfig_")], CHECKS_FILE, "revfig_")
    update_checks([c for c in CHECKS if c["check"].startswith("revtab_")], CHECKS_FILE, "revtab_")
    print(f"Run time {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
