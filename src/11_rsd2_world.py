"""System-level excess emissions by ship type (RS-D2) with the RS-D15 estimator and RS-D16 placebos.

World (W) RES_TOTAL by ship type, per-day values, 2019-01..2025-10; 18 types
(CRUISE excluded and described only). No Panama term.
- main: transit types treated, non-transit types as controls;
- B1: CONTAINER treated, all other 17 types as controls (comparison only).

Outputs
- outputs/tables/rsd2_types.csv, rsd2_monthly.csv, rsd2_summary.csv, rsd2_placebo_aggregate.csv
- outputs/checks/estimation_checks.csv (rows starting with 'rsd2_')
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import numeric_check, rel, update_checks

imp = importlib.import_module("09_imputation")

TABLES = C.OUTPUTS / "tables"
MT = 1e6
TRANSIT = ["CONTAINER", "BULK_CARRIER", "OIL_TANKER", "CHEM_TANKER", "GEN_CARGO", "LIQ_GAS_TANKER",
           "VEHICLE", "RO_RO", "REFRIG_BULK", "OTHER_LIQ_TANKER"]
NON_TRANSIT = ["FERRY_ROPAX", "OFFSHORE", "MISC_OTHER", "MISC_FISH", "SERVICE_TUG", "FERRY_PAX",
               "YACHT", "SERVICE_OTHER"]
EXCLUDED = ["CRUISE"]
LAST_PRE = "2023-11"
PANAMA_NORMAL = ("2024-08", "2025-10")

REF = {
    "main": dict(S1=("41.03", "2.62"), S2=("29.50", "1.87"),
                 years={"2023": "0.40", "2024": "21.08", "2025": "19.55"}, container="39.95",
                 placebo={"S1": ("3.61", "0.17", "-0.93", "-0.74", "-0.77"),
                          "S2": ("-0.66", "-5.82", "-5.81", "-3.50", "-2.59")}),
    "B1": dict(S1=("39.50", "9.06"), S2=("55.04", "13.09"), years={}, container=None,
               placebo={"S1": ("5.05", "1.74", "-0.61", "-5.05", "-6.13"),
                        "S2": ("10.23", "-0.75", "-3.82", "-7.36", "-7.27")}),
}


def main():
    t0 = time.perf_counter()
    TABLES.mkdir(parents=True, exist_ok=True)
    checks = []
    w_all = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w_all[(w_all["period"] >= C.PRE_START) & (w_all["period"] <= C.MAIN_END)]
    base = w[w["vessel"].isin(TRANSIT + NON_TRANSIT)].rename(columns={"vessel": "unit"})
    assert base["unit"].nunique() == 18

    runs = {"main": set(TRANSIT), "B1": {"CONTAINER"}}
    summary, placebo, monthly, diags, type_tables = [], [], {}, [], {}
    for run, treated_types in runs.items():
        df = base.copy()
        df["control"] = ~df["unit"].isin(treated_types)
        main_tr = {}
        for spec in imp.SPECS:
            tr, dg, wts = imp.fit_impute(df, shock=C.SHOCK_START, last=C.MAIN_END, spec=spec, dense_check=True)
            main_tr[spec] = tr
            diags.append({"run": run, **dg})
        unit_pl, agg_pl = imp.placebo_runs(df, last_pre=LAST_PRE)
        band_lo, band_hi = agg_pl["pct"].min(), agg_pl["pct"].max()
        max_abs_agg = agg_pl["pct"].abs().max()

        # per type
        g1, by_year = imp.summarise_unit(main_tr["S1"])
        g2, _ = imp.summarise_unit(main_tr["S2"])
        t = pd.DataFrame({"vessel": sorted(treated_types)})
        t["weight"] = t["vessel"].map(wts)
        t["cf_total_t"] = t["vessel"].map(g1["cf_t"])
        for spec, g in (("S1", g1), ("S2", g2)):
            t[f"excess_total_t_{spec}"] = t["vessel"].map(g["excess_t"])
            t[f"pct_{spec}"] = t["vessel"].map(g["pct"])
        for y in ("2023", "2024", "2025"):
            t[f"excess_{y}_S1"] = t["vessel"].map(by_year[y])
        pl = unit_pl.reindex(t["vessel"])
        for c in unit_pl.columns:
            t[c] = pl[c].values
        t["max_abs_placebo"] = pl.abs().max(axis=1).values
        t["robust"] = imp.robust(t["pct_S1"], t["pct_S2"], t["max_abs_placebo"]).values
        type_tables[run] = t

        monthly[run] = pd.DataFrame({f"excess_t_S1_{run}": main_tr["S1"].groupby("period")["excess_t"].sum(),
                                     f"excess_t_S2_{run}": main_tr["S2"].groupby("period")["excess_t"].sum()})

        tot = {s: main_tr[s]["excess_t"].sum() for s in imp.SPECS}
        cf = {s: main_tr[s]["cf_t"].sum() for s in imp.SPECS}
        pcts = {s: imp.pct(tot[s], cf[s]) for s in imp.SPECS}
        total_robust = bool(np.sign(pcts["S1"]) == np.sign(pcts["S2"])
                            and min(abs(pcts["S1"]), abs(pcts["S2"])) > max_abs_agg)
        for spec, dg in zip(imp.SPECS, diags[-2:]):
            tr = main_tr[spec]
            yr = tr.groupby(tr["period"].str[:4])["excess_t"].sum()
            pn = tr[(tr["period"] >= PANAMA_NORMAL[0]) & (tr["period"] <= PANAMA_NORMAL[1])]["excess_t"].sum()
            summary.append({
                "run": run, "spec": spec, "treated_types": " ".join(sorted(treated_types)),
                "excess_Mt": tot[spec] / MT, "cf_Mt": cf[spec] / MT, "pct": pcts[spec],
                "excess_2023_Mt": yr.get("2023", 0) / MT, "excess_2024_Mt": yr.get("2024", 0) / MT,
                "excess_2025_Mt": yr.get("2025", 0) / MT,
                "placebo_band_pct_min": band_lo, "placebo_band_pct_max": band_hi,
                "placebo_band_Mt_min": band_lo * cf[spec] / 100 / MT, "placebo_band_Mt_max": band_hi * cf[spec] / 100 / MT,
                "max_abs_placebo_pct": max_abs_agg, "total_robust": total_robust,
                "excess_panama_normal_Mt": pn / MT,
                "weighted_r2": dg["weighted_r2"], "rmse_log": dg["rmse_log"], "n_untreated": dg["n_untreated"],
                "n_treated": dg["n_treated"], "n_params": dg["n_params"],
                "solver_rel_residual": dg["solver_rel_residual"],
                "dense_max_abs_fitted_diff": dg["dense_max_abs_fitted_diff"],
            })
        agg_pl.insert(0, "run", run)
        agg_pl["excess_Mt"] = agg_pl["excess_t"] / MT
        placebo.append(agg_pl)

        ref = REF[run]
        d = f"RS-D2 {run}"
        for spec in imp.SPECS:
            checks.append(numeric_check(f"rsd2_{run}_{spec}_Mt", f"{d}: total excess {spec}, Mt",
                                        ref[spec][0], tot[spec] / MT, 2, tol=0.05))
            checks.append(numeric_check(f"rsd2_{run}_{spec}_pct", f"{d}: total excess {spec}, %",
                                        ref[spec][1], pcts[spec], 2, tol=0.02))
            for date, e in zip(imp.PLACEBO_DATES, ref["placebo"][spec]):
                v = agg_pl.loc[(agg_pl["spec"] == spec) & (agg_pl["placebo_date"] == date), "pct"].iloc[0]
                checks.append(numeric_check(f"rsd2_{run}_placebo_{date}_{spec}",
                                            f"{d}: aggregate placebo %, {date}, {spec}", e, v, 2, tol=0.02))
        yr1 = main_tr["S1"].groupby(main_tr["S1"]["period"].str[:4])["excess_t"].sum() / MT
        for y, e in ref["years"].items():
            checks.append(numeric_check(f"rsd2_{run}_S1_{y}_Mt", f"{d}: excess S1 in {y}, Mt", e, yr1.get(y), 2, tol=0.05))
        if ref["container"]:
            checks.append(numeric_check(f"rsd2_{run}_S1_CONTAINER_Mt", f"{d}: CONTAINER excess S1, Mt",
                                        ref["container"], g1["excess_t"]["CONTAINER"] / MT, 2, tol=0.05))
        print(f"{run}: S1 {tot['S1'] / MT:+.2f} Mt ({pcts['S1']:+.2f}%), S2 {tot['S2'] / MT:+.2f} Mt "
              f"({pcts['S2']:+.2f}%), placebo band {band_lo:.2f}..{band_hi:.2f}%, total robust {total_robust}")

    type_tables["main"].to_csv(TABLES / "rsd2_types.csv", index=False)
    type_tables["B1"].to_csv(TABLES / "rsd2_types_B1.csv", index=False)
    mon = pd.concat(monthly.values(), axis=1).reset_index().rename(columns={"index": "period"})
    mon.to_csv(TABLES / "rsd2_monthly.csv", index=False)
    pd.DataFrame(summary).to_csv(TABLES / "rsd2_summary.csv", index=False)
    pd.concat(placebo, ignore_index=True)[["run", "spec", "placebo_date", "last_period", "pct", "excess_Mt"]] \
        .to_csv(TABLES / "rsd2_placebo_aggregate.csv", index=False)
    pd.DataFrame(diags).to_csv(C.CHECKS / "rsd2_fit_diagnostics.csv", index=False)

    # Cruise: description only (calendar-year totals from the full series)
    cr = w_all[w_all["vessel"] == "CRUISE"]
    cruise = cr.groupby(cr["period"].str[:4])["value_t"].agg(["sum", "count"]).reset_index()
    cruise.columns = ["year", "res_total_t", "n_months"]
    cruise = cruise[cruise["year"].isin(["2023", "2024", "2025"])]
    cruise["res_total_Mt"] = cruise["res_total_t"] / MT
    cruise.to_csv(TABLES / "rsd2_cruise.csv", index=False)

    for f in ("rsd2_types.csv", "rsd2_types_B1.csv", "rsd2_monthly.csv", "rsd2_summary.csv",
              "rsd2_placebo_aggregate.csv", "rsd2_cruise.csv"):
        print(f"{rel(TABLES / f)} written")
    update_checks(checks, C.CHECKS / "estimation_checks.csv", "rsd2_")
    print(f"Run time {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
