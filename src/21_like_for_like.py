"""Like-for-like comparison of the two principles (RS-D29).

Two new series (ALL_VESSELS, window 2019-01..2025-10):
- RES_INT = D + E + F (RES_INT_FROM + RES_INT_TO + RES_INT_OUT), absent components = 0 (RS-D13);
  compared with TER_INT (international voyages under both principles).
- TER_TOT = TER_DOM + TER_INT; compared with RES_TOTAL (all voyages under both principles).

Panels
- RES_INT: economies whose RES_TOTAL is complete over the window, whose RES_INT has at least one
  positive month in each pre-crisis year (2019..2023), and whose RES_INT is positive in every
  window month. The last condition applies the RS-D10 complete-series rule to RES_INT: a zero
  RES_INT means that none of D, E, F is published for that month, and log(0) has no value.
- TER_TOT: economies complete in both TER_DOM and TER_INT over the window.

Exposure (pre-crisis component sums or means; ratios do not depend on which)
- e_int = (D*x_v + E*m_v + F*w) / (D + E + F), D, E, F from data/interim/exposure.csv;
  Panama share P_int: the same formula with x_P, m_P and w_P.
- x_tot = x_v * mean(TER_INT) / mean(TER_TOT), means over the pre-crisis months used in
  estimation; P_tot = x_P * the same ratio.

Pipeline per series, unchanged from the main estimates: RS-D14 anomaly scan (05_anomaly_scan.scan)
with system-wide anomalous months excluded; control pool = tercile cut-off over the series panel
with exposure data, excluding RSL, CPA, HQ and RUS; RS-D15 S1 and S2 with the Panama term;
RS-D16 placebos and robust rule. The two main series are read from the existing outputs as
reference rows, not re-estimated; the generic pipeline is also run on them once to confirm that
it reproduces the stored results (checks only).

Outputs
- outputs/tables/like_for_like_units.csv, like_for_like_summary.csv, like_for_like_pairs.csv,
  like_for_like_pairs_summary.csv, like_for_like_placebo_aggregate.csv
- outputs/checks/like_for_like_anomaly_flags.csv, like_for_like_anomaly_months.csv,
  like_for_like_exposure.csv
- data/interim/like_for_like_panel.csv.gz, like_for_like_runs.csv (inputs of 23_rolling_placebo.py)
- outputs/checks/revision_checks.csv (rows starting with 'lfl_')
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import complete_economies, days_in, exact_check, load_oecd_monthly, months, rel, update_checks

imp = importlib.import_module("09_imputation")
m05 = importlib.import_module("05_anomaly_scan")
m10 = importlib.import_module("10_rsd4_economies")

TABLES = C.OUTPUTS / "tables"
MT = 1e6
WINDOW = months(C.PRE_START, C.MAIN_END)
PRE = months(C.PRE_START, C.PRE_END)
GROUPS = ["rsl", "cpa", "hq", "eea", "rus"]
EXCLUDED_FROM_POOL = ("rsl", "cpa", "hq", "rus")
INT_COMP = ["RES_INT_FROM", "RES_INT_TO", "RES_INT_OUT"]
CHECKS_FILE = C.CHECKS / "revision_checks.csv"
SERIES_ORDER = ["RES_TOTAL", "RES_INT", "TER_INT", "TER_TOT"]
PAIRS = [("RES_INT", "TER_INT"), ("RES_TOTAL", "TER_TOT")]
MAIN_PRINCIPLE = {"RES_TOTAL": "residence", "TER_INT": "departure"}


# ---------------------------------------------------------------------------
# Series and panels
# ---------------------------------------------------------------------------
def build_series(m, checks):
    """Long tables (iso3, period, value_t) of RES_INT and TER_TOT on their panels, plus panel notes."""
    notes = {}
    # ---- RES_INT --------------------------------------------------------
    res_panel = complete_economies(m, "RES_TOTAL", C.PRE_START, C.MAIN_END)
    econ = m[~m["area"].isin(C.NON_ECONOMY_AREAS)]
    tot_all = econ[econ["source"] == "RES_TOTAL"].set_index(["area", "period"])["value_t"]
    comp_all = econ[econ["source"].isin(INT_COMP)].groupby(["area", "period"])["value_t"].sum()
    ri_all = comp_all.reindex(tot_all.index).fillna(0.0)
    rel_over = (ri_all - tot_all) / tot_all
    viol = int((rel_over > 1e-9).sum())
    checks.append(exact_check("lfl_identity_res_int_le_res_total",
                              f"economy-months (all economies, all months with RES_TOTAL; {len(tot_all)}) with "
                              "RES_INT = D+E+F > RES_TOTAL x (1 + 1e-9); largest relative excess of RES_INT over "
                              f"RES_TOTAL in any economy-month: {rel_over.max():.3g} (floating-point rounding)",
                              0, viol))

    ri = ri_all.rename("value_t").reset_index().rename(columns={"area": "iso3"})
    ri = ri[ri["iso3"].isin(res_panel) & ri["period"].isin(WINDOW)]
    pre = ri[ri["period"].isin(PRE)]
    pos_year = pre.assign(year=pre["period"].str[:4]).groupby(["iso3", "year"])["value_t"].apply(
        lambda x: bool((x > 0).any())).unstack()
    cond1 = pos_year.all(axis=1)
    drop1 = sorted(cond1[~cond1].index)
    pos_all = ri.groupby("iso3")["value_t"].apply(lambda x: bool((x > 0).all()))
    drop2 = sorted(set(pos_all[~pos_all].index) - set(drop1))
    zero_months = ri[(ri["value_t"] <= 0) & ri["iso3"].isin(drop2)].groupby("iso3")["period"].apply(list)
    keep = sorted(set(res_panel) - set(drop1) - set(drop2))
    ri = ri[ri["iso3"].isin(keep)]
    notes["RES_INT"] = {
        "base_panel": f"RES_TOTAL complete over the window ({len(res_panel)})",
        "dropped_no_positive_month_in_a_pre_crisis_year": " ".join(drop1),
        "dropped_zero_month_in_window": " ".join(drop2),
        "zero_months": "; ".join(f"{k}: {' '.join(v)}" for k, v in zero_months.items()),
    }
    checks.append(exact_check("lfl_res_int_base_panel", "RES_INT: economies with RES_TOTAL complete over "
                              "2019-01..2025-10", "140", len(res_panel)))
    checks.append(exact_check("lfl_res_int_dropped_rule_positive_year", "RES_INT: economies dropped for no positive "
                              "month in some pre-crisis year (" + (" ".join(drop1) or "none") + ")", "(report)",
                              len(drop1)) | {"pass": True, "abs_diff": ""})
    checks.append(exact_check("lfl_res_int_dropped_zero_month", "RES_INT: economies dropped for a zero month in the "
                              "window, i.e. none of D, E, F published (" + (" ".join(drop2) or "none") + ")",
                              "(report)", len(drop2)) | {"pass": True, "abs_diff": ""})

    # ---- TER_TOT --------------------------------------------------------
    dom = complete_economies(m, "TER_DOM", C.PRE_START, C.MAIN_END)
    ter = complete_economies(m, "TER_INT", C.PRE_START, C.MAIN_END)
    both = sorted(set(dom) & set(ter))
    t = econ[econ["source"].isin(["TER_DOM", "TER_INT"]) & econ["area"].isin(both) & econ["period"].isin(WINDOW)]
    tw = t.pivot_table(index=["area", "period"], columns="source", values="value_t", aggfunc="first")
    tt = (tw["TER_DOM"] + tw["TER_INT"]).rename("value_t").reset_index().rename(columns={"area": "iso3"})
    notes["TER_TOT"] = {"base_panel": f"TER_DOM complete ({len(dom)}) and TER_INT complete ({len(ter)})",
                        "TER_INT_not_TER_DOM": " ".join(sorted(set(ter) - set(dom))),
                        "TER_DOM_not_TER_INT": " ".join(sorted(set(dom) - set(ter)))}
    checks.append(exact_check("lfl_ter_tot_panel", "TER_TOT: economies complete in both TER_DOM and TER_INT "
                              f"(TER_INT only: {notes['TER_TOT']['TER_INT_not_TER_DOM'] or 'none'})", "(report)",
                              len(both)) | {"pass": True, "abs_diff": ""})
    return {"RES_INT": ri.reset_index(drop=True), "TER_TOT": tt}, tw, notes


def anomaly_scan(series):
    """RS-D14 scan on each new series (05_anomaly_scan.scan). Returns flags, months, system-wide months."""
    flags, mons, sw = [], [], {}
    for name, s in series.items():
        mm = s.rename(columns={"iso3": "area"}).assign(source=name)
        sc, n_panel, n_larger = m05.scan(mm, name, C.PRE_START, C.MAIN_END)
        by = sc.groupby("period").agg(
            n_flagged_larger_half=("flag", lambda f: int((f & sc.loc[f.index, "larger_half"]).sum())),
            n_flagged_all=("flag", "sum")).reset_index()
        by["n_flagged_all"] = by["n_flagged_all"].astype(int)
        by["system_wide"] = by["n_flagged_larger_half"] >= m05.MIN_LARGER_HALF
        by.insert(0, "series", name)
        mons.append(by)
        f = sc[sc["flag"]].copy()
        f.insert(0, "series", name)
        sw[name] = sorted(by.loc[by["system_wide"], "period"])
        f["system_wide_month"] = f["period"].isin(sw[name])
        flags.append(f[["series", "iso3", "period", "value_t", "per_day", "rolling_median", "log_ratio",
                        "larger_half", "system_wide_month"]])
        print(f"{name}: scan panel {n_panel}, larger half {n_larger}, flags {len(f)}, "
              f"system-wide months {sw[name] or 'none'}")
    return pd.concat(flags, ignore_index=True), pd.concat(mons, ignore_index=True), sw


# ---------------------------------------------------------------------------
# Exposure and estimation tables
# ---------------------------------------------------------------------------
def exposure(series, tw, sw, ex, pt, checks):
    v3 = pd.read_csv(C.V3_SHARES)
    sx = v3[(v3["chokepoint"] == "Suez Canal") & (v3["direction"] == "export")]
    w = sx["v_canal"].sum() / sx["v_sea_predict"].sum()
    px = v3[(v3["chokepoint"] == "Panama Canal") & (v3["direction"] == "export")]
    w_p = px["v_canal"].sum() / px["v_sea_predict"].sum()
    e = ex.set_index("iso3")
    out = {}

    # RES_INT
    iso = sorted(series["RES_INT"]["iso3"].unique())
    d = e.reindex(iso)
    den = (d["D"] + d["E"] + d["F"]).replace(0, np.nan)
    t = pd.DataFrame({"iso3": iso})
    t["exposure"] = ((d["D"] * d["x_v"] + d["E"] * d["m_v"] + d["F"] * w) / den).to_numpy()
    p = pt.reindex(iso)
    t["P"] = ((d["D"] * p["x_P"] + d["E"] * p["m_P"] + d["F"] * w_p) / den).to_numpy()
    t["int_share_pre"] = (den / (d["A"] + d["B"] + den)).to_numpy()
    out["RES_INT"] = t

    # TER_TOT
    iso = sorted(series["TER_TOT"]["iso3"].unique())
    pre = [q for q in PRE if q not in sw["TER_TOT"]]
    tp = tw[tw.index.get_level_values("period").isin(pre)]
    mean_int = tp["TER_INT"].groupby(level="area").mean()
    mean_tot = (tp["TER_DOM"] + tp["TER_INT"]).groupby(level="area").mean()
    ratio = (mean_int / mean_tot).reindex(iso)
    t = pd.DataFrame({"iso3": iso})
    t["exposure"] = (e["x_v"].reindex(iso) * ratio).to_numpy()
    t["P"] = (pt["x_P"].reindex(iso) * ratio).to_numpy()
    t["int_share_pre"] = ratio.to_numpy()
    out["TER_TOT"] = t
    checks.append(exact_check("lfl_ter_tot_ratio_months", "TER_TOT: pre-crisis months used for mean(TER_INT) / "
                              "mean(TER_TOT) (system-wide anomalous months excluded)", "(report)",
                              f"{pre[0]}..{pre[-1]} ({len(pre)} months)") | {"pass": True, "abs_diff": ""})

    grp = ex.set_index("iso3")[GROUPS]
    for name, t in out.items():
        t[GROUPS] = grp.reindex(t["iso3"]).fillna(False).astype(bool).to_numpy()
        base = t[t["exposure"].notna()]
        cut = base["exposure"].quantile(1 / 3)
        t["control"] = t["exposure"].notna() & (t["exposure"] <= cut) & ~t[list(EXCLUDED_FROM_POOL)].any(axis=1)
        t["cutoff"] = cut
        t["has_exposure"] = t["exposure"].notna()
        t.insert(0, "series", name)
        missing = sorted(t.loc[~t["has_exposure"], "iso3"])
        checks.append(exact_check(f"lfl_{name}_n_with_exposure", f"{name}: panel economies with exposure data "
                                  f"(missing: {' '.join(missing) or 'none'})", "(report)", len(base))
                      | {"pass": True, "abs_diff": ""})
        checks.append(exact_check(f"lfl_{name}_pool_size", f"{name}: control pool, cut-off {cut:.6f}", "(report)",
                                  int(t["control"].sum())) | {"pass": True, "abs_diff": ""})
        v = base["exposure"]
        checks.append({"check": f"lfl_{name}_exposure_range", "definition": f"{name}: exposure range over the panel "
                       "with exposure data (must lie in [0, 1])", "expected": "0-1",
                       "obtained": f"{v.min():.6f}-{v.max():.6f}", "abs_diff": "",
                       "pass": bool(v.min() >= 0 and v.max() <= 1)})
        vp = t.loc[t["P"].notna(), "P"]
        checks.append({"check": f"lfl_{name}_panama_range", "definition": f"{name}: Panama share range (in [0, 1])",
                       "expected": "0-1", "obtained": f"{vp.min():.6f}-{vp.max():.6f}", "abs_diff": "",
                       "pass": bool(vp.min() >= 0 and vp.max() <= 1)})
    return out, w, w_p


def estimation_table(s, t, R):
    s = s[s["iso3"].isin(t.loc[t["has_exposure"], "iso3"])].sort_values(["iso3", "period"])
    df = pd.DataFrame({"unit": s["iso3"].to_numpy(), "period": s["period"].to_numpy()})
    df["days"] = days_in(df["period"]).to_numpy()
    df["value_t"] = s["value_t"].to_numpy()
    df["per_day"] = df["value_t"] / df["days"]
    ti = t.set_index("iso3")
    df["control"] = df["unit"].map(ti["control"]).astype(bool)
    df["P"] = df["unit"].map(ti["P"])
    df["R"] = df["period"].map(R).fillna(0).astype(int)
    return df


def run_series(name, df, drop, last_pre, grp):
    """Main S1/S2 fits and RS-D16 placebos; units table with the columns of rsd4_<principle>_units.csv."""
    main, diags, weights = {}, {}, None
    for spec in imp.SPECS:
        tr, dg, wts = imp.fit_impute(df, shock=C.SHOCK_START, drop=drop, last=C.MAIN_END, spec=spec, panama=True)
        main[spec], diags[spec], weights = tr, dg, wts
    unit_pl, agg_pl = imp.placebo_runs(df, last_pre=last_pre, drop=drop, panama=True)
    econ = sorted(df["unit"].unique())
    u = pd.DataFrame({"iso3": econ})
    u = u.join(grp.reindex(econ).reset_index(drop=True))
    u["control"] = u["iso3"].map(df.drop_duplicates("unit").set_index("unit")["control"])
    u["weight"] = u["iso3"].map(weights)
    g1, by_year = imp.summarise_unit(main["S1"])
    g2, _ = imp.summarise_unit(main["S2"])
    u["cf_total_t"] = u["iso3"].map(g1["cf_t"])
    u["cf_total_t_S2"] = u["iso3"].map(g2["cf_t"])
    u["excess_total_t_S1"] = u["iso3"].map(g1["excess_t"])
    u["excess_total_t_S2"] = u["iso3"].map(g2["excess_t"])
    u["pct_S1"] = u["iso3"].map(g1["pct"])
    u["pct_S2"] = u["iso3"].map(g2["pct"])
    for y in ("2023", "2024", "2025"):
        u[f"excess_{y}_S1"] = u["iso3"].map(by_year[y]) if y in by_year else np.nan
    pl = unit_pl.reindex(u["iso3"])
    for c in unit_pl.columns:
        u[c] = pl[c].values
    u["max_abs_placebo"] = pl.abs().max(axis=1).values
    u["robust"] = imp.robust(u["pct_S1"], u["pct_S2"], u["max_abs_placebo"]) & ~u["control"]
    u.loc[u["control"], "robust"] = False
    for spec, tr in main.items():
        if not np.isfinite(tr["excess_t"]).all():
            raise RuntimeError(f"{name}: non-finite excess in the main {spec} fit")
    return u, main, agg_pl, diags


def summary_row(name, u, main, agg, source, drop, last_pre):
    nc = u[~u["control"].astype(bool)]
    e1 = nc["excess_total_t_S1"]
    rob = nc["robust"].astype(bool)
    cf1 = main["S1"]["cf_t"].sum() if main is not None else nc["cf_total_t"].sum()
    cf2 = main["S2"]["cf_t"].sum() if main is not None else nc["cf_total_t_S2"].sum()
    x1, x2 = e1.sum(), nc["excess_total_t_S2"].sum()
    lo, hi = agg["pct"].min(), agg["pct"].max()
    return {"series": name, "source": source, "n_economies": len(u), "n_control": int(u["control"].sum()),
            "n_noncontrol": len(nc), "excluded_months": " ".join(drop) or "none", "last_pre_placebo": last_pre,
            "excess_Mt_S1": x1 / MT, "cf_Mt_S1": cf1 / MT, "pct_S1": 100 * x1 / cf1,
            "excess_Mt_S2": x2 / MT, "cf_Mt_S2": cf2 / MT, "pct_S2": 100 * x2 / cf2,
            "placebo_band_pct_min": lo, "placebo_band_pct_max": hi,
            "placebo_band_Mt_min_S1": lo * cf1 / 100 / MT, "placebo_band_Mt_max_S1": hi * cf1 / 100 / MT,
            "gross_gains_all_Mt": e1[e1 > 0].sum() / MT, "gross_losses_all_Mt": e1[e1 < 0].sum() / MT,
            "gross_gains_robust_Mt": e1[(e1 > 0) & rob].sum() / MT,
            "gross_losses_robust_Mt": e1[(e1 < 0) & rob].sum() / MT,
            "n_robust": int(rob.sum()), "n_robust_positive": int((rob & (e1 > 0)).sum()),
            "n_robust_negative": int((rob & (e1 < 0)).sum()),
            "robust_list": " ".join(sorted(nc.loc[rob, "iso3"]))}


def main():
    t0 = time.perf_counter()
    checks = []
    m = load_oecd_monthly("ALL_VESSELS")
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    R = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")["R"]
    grp = ex.set_index("iso3")[GROUPS].astype(bool)

    series, tw, notes = build_series(m, checks)
    # identity TER_TOT = TER_DOM + TER_INT, recomputed from the OECD extract
    tt = series["TER_TOT"].set_index(["iso3", "period"])["value_t"]
    re = tw.reindex(pd.MultiIndex.from_frame(series["TER_TOT"][["iso3", "period"]]))
    diff = float(np.max(np.abs(tt.to_numpy() - (re["TER_DOM"] + re["TER_INT"]).to_numpy())))
    checks.append({"check": "lfl_identity_ter_tot", "definition": "max |TER_TOT - (TER_DOM + TER_INT)| over the "
                   "TER_TOT panel, tonnes", "expected": "0", "obtained": f"{diff:.6g}", "abs_diff": f"{diff:.6g}",
                   "pass": diff == 0.0})

    flags, mons, sw = anomaly_scan(series)
    flags.to_csv(C.CHECKS / "like_for_like_anomaly_flags.csv", index=False)
    mons.to_csv(C.CHECKS / "like_for_like_anomaly_months.csv", index=False)
    for name in ("RES_INT", "TER_TOT"):
        f = flags[flags["series"] == name]
        checks.append(exact_check(f"lfl_{name}_scan_flags", f"{name}: flagged economy-months (RS-D14 scan)",
                                  "(report)", len(f)) | {"pass": True, "abs_diff": ""})
        checks.append(exact_check(f"lfl_{name}_scan_system_wide", f"{name}: system-wide anomalous months "
                                  "(excluded from estimation)", "(report)", " ".join(sw[name]) or "none")
                      | {"pass": True, "abs_diff": ""})

    expo, w, w_p = exposure(series, tw, sw, ex, pt, checks)
    expo_all = pd.concat(expo.values(), ignore_index=True)
    expo_all.to_csv(C.CHECKS / "like_for_like_exposure.csv", index=False)

    units, summ, aggs, panel_rows, run_rows = [], [], [], [], []
    for name in ("RES_INT", "TER_TOT"):
        t1 = time.perf_counter()
        drop = tuple(sw[name])
        pre_kept = [q for q in PRE if q not in drop]
        last_pre = pre_kept[-1]
        df = estimation_table(series[name], expo[name], R)
        u, main_tr, agg, diags = run_series(name, df, drop, last_pre, grp)
        u.insert(0, "series", name)
        units.append(u)
        summ.append(summary_row(name, u, main_tr, agg, "estimated (21_like_for_like.py)", drop, last_pre))
        agg.insert(0, "series", name)
        agg["excess_Mt"] = agg["excess_t"] / MT
        aggs.append(agg[["series", "spec", "placebo_date", "last_period", "pct", "excess_Mt"]])
        panel_rows.append(df.assign(series=name))
        run_rows.append({"series": name, "drop": " ".join(drop), "last_pre": last_pre, "weights_end": "2023-11",
                         "gamma_panama_S1": diags["S1"]["gamma"], "gamma_panama_S2": diags["S2"]["gamma"],
                         "weighted_r2_S1": diags["S1"]["weighted_r2"], "weighted_r2_S2": diags["S2"]["weighted_r2"]})
        checks.append(exact_check(f"lfl_{name}_placebo_runs", f"{name}: placebo runs (5 dates x S1, S2)", 10,
                                  len(agg)))
        checks.append(exact_check(f"lfl_{name}_finite", f"{name}: non-finite unit % among non-control economies", 0,
                                  int((~np.isfinite(u.loc[~u["control"], ["pct_S1", "pct_S2"]].to_numpy())).sum())))
        print(f"{name}: {len(u)} economies ({int(u['control'].sum())} controls), S1 {summ[-1]['excess_Mt_S1']:+.2f} Mt "
              f"({summ[-1]['pct_S1']:+.2f}%), S2 {summ[-1]['excess_Mt_S2']:+.2f} Mt ({summ[-1]['pct_S2']:+.2f}%), "
              f"robust {summ[-1]['n_robust']}: {summ[-1]['robust_list']} ({time.perf_counter() - t1:.1f} s)")

    # ---- reference rows from the existing outputs (not re-estimated) ----------
    ref_summ = pd.read_csv(TABLES / "rsd4_summary.csv").set_index(["principle", "spec"])
    ref_pl = pd.read_csv(TABLES / "rsd4_placebo_aggregate.csv")
    ref_units = {}
    for name, pr in MAIN_PRINCIPLE.items():
        u = pd.read_csv(TABLES / f"rsd4_{pr}_units.csv")
        ref_units[name] = u
        agg = ref_pl[ref_pl["principle"] == pr]
        drop = ("2023-11",) if pr == "departure" else ()
        row = summary_row(name, u, None, agg, f"reference: outputs/tables/rsd4_{pr}_units.csv, rsd4_summary.csv",
                          drop, m10.PRINCIPLES[pr]["last_pre"])
        # the totals in rsd4_summary.csv include no control excess (controls are untreated)
        for spec in ("S1", "S2"):
            checks.append({"check": f"lfl_reference_{name}_{spec}", "definition": f"{name} {spec}: sum of unit excess "
                           "(units file) equals rsd4_summary.csv excess_Mt", "expected": "agree",
                           "obtained": f"{row[f'excess_Mt_{spec}']:.6f} vs {ref_summ.loc[(pr, spec), 'excess_Mt']:.6f}",
                           "abs_diff": "", "pass": abs(row[f"excess_Mt_{spec}"] - ref_summ.loc[(pr, spec), "excess_Mt"])
                           < 1e-6})
        summ.append(row)
        aggs.append(agg.assign(series=name)[["series", "spec", "placebo_date", "last_period", "pct", "excess_Mt"]])

    # ---- the generic pipeline reproduces the stored main results (checks only) --
    pt10 = pt.copy()
    for name, pr in MAIN_PRINCIPLE.items():
        cfg = m10.PRINCIPLES[pr]
        df = m10.build_df(cfg, ex, pt10, R)
        u, _, _, _ = run_series(name, df, tuple(cfg["drop"]), cfg["last_pre"], grp)
        ref = ref_units[name].set_index("iso3")
        u = u.set_index("iso3").loc[ref.index]
        cols = ["pct_S1", "pct_S2", "max_abs_placebo", "excess_total_t_S1", "excess_total_t_S2"]
        a, b = u[cols].to_numpy(dtype=float), ref[cols].to_numpy(dtype=float)
        dmax = float(np.nanmax(np.abs(a - b) / np.maximum(1.0, np.abs(b))))
        same_rob = bool((u["robust"].astype(bool) == ref["robust"].astype(bool)).all())
        checks.append({"check": f"lfl_pipeline_reproduces_{name}", "definition": f"generic pipeline on the main "
                       f"{name} table: max relative difference of unit %, excess and max |placebo %| against "
                       f"rsd4_{pr}_units.csv (<= 1e-9), robust flags identical", "expected": "agree",
                       "obtained": f"{dmax:.3g}; robust identical {same_rob}", "abs_diff": f"{dmax:.3g}",
                       "pass": dmax <= 1e-9 and same_rob})

    # ---- write ---------------------------------------------------------------
    ref_cols = list(ref_units["RES_TOTAL"].columns)
    u_all = pd.concat(units, ignore_index=True)[["series"] + ref_cols]
    u_all.to_csv(TABLES / "like_for_like_units.csv", index=False)
    s = pd.DataFrame(summ).set_index("series").loc[SERIES_ORDER].reset_index()
    s.to_csv(TABLES / "like_for_like_summary.csv", index=False)
    a = pd.concat(aggs, ignore_index=True)
    a["series"] = pd.Categorical(a["series"], SERIES_ORDER, ordered=True)
    a.sort_values(["series", "spec", "placebo_date"]).to_csv(TABLES / "like_for_like_placebo_aggregate.csv",
                                                              index=False)

    # ---- pairs -----------------------------------------------------------------
    allu = {"RES_TOTAL": ref_units["RES_TOTAL"], "TER_INT": ref_units["TER_INT"],
            "RES_INT": units[0].drop(columns="series"), "TER_TOT": units[1].drop(columns="series")}
    pairs, psum = [], []
    for a_name, b_name in PAIRS:
        ua, ub = allu[a_name].set_index("iso3"), allu[b_name].set_index("iso3")
        both = sorted(set(ua.index) & set(ub.index))
        p = pd.DataFrame({"pair": f"{a_name} vs {b_name}", "iso3": both})
        p[GROUPS] = grp.reindex(both).to_numpy()
        for tag, uu, nm in (("a", ua, a_name), ("b", ub, b_name)):
            p[f"series_{tag}"] = nm
            p[f"control_{tag}"] = uu.loc[both, "control"].astype(bool).to_numpy()
            p[f"pct_S1_{tag}"] = uu.loc[both, "pct_S1"].to_numpy()
            p[f"excess_Mt_S1_{tag}"] = (uu.loc[both, "excess_total_t_S1"] / MT).to_numpy()
            p[f"robust_{tag}"] = uu.loc[both, "robust"].astype(bool).to_numpy()
        p["diff_pct_S1_a_minus_b"] = p["pct_S1_a"] - p["pct_S1_b"]
        pairs.append(p)
        nc = p[~p["control_a"] & ~p["control_b"]]
        top = nc.reindex(nc["diff_pct_S1_a_minus_b"].abs().sort_values(ascending=False).index).head(5)
        psum.append({"pair": f"{a_name} vs {b_name}", "n_in_both": len(p), "n_noncontrol_in_both": len(nc),
                     "pearson_pct_S1": nc["pct_S1_a"].corr(nc["pct_S1_b"]),
                     "spearman_pct_S1": nc["pct_S1_a"].corr(nc["pct_S1_b"], method="spearman"),
                     "n_same_sign": int((np.sign(nc["pct_S1_a"]) == np.sign(nc["pct_S1_b"])).sum()),
                     "n_robust_both": int((nc["robust_a"] & nc["robust_b"]).sum()),
                     "robust_both": " ".join(nc.loc[nc["robust_a"] & nc["robust_b"], "iso3"]),
                     "robust_a_only": " ".join(nc.loc[nc["robust_a"] & ~nc["robust_b"], "iso3"]),
                     "robust_b_only": " ".join(nc.loc[~nc["robust_a"] & nc["robust_b"], "iso3"]),
                     "largest_abs_diff": "; ".join(f"{r.iso3} {r.pct_S1_a:.2f} vs {r.pct_S1_b:.2f}"
                                                   for r in top.itertuples())})
    pd.concat(pairs, ignore_index=True).to_csv(TABLES / "like_for_like_pairs.csv", index=False)
    pd.DataFrame(psum).to_csv(TABLES / "like_for_like_pairs_summary.csv", index=False)

    # ---- interim inputs for 23_rolling_placebo.py ------------------------------
    pd.concat(panel_rows, ignore_index=True)[["series", "unit", "period", "days", "value_t", "per_day", "control",
                                              "P", "R"]].to_csv(C.INTERIM / "like_for_like_panel.csv.gz",
                                                                index=False, compression="gzip")
    pd.DataFrame(run_rows).to_csv(C.INTERIM / "like_for_like_runs.csv", index=False)

    for k, v in notes.items():
        print(f"{k} panel notes: {v}")
    for f in ("like_for_like_units.csv", "like_for_like_summary.csv", "like_for_like_pairs.csv",
              "like_for_like_pairs_summary.csv", "like_for_like_placebo_aggregate.csv"):
        print(f"{rel(TABLES / f)} written")
    update_checks(checks, CHECKS_FILE, "lfl_")
    print(f"Run time {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
