"""Figures of RS-D22 from the existing outputs (no estimate changes).

Main figures (outputs/figures/) and supplementary figures (outputs/figures/supplementary/),
each as PDF and 300-dpi PNG with a data file <name>_data.csv holding the plotted numbers.
Counterfactual paths are re-computed with 09_imputation (same data and specification as the
main tables); the figure checks confirm that they reproduce the tabulated excess.

Outputs
- outputs/figures/*.pdf|png|_data.csv, outputs/figures/supplementary/*
- outputs/figures/figure_notes.md
- outputs/checks/figure_checks.csv
"""

import importlib
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import config as C
import figstyle as fs
from common import months, rel, write_checks

imp = importlib.import_module("09_imputation")
m10 = importlib.import_module("10_rsd4_economies")
m11 = importlib.import_module("11_rsd2_world")

T = C.OUTPUTS / "tables"
MT, KT = 1e6, 1e3
WINDOW = months(C.PRE_START, C.MAIN_END)
PATH_START = "2021-01"
DEP_PATH_ORDER = ["EGY", "SAU", "MYS", "ESP", "IND", "LKA", "MUS", "LBN", "AZE"]
ROB_DEP_KEYS = ["EGY", "SAU", "MYS", "ESP", "IND", "LKA", "MUS"]

# Readable axis labels for the OECD ship-type codes (sfig_world_types; the data file keeps the codes)
TYPE_LABELS = {"CONTAINER": "Container ships", "VEHICLE": "Vehicle carriers", "BULK_CARRIER": "Bulk carriers",
               "OIL_TANKER": "Oil tankers", "CHEM_TANKER": "Chemical tankers",
               "LIQ_GAS_TANKER": "Liquefied-gas tankers", "RO_RO": "Ro-ro ships", "GEN_CARGO": "General cargo ships",
               "OTHER_LIQ_TANKER": "Other liquids tankers", "REFRIG_BULK": "Refrigerated bulk carriers"}

# Within-EEA scatter: economies always labelled, and the |S1 %| threshold for labelling any other point
EEA_ALWAYS_LABEL = ["ESP", "GRC", "FRA"]
EEA_LABEL_PCT = 20

# Point labels (place_labels): a label next to its point must be at least this much (points) nearer
# to its own marker than to any other marker
NEAR_MARGIN = 3.0
# Sentence added to the notes of figures whose labels may use leader lines
LEADER_NOTE = "Where a label cannot sit next to its point, a thin grey line joins them."

NOTES = {}
CHECKS = []
FILES = []


def note(name, supplementary, **kw):
    NOTES[name] = {"supplementary": supplementary, **kw}


def check(name, desc, expected, obtained, ok):
    CHECKS.append({"check": name, "definition": desc, "expected": str(expected), "obtained": str(obtained),
                   "abs_diff": "", "pass": bool(ok)})


def check_close(name, desc, a, b, tol=1e-6):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    diff = float(np.nanmax(np.abs(a - b))) if a.size else 0.0
    same_nan = bool(np.array_equal(np.isnan(a), np.isnan(b)))
    CHECKS.append({"check": name, "definition": desc + f" (max |diff| <= {tol:g})", "expected": "agree",
                   "obtained": f"max |diff| = {diff:.3g}", "abs_diff": f"{diff:.3g}",
                   "pass": bool(diff <= tol and same_nan)})


def reread(paths):
    return pd.read_csv(paths[2])


def place_labels(fig, ax, pts, labels, markers, fontsize=fs.FONT, marker_r=3.0, own_r=None, obstacles=(),
                 lines=(), rings=(0.0, 8.0, 16.0, 24.0, 32.0, 40.0)):
    """Annotate points with labels, avoiding overlaps (deterministic greedy placement).

    pts: (x, y) data coordinates of the points to label, in order; markers: (x, y) of every
    marker drawn; marker_r: their radius in points (scalar or one per marker); own_r: radius of
    each labelled point's own marker (default marker_r), from which the label offset starts;
    obstacles: artists (e.g. the legend) whose boxes labels must avoid; lines: (x, y) points
    sampled along lines that labels must not cover; rings: extra distances (points) of
    successive rings of eight candidate offsets around the point (right, upper right, lower
    right, left, upper left, lower left, above, below).

    A candidate is accepted when its rendered text box stays inside the axes and overlaps no
    placed label, obstacle, line or other marker (lines with a clearance of 1 point). On the first
    ring the box must also lie nearer to the edge of its own marker than to the edge of any other
    marker, by at least NEAR_MARGIN points, so that the label cannot be read as belonging to a
    neighbour. Beyond the first ring
    the label gets a thin leader line to its point, which must not pass through another marker.
    The first accepted candidate is used (if none, the first candidate). Labels are placed in
    decreasing order of their own marker size, ties in the given order. Call after the layout is
    final.
    """
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    to_pt = 72.0 / fig.dpi
    disp = lambda xy: np.asarray(ax.transData.transform(np.asarray(xy, dtype=float))) * to_pt
    mk = disp(markers).reshape(-1, 2)
    ln = disp(list(lines)).reshape(-1, 2) if len(lines) else np.empty((0, 2))
    mr = np.broadcast_to(np.asarray(marker_r, dtype=float), (len(mk),))
    own = np.broadcast_to(np.asarray(marker_r if own_r is None else own_r, dtype=float), (len(pts),))
    axb = ax.get_window_extent(r)
    ax_box = (axb.x0 * to_pt, axb.y0 * to_pt, axb.x1 * to_pt, axb.y1 * to_pt)
    placed = []
    for o in obstacles:
        b = o.get_window_extent(r)
        placed.append((b.x0 * to_pt, b.y0 * to_pt, b.x1 * to_pt, b.y1 * to_pt))

    def box_dist(pt, box):
        """Distance from points (n x 2) to a box; 0 inside."""
        ddx = np.maximum.reduce([box[0] - pt[:, 0], np.zeros(len(pt)), pt[:, 0] - box[2]])
        ddy = np.maximum.reduce([box[1] - pt[:, 1], np.zeros(len(pt)), pt[:, 1] - box[3]])
        return np.hypot(ddx, ddy)

    def seg_dist(pt, a, b):
        """Distance from points (n x 2) to the segment a-b."""
        ab = b - a
        t = np.clip(((pt - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
        return np.hypot(*(pt - (a + t[:, None] * ab)).T)

    # labels of larger markers first (ties in the given order), as they have fewer free positions
    order = sorted(range(len(pts)), key=lambda i: (-own[i], i))
    for x, y, text, g in [(pts[i][0], pts[i][1], labels[i], own[i]) for i in order]:
        p = disp((x, y))
        ext = plt.Text(0, 0, text, fontsize=fontsize, figure=fig).get_window_extent(r)
        w, h = ext.width * to_pt, ext.height * to_pt
        def text_box(dx, dy, ha, va):
            x0 = p[0] + dx - (w if ha == "right" else w / 2 if ha == "center" else 0)
            y0 = p[1] + dy - (h if va == "top" else h / 2 if va == "center" else 0)
            return (x0, y0, x0 + w, y0 + h)

        cand = []
        for k, extra in enumerate(rings):
            q = g + 1.0 + extra
            cand += [(q + 1, 0, "left", "center", k), (q, 0.7 * q, "left", "bottom", k),
                     (q, -0.7 * q, "left", "top", k), (-q - 1, 0, "right", "center", k),
                     (-q, 0.7 * q, "right", "bottom", k), (-q, -0.7 * q, "right", "top", k),
                     (0, q + 2, "center", "bottom", k), (0, -q - 2, "center", "top", k)]
        others_m = np.hypot(mk[:, 0] - p[0], mk[:, 1] - p[1]) > 1e-6
        others, orr = mk[others_m], mr[others_m]
        best = None
        for dx, dy, ha, va, k in cand:
            box = text_box(dx, dy, ha, va)
            inside = box[0] >= ax_box[0] and box[1] >= ax_box[1] and box[2] <= ax_box[2] and box[3] <= ax_box[3]
            hit_label = any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in placed)
            d_other = box_dist(others, box) - orr
            if not inside or hit_label or np.any(box_dist(ln, box) <= 1.0):
                continue
            if k == 0:
                if np.any(d_other <= 0) or \
                        float(box_dist(p[None, :], box)[0]) - g + NEAR_MARGIN >= float(d_other.min()):
                    continue  # a neighbour is about as near to the label as its own marker
            else:
                if np.any(d_other <= NEAR_MARGIN):
                    continue  # the label would sit against another marker
                # the leader runs from the label centre to the point; check its part outside the label
                c = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
                s = c + np.linspace(0, 1, 40)[:, None] * (p - c)
                s = s[box_dist(s, box) > 0]
                if np.any(seg_dist(others, s[0], p) <= orr):
                    continue  # the leader line would pass through another marker
                if any(np.any(box_dist(s, b) <= 1.0) for b in placed):
                    continue  # the leader line would cross a placed label
            best = (dx, dy, ha, va, k)
            break
        if best is None:
            print(f"place_labels: no free position for {text}; first candidate used")
            best = cand[0]
        dx, dy, ha, va, k = best
        box = text_box(dx, dy, ha, va)
        placed.append(box)
        if k > 0:  # later labels must not cover this leader line
            c = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
            seg = c + np.linspace(0, 1, 40)[:, None] * (p - c)
            ln = np.vstack([ln, seg[box_dist(seg, box) > 0]])
        leader = (dict(arrowstyle="-", lw=0.5, color=fs.OI["grey"], shrinkA=1, shrinkB=g + 0.5) if k > 0
                  else None)
        ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=fontsize,
                    arrowprops=leader)


# ---------------------------------------------------------------------------
# Re-computed paths (same specification as the main tables)
# ---------------------------------------------------------------------------
def economy_paths(principle, units):
    """Observed, fitted (pre) and counterfactual (post) per-day values, S1 and S2."""
    cfg = m10.PRINCIPLES[principle]
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    R = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")["R"]
    df = m10.build_df(cfg, ex, pt, R)
    out = {}
    for spec in imp.SPECS:
        tr, _, _, un = imp.fit_impute(df, shock=C.SHOCK_START, drop=cfg["drop"], last=C.MAIN_END,
                                      spec=spec, panama=True, return_untreated=True)
        out[spec] = pd.concat([un.rename(columns={"fitted_per_day": "line"}),
                               tr.rename(columns={"cf_per_day": "line"})])[["unit", "period", "line"]]
    obs = df[["unit", "period", "per_day", "days"]]
    rows = []
    for u in units:
        o = obs[obs["unit"] == u].set_index("period")
        s1 = out["S1"][out["S1"]["unit"] == u].set_index("period")["line"]
        s2 = out["S2"][out["S2"]["unit"] == u].set_index("period")["line"]
        for p in months(PATH_START, C.MAIN_END):
            excluded = p in cfg["drop"]
            rows.append({"iso3": u, "period": p, "days": o.loc[p, "days"],
                         "observed_kt_per_day": np.nan if excluded else o.loc[p, "per_day"] / KT,
                         "excluded_month_observed_kt_per_day": o.loc[p, "per_day"] / KT if excluded else np.nan,
                         "s1_fitted_or_counterfactual_kt_per_day": s1.get(p, np.nan) / KT,
                         "s2_counterfactual_kt_per_day": s2.get(p, np.nan) / KT if p >= C.SHOCK_START else np.nan})
    return pd.DataFrame(rows)


def plot_paths(data, units, ncols, height_mm, excluded_label):
    nrows = int(np.ceil(len(units) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(fs.FULL, height_mm * fs.MM), sharex=True)
    axes = np.atleast_1d(axes).ravel()
    for ax, u in zip(axes, units):
        d = data[data["iso3"] == u]
        x = fs.to_dt(d["period"])
        ax.plot(x, d["observed_kt_per_day"], color=fs.OI["black"], lw=0.9, label="Observed")
        ax.plot(x, d["s1_fitted_or_counterfactual_kt_per_day"], color=fs.OI["blue"], lw=0.9,
                ls=(0, (4, 1.5)), label="S1 fit (to November 2023) and counterfactual")
        ax.plot(x, d["s2_counterfactual_kt_per_day"], color=fs.OI["vermillion"], lw=0.9, ls=(0, (1, 1)),
                label="S2 counterfactual")
        if d["excluded_month_observed_kt_per_day"].notna().any():
            ax.plot(x, d["excluded_month_observed_kt_per_day"], ls="none", marker="x", ms=4,
                    color=fs.OI["black"], label=excluded_label)
        fs.shock_line(ax)
        ax.set_title(u, loc="left", pad=2)
        ax.tick_params(axis="x", rotation=0)
        ax.xaxis.set_major_locator(plt.matplotlib.dates.YearLocator())
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y"))
    for ax in axes[len(units):]:
        ax.set_visible(False)
    for i, ax in enumerate(axes[:len(units)]):
        if i + ncols >= len(units):  # nothing visible below: show the year labels
            ax.xaxis.set_tick_params(labelbottom=True)
    for i, ax in enumerate(axes[:len(units)]):
        if i % ncols == 0:
            ax.set_ylabel(f"kt {fs.CO2} per day")
    handles, labels = axes[0].get_legend_handles_labels()
    if excluded_label and not any(lbl == excluded_label for lbl in labels):
        for ax in axes[:len(units)]:
            h, lab = ax.get_legend_handles_labels()
            if excluded_label in lab:
                handles, labels = h, lab
                break
    # legend in two rows below the panels, in a strip of 11 mm
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 11 / height_mm, 1, 1), h_pad=0.8, w_pad=0.8)
    return fig


def path_checks(name, data, principle, units, excluded):
    u0 = pd.read_csv(T / f"rsd4_{principle}_units.csv").set_index("iso3")
    post = data[data["period"] >= C.SHOCK_START]
    for spec, col in (("S1", "s1_fitted_or_counterfactual_kt_per_day"), ("S2", "s2_counterfactual_kt_per_day")):
        got = post.assign(e=(post["observed_kt_per_day"] - post[col]) * post["days"] / KT).groupby("iso3")["e"].sum()
        check_close(f"{name}_excess_{spec}", f"{name}: sum over 2023-12..2025-10 of (observed - {spec} line) x days "
                    f"equals excess_total_t_{spec} per economy, Mt", got.reindex(units),
                    u0.loc[units, f"excess_total_t_{spec}"] / MT)
    check(f"{name}_n", f"{name}: economies shown", len(units), data["iso3"].nunique(),
          data["iso3"].nunique() == len(units))
    for p in excluded:
        rows = data[data["period"] == p]
        absent = rows[["observed_kt_per_day", "s1_fitted_or_counterfactual_kt_per_day",
                       "s2_counterfactual_kt_per_day"]].isna().all().all()
        check(f"{name}_excluded_{p}", f"{name}: {p} absent from every line", True, bool(absent), bool(absent))


# ---------------------------------------------------------------------------
# Main figures
# ---------------------------------------------------------------------------
def fig_transits():
    name = "fig_transits"
    src = pd.read_csv(C.CHECKS / "portwatch_relative_transits.csv")
    cps = [("Suez Canal", fs.OI["blue"], "-"), ("Bab el-Mandeb Strait", fs.OI["vermillion"], (0, (4, 1.5))),
           ("Cape of Good Hope", fs.OI["green"], (0, (1, 1)))]
    d = src[(src["vessel_type"] == "total") & src["period"].isin(WINDOW) & src["chokepoint"].isin([c[0] for c in cps])]
    d = d[["chokepoint", "period", "n_rel"]].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(fs.FULL, 70 * fs.MM))
    for cp, col, ls in cps:
        s = d[d["chokepoint"] == cp]
        ax.plot(fs.to_dt(s["period"]), s["n_rel"], color=col, ls=ls, lw=1.1, label=cp)
    ax.axhline(1, color=fs.OI["grey"], lw=0.5, zorder=0)
    fs.shock_line(ax)
    ax.set_ylabel("Mean daily transits relative to the\nJanuary 2019 to November 2023 mean")
    ax.legend(loc="upper left")  # the empty area above the pre-crisis lines
    fig.tight_layout()
    paths = fs.save(fig, name, d)
    back = reread(paths)
    ref = src[(src["vessel_type"] == "total")].set_index(["chokepoint", "period"])["n_rel"]
    check_close(name, f"{name}: n_rel equals portwatch_relative_transits.csv",
                back["n_rel"], ref.reindex(list(zip(back["chokepoint"], back["period"]))).to_numpy())
    check(f"{name}_n", f"{name}: series x months", "3 x 82", f"{back['chokepoint'].nunique()} x {back['period'].nunique()}",
          back["chokepoint"].nunique() == 3 and back["period"].nunique() == 82)
    note(name, False, data=paths[2], sources="outputs/checks/portwatch_relative_transits.csv (from the PortWatch "
         "daily file via data/interim/portwatch_monthly.csv.gz)",
         specification="Monthly mean of daily total transits (n_total) divided by the chokepoint's own mean over "
         "2019-01..2023-11; 2019-01..2025-10.",
         definitions="Horizontal line at 1 = pre-crisis mean (January 2019 to November 2023, as in the y-axis "
         "label). Dashed vertical line = 2023-12 (shock month).")
    return paths


def fig_world_container():
    name = "fig_world_container"
    w = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w[w["period"].isin(WINDOW) & w["vessel"].isin(m11.TRANSIT + m11.NON_TRANSIT)].rename(columns={"vessel": "unit"})
    w["control"] = ~w["unit"].isin(m11.TRANSIT)
    lines = {}
    for spec in imp.SPECS:
        tr, _, _, un = imp.fit_impute(w, shock=C.SHOCK_START, last=C.MAIN_END, spec=spec, return_untreated=True)
        s = pd.concat([un.rename(columns={"fitted_per_day": "line"}), tr.rename(columns={"cf_per_day": "line"})])
        lines[spec] = s[s["unit"] == "CONTAINER"].set_index("period")["line"]
    types = pd.read_csv(T / "rsd2_types.csv").set_index("vessel")
    m = types.loc["CONTAINER", "max_abs_placebo"]
    o = w[w["unit"] == "CONTAINER"].set_index("period")
    post = np.array([p >= C.SHOCK_START for p in WINDOW])
    d = pd.DataFrame({"period": WINDOW, "days": o.loc[WINDOW, "days"].to_numpy(),
                      "observed_kt_per_day": o.loc[WINDOW, "per_day"].to_numpy() / KT,
                      "s1_kt_per_day": lines["S1"].reindex(WINDOW).to_numpy() / KT,
                      "s2_kt_per_day": lines["S2"].reindex(WINDOW).to_numpy() / KT})
    d["band_low_kt_per_day"] = np.where(post, d["s1_kt_per_day"] * (1 - m / 100), np.nan)
    d["band_high_kt_per_day"] = np.where(post, d["s1_kt_per_day"] * (1 + m / 100), np.nan)
    d["band_half_width_pct"] = np.where(post, m, np.nan)

    fig, ax = plt.subplots(figsize=(fs.FULL, 90 * fs.MM))
    x = fs.to_dt(d["period"])
    ax.fill_between(x, d["band_low_kt_per_day"], d["band_high_kt_per_day"], color=fs.OI["sky"], alpha=0.35, lw=0,
                    label=f"S1 counterfactual ± max |placebo %| ({m:.2f}%)")
    ax.plot(x, d["observed_kt_per_day"], color=fs.OI["black"], lw=1.1, label="Observed")
    ax.plot(x, d["s1_kt_per_day"], color=fs.OI["blue"], lw=1.0, ls=(0, (4, 1.5)),
            label="S1 fit (to November 2023) and counterfactual")
    ax.plot(x, d["s2_kt_per_day"], color=fs.OI["vermillion"], lw=1.0, ls=(0, (1, 1)),
            label="S2 fit (to November 2023) and counterfactual")
    fs.shock_line(ax)
    ax.set_ylabel(f"World container-ship emissions\n(kt {fs.CO2} per day)")
    # legend below the plotting area, so that it covers no line
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    paths = fs.save(fig, name, d)
    back = reread(paths)
    bp = back[back["period"] >= C.SHOCK_START]
    for spec, col in (("S1", "s1_kt_per_day"), ("S2", "s2_kt_per_day")):
        check_close(f"{name}_excess_{spec}", f"{name}: sum of (observed - {spec}) x days over 2023-12..2025-10 equals "
                    f"rsd2_types.csv CONTAINER excess_total_t_{spec}, Mt",
                    ((bp["observed_kt_per_day"] - bp[col]) * bp["days"]).sum() / KT,
                    types.loc["CONTAINER", f"excess_total_t_{spec}"] / MT)
    check_close(f"{name}_band", f"{name}: band half-width equals CONTAINER max_abs_placebo (rsd2_types.csv), %",
                (bp["band_high_kt_per_day"] / bp["s1_kt_per_day"] - 1) * 100, np.full(len(bp), m))
    note(name, False, data=paths[2], sources="data/interim/world_by_vessel.csv.gz (W RES_TOTAL by ship type); "
         "outputs/tables/rsd2_types.csv (max_abs_placebo)",
         specification="RS-D2 main run (W0): transit types treated, non-transit types as controls; RS-D15 S1 and S2; "
         "2019-01..2025-10.",
         definitions="Lines 'S1 fit (to November 2023) and counterfactual' and 'S2 fit (to November 2023) and "
         "counterfactual': up to 2023-11 they are fitted values of the model on untreated observations, multiplied by "
         "the smearing factor S_u; from 2023-12 they are the counterfactual. Band (from 2023-12 only): S1 "
         f"counterfactual x (1 +- m/100), m = CONTAINER's maximum absolute placebo percentage over the 10 RS-D16 "
         f"placebo runs of the main run ({m:.4f}%). Per-day values in kt CO2 per day.")
    return paths


def fig_departure_bars():
    name = "fig_departure_bars"
    u = pd.read_csv(T / "rsd4_departure_units.csv")
    u = u[~u["control"]]
    xu = pd.read_csv(T / "xu_gsc.csv")
    xu = xu[xu["principle"] == "departure"].set_index("iso3")
    sel = u[u["robust"] | (u["excess_total_t_S1"].abs() >= MT)].copy()
    sel = sel.sort_values("excess_total_t_S1")
    d = pd.DataFrame({"iso3": sel["iso3"], "robust": sel["robust"], "s1_excess_Mt": sel["excess_total_t_S1"] / MT,
                      "s2_excess_Mt": sel["excess_total_t_S2"] / MT,
                      "xu_excess_Mt": sel["iso3"].map(xu["excess_Mt"]).where(sel["robust"])}).reset_index(drop=True)
    legend_mm = 20  # strip below the axes for the one-column legend
    h = 12 + 4.2 * len(d) + legend_mm
    fig, ax = plt.subplots(figsize=(fs.SINGLE, h * fs.MM))
    y = np.arange(len(d))
    ax.barh(y[d["robust"]], d.loc[d["robust"], "s1_excess_Mt"], color=fs.OI["blue"], edgecolor=fs.OI["blue"],
            height=0.65, lw=0.6)
    ax.barh(y[~d["robust"]], d.loc[~d["robust"], "s1_excess_Mt"], color="white", edgecolor=fs.OI["blue"],
            height=0.65, lw=0.6)
    ax.plot(d["s2_excess_Mt"], y, ls="none", marker="D", ms=3, color=fs.OI["vermillion"])
    ax.plot(d["xu_excess_Mt"], y, ls="none", marker="x", ms=4, mew=1.0, color=fs.OI["black"])
    ax.axvline(0, color=fs.OI["black"], lw=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(d["iso3"])
    ax.set_xlabel(f"Excess, December 2023 to October 2025 (Mt {fs.CO2})")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    handles = [Patch(facecolor=fs.OI["blue"], edgecolor=fs.OI["blue"], label="S1, robust"),
               Patch(facecolor="white", edgecolor=fs.OI["blue"], label="S1, not robust"),
               Line2D([], [], ls="none", marker="D", ms=3, color=fs.OI["vermillion"], label="S2"),
               Line2D([], [], ls="none", marker="x", ms=4, mew=1.0, color=fs.OI["black"],
                      label="Generalized synthetic control (robust only)")]
    # one-column legend below the axes: the last entry is too wide for two columns or for the
    # empty part of the plotting area
    fig.legend(handles=handles, loc="lower center", ncol=1, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, legend_mm / h, 1, 1))
    paths = fs.save(fig, name, d)
    back = reread(paths).set_index("iso3")
    uu = u.set_index("iso3")
    check_close(f"{name}_S1", f"{name}: S1 equals rsd4_departure_units.csv", back["s1_excess_Mt"],
                uu.loc[back.index, "excess_total_t_S1"] / MT)
    check_close(f"{name}_S2", f"{name}: S2 equals rsd4_departure_units.csv", back["s2_excess_Mt"],
                uu.loc[back.index, "excess_total_t_S2"] / MT)
    rb = back[back["robust"]]
    check_close(f"{name}_xu", f"{name}: Xu equals xu_gsc.csv", rb["xu_excess_Mt"], xu.loc[rb.index, "excess_Mt"])
    n_exp = int((u["robust"] | (u["excess_total_t_S1"].abs() >= MT)).sum())
    check(f"{name}_n", f"{name}: economies shown (robust or |S1| >= 1 Mt, non-control)", n_exp, len(back),
          n_exp == len(back))
    note(name, False, data=paths[2], sources="outputs/tables/rsd4_departure_units.csv; outputs/tables/xu_gsc.csv",
         specification="Departure principle (TER_INT), R0 main estimates (RS-D4, RS-D15), window 2023-12..2025-10; "
         "Xu (2017) generalized synthetic control (RS-D20, r chosen from 0..5).",
         definitions=f"Economies shown: non-control economies that are robust (RS-D16) or have |S1 excess| >= 1 Mt "
         f"({len(d)} economies), sorted by S1 excess. x-axis: excess summed over December 2023 to October 2025. "
         "Filled bars: robust; hollow bars: not robust. Diamonds: S2 excess. Crosses ('Generalized synthetic control "
         "(robust only)'): Xu (2017) generalized synthetic control excess, robust economies only.")
    return paths


def fig_departure_paths():
    name = "fig_departure_paths"
    d = economy_paths("departure", DEP_PATH_ORDER)
    fig = plot_paths(d, DEP_PATH_ORDER, 3, 150, "Observed, November 2023 (excluded from estimation)")
    paths = fs.save(fig, name, d)
    path_checks(name, reread(paths), "departure", DEP_PATH_ORDER, ["2023-11"])
    note(name, False, data=paths[2], sources="data/interim/panel_departure.csv.gz; re-computed with "
         "src/09_imputation.py (same data and specification as outputs/tables/rsd4_departure_units.csv)",
         specification="Departure principle (TER_INT), R0, RS-D15 S1 and S2 with the Panama term; 2023-11 excluded "
         "from estimation (RS-D14). Panels shown 2021-01..2025-10; each panel has its own y-axis.",
         definitions="Solid black: observed per-day TER_INT. Dashed blue ('S1 fit (to November 2023) and "
         "counterfactual'): S1 fitted values up to 2023-11 (exp(fitted) x S_u) and the S1 counterfactual from "
         "2023-12. Dotted vermillion: S2 counterfactual from 2023-12. Cross ('Observed, November 2023 (excluded from "
         "estimation)'): observed value in 2023-11, which is excluded from estimation and from the lines. "
         "Order: EGY, SAU, MYS, ESP, IND, LKA, MUS, LBN, AZE.")
    return paths


def fig_principles():
    name = "fig_principles"
    s = pd.read_csv(T / "rsd4_summary.csv").set_index(["principle", "spec"])
    rows = []
    for p in ("residence", "departure"):
        for spec in imp.SPECS:
            r = s.loc[(p, spec)]
            rows.append({"principle": p, "spec": spec, "gross_gains_Mt": r["gross_gains_all_Mt"],
                         "gross_losses_Mt": r["gross_losses_all_Mt"], "net_Mt": r["excess_Mt"],
                         "robust_gains_Mt": r["gross_gains_robust_Mt"], "robust_losses_Mt": r["gross_losses_robust_Mt"]})
    d = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(fs.SINGLE, 82 * fs.MM))
    xs, labels = [], []
    for i, p in enumerate(("residence", "departure")):
        r1 = d[(d["principle"] == p) & (d["spec"] == "S1")].iloc[0]
        r2 = d[(d["principle"] == p) & (d["spec"] == "S2")].iloc[0]
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
        ax.text(base + 1, 1.02, p.capitalize(), transform=ax.get_xaxis_transform(), ha="center", va="bottom")
    ax.axhline(0, color=fs.OI["black"], lw=0.6)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_ylabel(f"Excess, December 2023 to\nOctober 2025 (Mt {fs.CO2})")
    handles = [Patch(facecolor=fs.OI["grey"], alpha=0.35, edgecolor=fs.OI["grey"], label="S1, all economies"),
               Patch(facecolor="none", edgecolor=fs.OI["grey"], hatch="////", label="S1, robust economies"),
               Line2D([], [], ls="none", marker="D", ms=3.5, color=fs.OI["black"], mfc="white", label="S2")]
    # legend in two rows below the axes, so that it covers no bar or marker
    fig.legend(handles=handles, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 12 / 82, 1, 1))
    paths = fs.save(fig, name, d)
    back = reread(paths).set_index(["principle", "spec"])
    for col, scol in (("gross_gains_Mt", "gross_gains_all_Mt"), ("gross_losses_Mt", "gross_losses_all_Mt"),
                      ("net_Mt", "excess_Mt"), ("robust_gains_Mt", "gross_gains_robust_Mt"),
                      ("robust_losses_Mt", "gross_losses_robust_Mt")):
        check_close(f"{name}_{col}", f"{name}: {col} equals rsd4_summary.csv {scol}", back[col],
                    s.loc[back.index, scol])
    note(name, False, data=paths[2], sources="outputs/tables/rsd4_summary.csv",
         specification="R0 main estimates, both principles, window 2023-12..2025-10; bars S1, diamonds S2.",
         definitions="Gross gains = sum of positive economy totals; gross losses = sum of negative economy totals "
         "(non-control economies); net = total excess. Hatched part = the contribution of robust economies (RS-D16) "
         "to gains and to losses (S1). Control economies have zero excess by construction.")
    return paths


def fig_rq3_scatter():
    name = "fig_rq3_scatter"
    u = pd.read_csv(T / "rsd4_departure_units.csv")
    u = u[~u["control"]].copy()
    ex = pd.read_csv(C.INTERIM / "exposure.csv").set_index("iso3")
    u["x_v"] = u["iso3"].map(ex["x_v"])
    u["group"] = np.where(u["rsl"], "RSL", np.where(u["cpa"], "CPA", "other"))
    co = pd.read_csv(T / "rq3_coefficients.csv")
    co = co[(co["principle"] == "departure") & (co["spec"] == "S1") & (co["variant"] == "weighted")].set_index("term")
    b0, b1 = co.loc["const", "coef"], co.loc["x_v", "coef"]
    max_cf = u["cf_total_t"].max()
    u["marker_area_pt2"] = 250 * u["cf_total_t"] / max_cf
    u["labelled"] = u["rsl"] | u["robust"]
    x_line = np.array([u["x_v"].min(), u["x_v"].max()])
    pts = pd.DataFrame({"element": "point", "iso3": u["iso3"], "group": u["group"], "robust": u["robust"],
                        "x_v": u["x_v"], "pct_S1": u["pct_S1"], "cf_Mt": u["cf_total_t"] / MT,
                        "marker_area_pt2": u["marker_area_pt2"], "labelled": u["labelled"]})
    line = pd.DataFrame({"element": "fitted_line_other", "x_v": x_line, "pct_S1": b0 + b1 * x_line})
    d = pd.concat([pts, line], ignore_index=True)

    style = {"other": (fs.OI["blue"], "o"), "CPA": (fs.OI["green"], "s"), "RSL": (fs.OI["vermillion"], "^")}
    legend_name = {"other": "Other economies", "CPA": "CPA", "RSL": "RSL"}  # the data file keeps the group codes
    fig, ax = plt.subplots(figsize=(fs.FULL, 110 * fs.MM))
    for g, (col, mk) in style.items():
        s = pts[pts["group"] == g]
        ax.scatter(s["x_v"], s["pct_S1"], s=s["marker_area_pt2"].clip(lower=4), c=col, marker=mk, alpha=0.6,
                   edgecolors=col, linewidths=0.5, label=legend_name[g])
    ax.plot(line["x_v"], line["pct_S1"], color=fs.OI["black"], lw=0.9,
            label="Weighted fit, other economies (S1)")
    ax.axhline(0, color=fs.OI["grey"], lw=0.5, zorder=0)
    ax.set_xlabel("Share of maritime export value through the Suez Canal")
    ax.set_ylabel("Departure-principle excess, S1\n(% of counterfactual)")
    leg = ax.legend(loc="upper left", markerscale=0.6)
    for h in leg.legend_handles[:3]:
        h.set_sizes([20])
    fig.tight_layout()
    # labels placed clear of every marker (radius from its area), the fitted line and the legend
    radius = np.sqrt(pts["marker_area_pt2"].clip(lower=4)) / 2
    xs_line = np.linspace(x_line[0], x_line[1], 200)
    xs_zero = np.linspace(*ax.get_xlim(), 200)
    lab_p = pts[pts["labelled"]].sort_values("iso3")
    place_labels(fig, ax, list(zip(lab_p["x_v"], lab_p["pct_S1"])), lab_p["iso3"].tolist(),
                 list(zip(pts["x_v"], pts["pct_S1"])), marker_r=radius.to_numpy(),
                 own_r=radius[lab_p.index].to_numpy(), obstacles=[leg],
                 lines=list(zip(xs_line, b0 + b1 * xs_line)) + list(zip(xs_zero, np.zeros(len(xs_zero)))))
    paths = fs.save(fig, name, d)
    back = reread(paths)
    bp = back[back["element"] == "point"].set_index("iso3")
    check_close(f"{name}_pct", f"{name}: pct_S1 equals rsd4_departure_units.csv", bp["pct_S1"],
                u.set_index("iso3").loc[bp.index, "pct_S1"])
    check_close(f"{name}_x_v", f"{name}: x_v equals exposure.csv", bp["x_v"], ex.loc[bp.index, "x_v"])
    bl = back[back["element"] == "fitted_line_other"]
    check_close(f"{name}_line", f"{name}: fitted line equals const + x_v coefficient (rq3_coefficients.csv)",
                bl["pct_S1"], b0 + b1 * bl["x_v"])
    check(f"{name}_n", f"{name}: economies shown (non-control, departure)", 88, len(bp), len(bp) == 88)
    note(name, False, data=paths[2], sources="outputs/tables/rsd4_departure_units.csv; data/interim/exposure.csv; "
         "outputs/tables/rq3_coefficients.csv (departure, S1, weighted)",
         specification="Departure principle, R0 S1, non-control economies (88).",
         definitions="Point area proportional to the economy's window counterfactual (S1; the largest point has "
         "250 pt^2). x-axis: x_v, the share of maritime export value through the Suez Canal. Groups: RSL (triangles), "
         "CPA (squares), other economies (circles; group 'other' in the data file; includes HQ and EEA economies). "
         "Line ('Weighted fit, other economies (S1)'): weighted RQ3 fit evaluated for other economies, const + b x "
         f"x_v = {b0:.3f} + {b1:.3f} x x_v, over the observed range of x_v. Labels: RSL members and robust "
         f"economies. {LEADER_NOTE}")
    return paths


# ---------------------------------------------------------------------------
# Supplementary figures
# ---------------------------------------------------------------------------
def sfig_residence_paths():
    name = "sfig_residence_paths"
    u0 = pd.read_csv(T / "rsd4_residence_units.csv")
    units = sorted(u0.loc[u0["robust"], "iso3"])
    d = economy_paths("residence", units)
    fig = plot_paths(d, units, 3, 190, None)
    paths = fs.save(fig, name, d, supplementary=True)
    path_checks(name, reread(paths), "residence", units, [])
    note(name, True, data=paths[2], sources="data/interim/panel_residence.csv.gz; re-computed with "
         "src/09_imputation.py (same data and specification as outputs/tables/rsd4_residence_units.csv)",
         specification="Residence principle (RES_TOTAL), R0, RS-D15 S1 and S2 with the Panama term; 2021-01..2025-10; "
         "no excluded month.",
         definitions=f"As fig_departure_paths. Economies: the {len(units)} residence robust economies "
         f"({' '.join(units)}), alphabetical.")
    return paths


def sfig_robustness_departure():
    name = "sfig_robustness_departure"
    r = pd.read_csv(T / "robustness_economies.csv")
    r = r[(r["principle"] == "departure") & (r["spec"] == "S1") & ~r["variant"].str.startswith("R14")]
    variants = list(r["variant"])
    d = r.melt(id_vars=["variant"], value_vars=[f"excess_Mt_{k}" for k in ROB_DEP_KEYS],
               var_name="iso3", value_name="s1_excess_Mt")
    d["iso3"] = d["iso3"].str.replace("excess_Mt_", "")
    fig, axes = plt.subplots(2, 4, figsize=(fs.FULL, 110 * fs.MM), sharey=True)
    axes = axes.ravel()
    y = np.arange(len(variants))[::-1]
    for ax, k in zip(axes, ROB_DEP_KEYS):
        s = d[d["iso3"] == k].set_index("variant").loc[variants]
        ax.plot(s["s1_excess_Mt"], y, ls="none", marker="o", ms=3, color=fs.OI["blue"])
        r0 = s.loc["R0", "s1_excess_Mt"]
        ax.axvline(r0, color=fs.OI["grey"], lw=0.6, ls=(0, (3, 2)))
        ax.axvline(0, color=fs.OI["black"], lw=0.5)
        ax.set_title(k, loc="left", pad=2)
        ax.set_xlabel(f"S1 excess (Mt {fs.CO2})")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(variants)
    axes[4].set_yticks(y)
    axes[4].set_yticklabels(variants)
    axes[-1].set_visible(False)
    fig.tight_layout(h_pad=1.0, w_pad=0.6)
    paths = fs.save(fig, name, d, supplementary=True)
    back = reread(paths)
    ref = r.set_index("variant")
    check_close(name, f"{name}: values equal robustness_economies.csv (departure, S1)", back["s1_excess_Mt"],
                [ref.loc[v, f"excess_Mt_{k}"] for v, k in zip(back["variant"], back["iso3"])])
    note(name, True, data=paths[2], sources="outputs/tables/robustness_economies.csv",
         specification="Departure principle, S1 window excess, variants R0-R10, R12, R13 (R11 is residence-only; "
         "R14 is leave-one-out and is not shown).",
         definitions="One panel per economy, each with its own x-axis. Dashed vertical line: R0 value. Missing "
         "marker: economy not estimated in that variant (ESP in R2, EEA dropped). Variant definitions in "
         "src/12_robustness_economies.py.")
    return paths


def sfig_world_types():
    name = "sfig_world_types"
    t = pd.read_csv(T / "rsd2_types.csv").sort_values("pct_S1")
    d = t[["vessel", "pct_S1", "pct_S2", "max_abs_placebo"]].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(fs.SINGLE, 88 * fs.MM))
    y = np.arange(len(d))
    ax.barh(y, 2 * d["max_abs_placebo"], left=-d["max_abs_placebo"], height=0.6, color=fs.OI["grey"], alpha=0.3,
            lw=0, label="± max |placebo %|")
    ax.plot(d["pct_S1"], y, ls="none", marker="o", ms=3.5, color=fs.OI["blue"], label="S1")
    ax.plot(d["pct_S2"], y, ls="none", marker="D", ms=3, color=fs.OI["vermillion"], label="S2")
    ax.axvline(0, color=fs.OI["black"], lw=0.5)
    # symmetric x-limits with a margin, so that no band ends on the axis line
    lim = 1.08 * float(np.nanmax(np.abs(d[["pct_S1", "pct_S2", "max_abs_placebo"]].to_numpy())))
    ax.set_xlim(-lim, lim)
    ax.set_yticks(y)
    ax.set_yticklabels([TYPE_LABELS[v] for v in d["vessel"]])
    ax.set_xlabel("Window excess, % of counterfactual")
    # legend below the plotting area, so that it covers no data
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    paths = fs.save(fig, name, d, supplementary=True)
    back = reread(paths).set_index("vessel")
    tt = t.set_index("vessel")
    for c in ("pct_S1", "pct_S2", "max_abs_placebo"):
        check_close(f"{name}_{c}", f"{name}: {c} equals rsd2_types.csv", back[c], tt.loc[back.index, c])
    check(f"{name}_n", f"{name}: transit types shown", 10, len(back), len(back) == 10)
    check(f"{name}_labels", f"{name}: every type shown has a readable label", "all",
          "all" if set(back.index) <= set(TYPE_LABELS) else "missing", set(back.index) <= set(TYPE_LABELS))
    note(name, True, data=paths[2], sources="outputs/tables/rsd2_types.csv",
         specification="RS-D2 main run (W0), transit types, window 2023-12..2025-10.",
         definitions="Grey band: from -m to +m, m = the type's maximum absolute placebo % over the 10 RS-D16 "
         "placebo runs. A type is robust when S1 and S2 share a sign and both exceed m in absolute value. Axis "
         "labels are readable names of the OECD ship-type codes, which are kept in the data file: "
         + "; ".join(f"{k} = {v}" for k, v in TYPE_LABELS.items()) + ".")
    return paths


def sfig_dose():
    name = "sfig_dose"
    t = pd.read_csv(T / "rsd2_dose_check.csv")
    t = t[t["status"] == "computed"]
    d = t[["category", "d_c_transits_per_ship_year", "pct_S1", "pct_S2"]].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(fs.SINGLE, 65 * fs.MM))
    ax.plot(d["d_c_transits_per_ship_year"], d["pct_S1"], ls="none", marker="o", ms=4, color=fs.OI["blue"], label="S1")
    ax.plot(d["d_c_transits_per_ship_year"], d["pct_S2"], ls="none", marker="D", ms=3.5, color=fs.OI["vermillion"],
            label="S2")
    ax.axhline(0, color=fs.OI["grey"], lw=0.5)
    ax.set_xlabel("Pre-crisis Suez transits per ship and year")
    ax.set_ylabel("Window excess, % of counterfactual")
    leg = ax.legend(loc="upper left")
    ax.margins(x=0.15, y=0.15)
    fig.tight_layout()
    # each category labelled at its upper marker, clear of the other markers, the zero line and the legend
    xs_zero = np.linspace(*ax.get_xlim(), 200)
    xd = d["d_c_transits_per_ship_year"]
    place_labels(fig, ax, list(zip(xd, d[["pct_S1", "pct_S2"]].max(axis=1))), d["category"].tolist(),
                 list(zip(xd, d["pct_S1"])) + list(zip(xd, d["pct_S2"])), marker_r=2.5,
                 obstacles=[leg], lines=list(zip(xs_zero, np.zeros(200))))
    paths = fs.save(fig, name, d, supplementary=True)
    back = reread(paths).set_index("category")
    tt = t.set_index("category")
    for c in ("d_c_transits_per_ship_year", "pct_S1", "pct_S2"):
        check_close(f"{name}_{c}", f"{name}: {c} equals rsd2_dose_check.csv", back[c], tt.loc[back.index, c])
    note(name, True, data=paths[2], sources="outputs/tables/rsd2_dose_check.csv",
         specification="RS-D2 dose check; W0 S1 and S2 excess summed over the category's OECD types; three "
         "categories computed (tanker skipped: UNCTAD labels for chemical tankers and liquefied gas carriers absent).",
         definitions="x-axis ('Pre-crisis Suez transits per ship and year'): d_c = PortWatch Suez Canal mean daily "
         "transits 2019-01..2023-11 x 365 / UNCTAD world number of ships of the category on 1 January 2023. Each "
         f"category is labelled at its upper marker. {LEADER_NOTE}")
    return paths


def sfig_within_eea():
    out = []
    w = pd.read_csv(T / "within_eea.csv")
    for principle in ("residence", "departure"):
        name = f"sfig_within_eea_{principle}"
        s = w[(w["principle"] == principle) & ~w["control_within_eea"]]
        d = s[["iso3", "R0_pct_S1", "pct_S1", "robust", "R0_robust"]].reset_index(drop=True)
        fig, ax = plt.subplots(figsize=(fs.SINGLE, 85 * fs.MM))
        lim = [min(d["R0_pct_S1"].min(), d["pct_S1"].min()) * 1.1, max(d["R0_pct_S1"].max(), d["pct_S1"].max()) * 1.1]
        ax.plot(lim, lim, color=fs.OI["grey"], lw=0.6, ls=(0, (3, 2)), label="45-degree line")
        rb = d["robust"].astype(bool)
        ax.plot(d.loc[~rb, "R0_pct_S1"], d.loc[~rb, "pct_S1"], ls="none", marker="o", ms=4, mfc="white",
                color=fs.OI["blue"], label="Not robust within EEA")
        ax.plot(d.loc[rb, "R0_pct_S1"], d.loc[rb, "pct_S1"], ls="none", marker="o", ms=4, color=fs.OI["blue"],
                label="Robust within EEA")
        # label only robust economies (within the EEA or in R0), ESP, GRC, FRA, and points with |S1 %| >= 20
        # in either estimate; all markers are drawn
        lab = (rb | d["R0_robust"].astype(bool) | d["iso3"].isin(EEA_ALWAYS_LABEL)
               | (d["R0_pct_S1"].abs() >= EEA_LABEL_PCT) | (d["pct_S1"].abs() >= EEA_LABEL_PCT))
        check(f"{name}_labels", f"{name}: economies labelled (rule in figure_notes.md)", "(report)",
              " ".join(sorted(d.loc[lab, "iso3"])), True)
        ax.axhline(0, color=fs.OI["grey"], lw=0.4)
        ax.axvline(0, color=fs.OI["grey"], lw=0.4)
        ax.set_xlabel("Main estimate (R0), S1 excess (% of counterfactual)")
        ax.set_ylabel("Within-EEA estimate, S1 excess\n(% of counterfactual)")
        leg = ax.legend(loc="upper left")
        fig.tight_layout()
        # labels clear of the markers, the 45-degree line, both zero lines and the legend
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        s45 = np.linspace(*lim, 200)
        lines = (list(zip(s45, s45)) + list(zip(np.linspace(x0, x1, 200), np.zeros(200)))
                 + list(zip(np.zeros(200), np.linspace(y0, y1, 200))))
        lab_d = d[lab].sort_values("iso3")
        place_labels(fig, ax, list(zip(lab_d["R0_pct_S1"], lab_d["pct_S1"])), lab_d["iso3"].tolist(),
                     list(zip(d["R0_pct_S1"], d["pct_S1"])), marker_r=3.0, obstacles=[leg], lines=lines)
        paths = fs.save(fig, name, d, supplementary=True)
        back = reread(paths).set_index("iso3")
        ww = s.set_index("iso3")
        check_close(f"{name}_values", f"{name}: values equal within_eea.csv",
                    np.r_[back["pct_S1"], back["R0_pct_S1"]], np.r_[ww.loc[back.index, "pct_S1"], ww.loc[back.index, "R0_pct_S1"]])
        check(f"{name}_n", f"{name}: EEA non-control economies shown", 16, len(back), len(back) == 16)
        note(name, True, data=paths[2], sources="outputs/tables/within_eea.csv",
             specification=f"RS-D19 within-EEA estimate, {principle} principle, S1, against the R0 S1 estimate; "
             "economies outside the within-EEA control pool.",
             definitions="Filled markers: robust within the EEA panel (RS-D16 rule within that panel). Labels: "
             "economies robust within the EEA panel or in R0, ESP, GRC and FRA, and any economy with |S1 %| >= "
             f"{EEA_LABEL_PCT} in either estimate; other economies are shown unlabelled. {LEADER_NOTE}")
        out.append(paths)
    return out


def sfig_xu_vs_imputation():
    out = []
    x = pd.read_csv(T / "xu_gsc.csv")
    for principle in ("residence", "departure"):
        name = f"sfig_xu_vs_imputation_{principle}"
        s = x[x["principle"] == principle].sort_values("R0_pct_S1")
        d = s[["iso3", "R0_pct_S1", "R0_pct_S2", "pct"]].rename(columns={"pct": "xu_pct"}).reset_index(drop=True)
        fig, ax = plt.subplots(figsize=(fs.SINGLE, (15 + 5.5 * len(d)) * fs.MM))
        y = np.arange(len(d))
        ax.plot(d["R0_pct_S1"], y + 0.2, ls="none", marker="o", ms=3.5, color=fs.OI["blue"], label="S1")
        ax.plot(d["R0_pct_S2"], y, ls="none", marker="D", ms=3, color=fs.OI["vermillion"], label="S2")
        ax.plot(d["xu_pct"], y - 0.2, ls="none", marker="x", ms=4, mew=1.0, color=fs.OI["black"], label="Xu")
        ax.axvline(0, color=fs.OI["black"], lw=0.5)
        ax.set_yticks(y)
        ax.set_yticklabels(d["iso3"])
        ax.set_xlabel("Window excess, % of counterfactual")
        ax.legend(loc="lower right")
        fig.tight_layout()
        paths = fs.save(fig, name, d, supplementary=True)
        back = reread(paths).set_index("iso3")
        xx = s.set_index("iso3")
        check_close(f"{name}_values", f"{name}: values equal xu_gsc.csv",
                    np.r_[back["R0_pct_S1"], back["R0_pct_S2"], back["xu_pct"]],
                    np.r_[xx.loc[back.index, "R0_pct_S1"], xx.loc[back.index, "R0_pct_S2"], xx.loc[back.index, "pct"]])
        note(name, True, data=paths[2], sources="outputs/tables/xu_gsc.csv",
             specification=f"{principle.capitalize()} principle, R0 robust economies: RS-D15 S1 and S2 (R0) and Xu "
             "(2017) generalized synthetic control (RS-D20, r chosen from 0..5), window 2023-12..2025-10.",
             definitions="Sorted by S1 %.")
        out.append(paths)
    return out


def write_notes(path):
    lines = ["# Figure notes", "",
             "Each figure is saved as PDF (vector) and PNG (300 dpi), with a data file holding the plotted numbers. "
             "Emissions are in Mt CO2, or kt CO2 per day where per-day values are plotted. The dashed vertical line "
             "on time axes marks 2023-12, the first crisis month. The estimation window ends in 2025-10.", ""]
    for supp in (False, True):
        lines += ["## " + ("Supplementary figures" if supp else "Main figures"), ""]
        for name, n in NOTES.items():
            if n["supplementary"] != supp:
                continue
            folder = "outputs/figures/supplementary/" if supp else "outputs/figures/"
            lines += [f"### {name}", "",
                      f"- Files: `{folder}{name}.pdf`, `{folder}{name}.png`",
                      f"- Data file: `{rel(n['data'])}`",
                      f"- Source tables: {n['sources']}",
                      f"- Specification: {n['specification']}",
                      f"- Definitions: {n['definitions']}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    t0 = time.perf_counter()
    fs.setup()
    for f in (fig_transits, fig_world_container, fig_departure_bars, fig_departure_paths, fig_principles,
              fig_rq3_scatter, sfig_residence_paths, sfig_robustness_departure, sfig_world_types, sfig_dose):
        p = f()
        FILES.extend(p)
        print(f"{f.__name__}: {rel(p[0])}")
    for f in (sfig_within_eea, sfig_xu_vs_imputation):
        for p in f():
            FILES.extend(p)
            print(f"{f.__name__}: {rel(p[0])}")
    # lettering audit of every figure (RS-D28), read from the drawn figure before saving (figstyle.audit)
    for name, a in fs.AUDIT.items():
        check(f"{name}_min_font", f"{name}: smallest rendered font size of any text, pt (mathtext sub- and "
              f"superscripts counted at {fs.MATHTEXT_SHRINK} x)", f">= {fs.MIN_FONT:.1f}", f"{a['min_font']:.1f}",
              a["min_font"] >= fs.MIN_FONT)
        check(f"{name}_text_inside", f"{name}: texts drawn wholly inside the figure (of {a['n_texts']} texts)", 0,
              len(a["outside"]), not a["outside"])
        check(f"{name}_text_overlap", f"{name}: pairs of overlapping text boxes", 0, len(a["overlaps"]),
              not a["overlaps"])
        check(f"{name}_plain_text", f"{name}: drawn texts containing an underscore, RS-D, RQ followed by a digit "
              "or a date written as YYYY-MM", 0, len(a["codes"]), not a["codes"])
        if a["outside"] or a["overlaps"] or a["codes"]:
            print(f"{name}: outside {a['outside']}; overlaps {a['overlaps']}; codes {a['codes']}")
    write_notes(fs.FIG_DIR / "figure_notes.md")
    print(f"{rel(fs.FIG_DIR / 'figure_notes.md')} written")
    write_checks(CHECKS, C.CHECKS / "figure_checks.csv")
    print(f"Run time {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
