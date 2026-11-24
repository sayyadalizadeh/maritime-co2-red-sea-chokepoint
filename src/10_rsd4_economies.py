"""Economy-level excess emissions (RS-D4) with the RS-D15 estimator and RS-D16 placebos.

Per principle (residence: RES_TOTAL; departure: TER_INT), main window
2019-01..2025-10, economies of the RS-D10 panel with exposure data; control
economies from data/interim/exposure.csv. Departure drops 2023-11 (RS-D14).
Panama term: P (economy exposure) x R (restriction months).

Outputs
- data/interim/panama_term.csv, data/interim/panama_restriction.csv
- outputs/tables/rsd4_<principle>_units.csv, rsd4_<principle>_monthly.csv
- outputs/tables/rsd4_summary.csv, rsd4_placebo_aggregate.csv, rsd4_principles_compare.csv
- outputs/checks/estimation_checks.csv (rows starting with 'rsd4_')
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import exact_check, months, numeric_check, rel, require_verified, update_checks

imp = importlib.import_module("09_imputation")

TABLES = C.OUTPUTS / "tables"
MT = 1e6
R_EPISODE_START = "2023-01"
GROUPS = ["rsl", "cpa", "hq", "eea", "rus"]

PRINCIPLES = {
    "residence": dict(panel="panel_residence.csv.gz", exposure="e_res", control="control_res",
                      P="P_res", drop=(), last_pre="2023-11"),
    "departure": dict(panel="panel_departure.csv.gz", exposure="x_v", control="control_dep",
                      P="P_dep", drop=("2023-11",), last_pre="2023-10"),
}

REF = {
    "residence": dict(n=125, n_control=29, S1=("-28.76", "-1.63"), S2=("17.80", "1.04"),
                      placebo={"S1": ("1.24", "-0.50", "-2.06", "-2.14", "-2.36"),
                               "S2": ("1.43", "-2.13", "-3.35", "-2.45", "-1.28")},
                      robust="AZE BEL CHL GIN HKG JOR KAZ MAR MUS OMN SYC", units={}),
    "departure": dict(n=122, n_control=34, S1=("37.64", "3.75"), S2=("0.65", "0.06"),
                      placebo={"S1": ("-0.69", "-0.35", "2.39", "1.45", "2.12"),
                               "S2": ("-0.38", "-1.24", "2.74", "0.87", "0.51")},
                      robust="AZE EGY ESP IND LBN LKA MUS MYS SAU",
                      units={"EGY": "-27.91", "MYS": "32.14"}),
}


def panama_inputs(ex, checks):
    """Economy Panama exposure (P_res, P_dep) and the restriction indicator R."""
    v3 = pd.read_csv(C.V3_SHARES)
    v3_iso = set(v3["iso3"])
    px = v3[(v3["chokepoint"] == "Panama Canal") & (v3["direction"] == "export")].set_index("iso3")
    pm = v3[(v3["chokepoint"] == "Panama Canal") & (v3["direction"] == "import")].set_index("iso3")
    w_p = px["v_canal"].sum() / px["v_sea_predict"].sum()
    checks.append(numeric_check("rsd4_w_P", "Sum v_canal / sum v_sea_predict, Panama Canal rows, v3 export file",
                                "0.0675", w_p, 4, tol=0.0001))

    pt = ex[["iso3", "A", "B", "D", "E", "F"]].copy()
    in_v3 = pt["iso3"].isin(v3_iso)
    pt["x_P"] = pt["iso3"].map(px["share_v"]).where(~in_v3, pt["iso3"].map(px["share_v"]).fillna(0.0))
    pt["m_P"] = pt["iso3"].map(pm["share_v"]).where(~in_v3, pt["iso3"].map(pm["share_v"]).fillna(0.0))
    denom = pt[["A", "B", "D", "E", "F"]].sum(axis=1).replace(0, np.nan)
    pt["P_res"] = (pt["D"] * pt["x_P"] + pt["E"] * pt["m_P"] + pt["F"] * w_p) / denom
    pt["P_dep"] = pt["x_P"]
    pt["in_v3"] = in_v3
    pt = pt[["iso3", "in_v3", "x_P", "m_P", "P_res", "P_dep"]]
    pt.to_csv(C.INTERIM / "panama_term.csv", index=False)
    print(f"{rel(C.INTERIM / 'panama_term.csv')}: {len(pt)} economies; w_P = {w_p:.4f}")

    require_verified(C.PORTWATCH_FILE)
    pw = pd.read_csv(C.PORTWATCH_MONTHLY)
    pan = pw[pw["portname"] == "Panama Canal"].set_index("period")["n_total_per_day_mean"].sort_index()
    base = pan[pan.index.isin(months(C.PRE_START, C.PRE_END))].mean()
    below = pan < 0.9 * base
    # RS-D15: the 2023-2024 drought-restriction episode (months from 2023-01 on, up to 2025-10).
    # R_all: the ratio rule over all months (robustness variant R1).
    r = pd.DataFrame({"period": pan.index, "n_total_per_day_mean": pan.values,
                      "ratio_to_pre_mean": (pan / base).values,
                      "below_0_90": below.astype(int).values,
                      "R": (below & (pan.index >= R_EPISODE_START) & (pan.index <= C.MAIN_END)).astype(int).values,
                      "R_all": below.astype(int).values})
    r.to_csv(C.INTERIM / "panama_restriction.csv", index=False)
    r_months = r.loc[r["R"] == 1, "period"].tolist()
    checks.append(exact_check("rsd4_panama_months", "Months 2023-01..2025-10 with Panama Canal mean daily n_total "
                              "< 0.90 x its 2019-01..2023-11 mean (RS-D15)",
                              ";".join(months("2023-11", "2024-07")), ";".join(r_months)))
    print(f"{rel(C.INTERIM / 'panama_restriction.csv')}: R = 1 in {r_months[0]}..{r_months[-1]} ({len(r_months)} months)")
    return pt.set_index("iso3"), r.set_index("period")["R"]


def build_df(cfg, ex, pt, R):
    """Estimation table for one principle: main window, economies with exposure data."""
    p = pd.read_csv(C.INTERIM / cfg["panel"])
    p = p[p["in_main_window"]]
    keep = ex.loc[ex[cfg["exposure"]].notna(), "iso3"]
    p = p[p["iso3"].isin(keep)]
    df = pd.DataFrame({"unit": p["iso3"], "period": p["period"], "days": p["days"],
                       "value_t": p["value_t"], "per_day": p["per_day"]})
    df["control"] = df["unit"].map(ex.set_index("iso3")[cfg["control"]]).astype(bool)
    df["P"] = df["unit"].map(pt[cfg["P"]])
    df["R"] = df["period"].map(R).fillna(0).astype(int)
    return df


def run_principle(name, cfg, ex, pt, R, checks):
    t0 = time.perf_counter()
    df = build_df(cfg, ex, pt, R)

    main, diags, weights = {}, [], None
    for spec in imp.SPECS:
        tr, dg, wts = imp.fit_impute(df, shock=C.SHOCK_START, drop=cfg["drop"], last=C.MAIN_END,
                                     spec=spec, panama=True, dense_check=True)
        main[spec] = tr
        diags.append({"principle": name, "run": "main", **dg})
        weights = wts
    unit_pl, agg_pl = imp.placebo_runs(df, last_pre=cfg["last_pre"], drop=cfg["drop"], panama=True)

    # ---- units ------------------------------------------------------------
    econ = sorted(df["unit"].unique())
    u = pd.DataFrame({"iso3": econ})
    u = u.merge(ex[["iso3"] + GROUPS], on="iso3", how="left")
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
    u.to_csv(TABLES / f"rsd4_{name}_units.csv", index=False)

    # ---- monthly ------------------------------------------------------------
    mon = pd.DataFrame({
        "excess_t_S1": main["S1"].groupby("period")["excess_t"].sum(),
        "excess_t_S2": main["S2"].groupby("period")["excess_t"].sum(),
        "cf_t_S1": main["S1"].groupby("period")["cf_t"].sum()}).reset_index()
    mon.to_csv(TABLES / f"rsd4_{name}_monthly.csv", index=False)

    # ---- summary ------------------------------------------------------------
    rows = []
    band_lo, band_hi = agg_pl["pct"].min(), agg_pl["pct"].max()
    treated = u[~u["control"]]
    for spec, dg in zip(imp.SPECS, diags):
        tr = main[spec]
        tot, cf = tr["excess_t"].sum(), tr["cf_t"].sum()
        yr = tr.groupby(tr["period"].str[:4])["excess_t"].sum()
        ex_u = treated[f"excess_total_t_{spec}"]
        rob = treated["robust"]
        rows.append({
            "principle": name, "spec": spec, "n_economies": len(u), "n_control": int(u["control"].sum()),
            "excess_Mt": tot / MT, "cf_Mt": cf / MT, "pct": imp.pct(tot, cf),
            "excess_2023_Mt": yr.get("2023", 0) / MT, "excess_2024_Mt": yr.get("2024", 0) / MT,
            "excess_2025_Mt": yr.get("2025", 0) / MT,
            "placebo_band_pct_min": band_lo, "placebo_band_pct_max": band_hi,
            "placebo_band_Mt_min": band_lo * cf / 100 / MT, "placebo_band_Mt_max": band_hi * cf / 100 / MT,
            "gross_gains_all_Mt": ex_u[ex_u > 0].sum() / MT, "gross_losses_all_Mt": ex_u[ex_u < 0].sum() / MT,
            "gross_gains_robust_Mt": ex_u[(ex_u > 0) & rob].sum() / MT,
            "gross_losses_robust_Mt": ex_u[(ex_u < 0) & rob].sum() / MT,
            "n_robust": int(rob.sum()),
            "n_robust_positive": int((rob & (treated["excess_total_t_S1"] > 0)).sum()),
            "n_robust_negative": int((rob & (treated["excess_total_t_S1"] < 0)).sum()),
            "weighted_r2": dg["weighted_r2"], "rmse_log": dg["rmse_log"], "n_untreated": dg["n_untreated"],
            "n_treated": dg["n_treated"], "n_params": dg["n_params"], "gamma_panama": dg["gamma"],
            "solver_rel_residual": dg["solver_rel_residual"],
            "dense_max_abs_fitted_diff": dg.get("dense_max_abs_fitted_diff", np.nan),
        })
    agg_pl.insert(0, "principle", name)
    agg_pl["excess_Mt"] = agg_pl["excess_t"] / MT

    # ---- checks -------------------------------------------------------------
    ref = REF[name]
    d = f"RS-D4 {name}"
    checks.append(exact_check(f"rsd4_{name}_n_economies", f"{d}: economies with exposure data", ref["n"], len(u)))
    checks.append(exact_check(f"rsd4_{name}_n_control", f"{d}: control economies", ref["n_control"],
                              int(u["control"].sum())))
    for spec in imp.SPECS:
        r = next(x for x in rows if x["spec"] == spec)
        checks.append(numeric_check(f"rsd4_{name}_{spec}_Mt", f"{d}: total excess {spec}, Mt", ref[spec][0],
                                    r["excess_Mt"], 2, tol=0.05))
        checks.append(numeric_check(f"rsd4_{name}_{spec}_pct", f"{d}: total excess {spec}, %", ref[spec][1],
                                    r["pct"], 2, tol=0.02))
        for date, e in zip(imp.PLACEBO_DATES, ref["placebo"][spec]):
            v = agg_pl.loc[(agg_pl["spec"] == spec) & (agg_pl["placebo_date"] == date), "pct"].iloc[0]
            checks.append(numeric_check(f"rsd4_{name}_placebo_{date}_{spec}", f"{d}: aggregate placebo %, {date}, {spec}",
                                        e, v, 2, tol=0.02))
    got = " ".join(sorted(u.loc[u["robust"], "iso3"]))
    checks.append(exact_check(f"rsd4_{name}_robust", f"{d}: robust economies (RS-D16)", ref["robust"], got))
    for iso, e in ref["units"].items():
        checks.append(numeric_check(f"rsd4_{name}_{iso}_S1_Mt", f"{d}: {iso} total excess S1, Mt", e,
                                    g1["excess_t"].get(iso, np.nan) / MT, 2, tol=0.05))

    print(f"{name}: {len(u)} economies ({int(u['control'].sum())} controls), "
          f"S1 {rows[0]['excess_Mt']:+.2f} Mt ({rows[0]['pct']:+.2f}%), "
          f"S2 {rows[1]['excess_Mt']:+.2f} Mt ({rows[1]['pct']:+.2f}%), robust {rows[0]['n_robust']}; "
          f"{time.perf_counter() - t0:.1f} s")
    return u, rows, agg_pl, diags


def main():
    t0 = time.perf_counter()
    TABLES.mkdir(parents=True, exist_ok=True)
    checks = []
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt, R = panama_inputs(ex, checks)

    units, summary, placebo, diags = {}, [], [], []
    for name, cfg in PRINCIPLES.items():
        u, rows, agg, dg = run_principle(name, cfg, ex, pt, R, checks)
        units[name] = u
        summary += rows
        placebo.append(agg)
        diags += dg

    pd.DataFrame(summary).to_csv(TABLES / "rsd4_summary.csv", index=False)
    pd.concat(placebo, ignore_index=True)[["principle", "spec", "placebo_date", "last_period", "pct", "excess_Mt"]] \
        .to_csv(TABLES / "rsd4_placebo_aggregate.csv", index=False)

    r, d = units["residence"].set_index("iso3"), units["departure"].set_index("iso3")
    both = sorted(set(r.index) & set(d.index))
    cmp = pd.DataFrame({"iso3": both})
    for name, t in (("res", r), ("dep", d)):
        cmp[f"control_{name}"] = cmp["iso3"].map(t["control"])
        cmp[f"excess_Mt_S1_{name}"] = cmp["iso3"].map(t["excess_total_t_S1"]) / MT
        cmp[f"pct_S1_{name}"] = cmp["iso3"].map(t["pct_S1"])
        cmp[f"robust_{name}"] = cmp["iso3"].map(t["robust"])
    cmp = cmp.merge(ex[["iso3"] + GROUPS], on="iso3", how="left")
    cmp.to_csv(TABLES / "rsd4_principles_compare.csv", index=False)

    pd.DataFrame(diags).to_csv(C.CHECKS / "rsd4_fit_diagnostics.csv", index=False)
    for f in ("rsd4_residence_units.csv", "rsd4_departure_units.csv", "rsd4_residence_monthly.csv",
              "rsd4_departure_monthly.csv", "rsd4_summary.csv", "rsd4_placebo_aggregate.csv",
              "rsd4_principles_compare.csv"):
        print(f"{rel(TABLES / f)} written")
    update_checks(checks, C.CHECKS / "estimation_checks.csv", "rsd4_")
    print(f"Run time: {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
