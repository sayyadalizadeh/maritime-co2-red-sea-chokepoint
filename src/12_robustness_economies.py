"""Robustness variants for the economy-level estimates (RS-D4), using 09_imputation unchanged.

Variants (each changes only what is stated):
  R0  none (main)                                   both        full
  R1  R from the ratio rule over all months         both        full
  R2  EEA economies dropped                         both        full
  R3  2020-01..2021-12 dropped                      both        full, placebo dates 2022-06 and 2022-12
  R4  2021-11..2022-10 dropped                      departure   full
  R5  2023-11 kept                                  departure   full
  R6  2023-09..2023-11 dropped                      departure   full
  R7  isolated anomaly flags (main scan) dropped    both        full
  R8  RUS dropped                                   both        full
  R9  quantity-based exposure and control pools     both        full
  R10 ALL_VESSELSXMISC_FISH values                  both        full
  R11 window 2019-01..2026-02                       residence   full
  R12 R0 excess without 2025-09                     both        no new estimation
  R13 R0 excess over 2024-08..2025-10               both        no new estimation
  R14 leave-one-out, 10 largest-weight non-controls both        main only

"Full" = S1 and S2, the placebo runs and the RS-D16 robust classification.

Outputs
- outputs/tables/robustness_economies.csv
- outputs/tables/robustness_robust_changes.csv
- outputs/checks/robustness_r9_pools.csv
- outputs/checks/robustness_checks.csv
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import exact_check, months, numeric_check, rel, run_variant, write_checks

m10 = importlib.import_module("10_rsd4_economies")

TABLES = C.OUTPUTS / "tables"
MT = 1e6
KEY = {"departure": ["EGY", "SAU", "MYS", "IND", "LKA", "ESP", "MUS", "USA", "CHN"],
       "residence": ["HKG", "CHE", "DNK", "CHN", "BEL", "SYC", "USA", "JPN", "GRC"]}
EXCLUDED_FROM_POOL = ("rsl", "cpa", "hq", "rus")
HQ_VARIANT_CODES = ("JPN", "SGP", "HKG")


def make_df(principle, ex, pt, R, value_col="value_t", keep=None, control=None, window="main",
            exclude_rows=None):
    """Estimation table for one principle with optional changes."""
    cfg = m10.PRINCIPLES[principle]
    p = pd.read_csv(C.INTERIM / cfg["panel"])
    p = p[p["in_main_window"] if window == "main" else p["in_sens_window"]]
    if keep is None:
        keep = set(ex.loc[ex[cfg["exposure"]].notna(), "iso3"])
    p = p[p["iso3"].isin(keep)]
    if exclude_rows is not None:
        key = set(exclude_rows)
        p = p[[(i, q) not in key for i, q in zip(p["iso3"], p["period"])]]
    if control is None:
        control = ex.set_index("iso3")[cfg["control"]]
    df = pd.DataFrame({"unit": p["iso3"], "period": p["period"], "days": p["days"],
                       "value_t": p[value_col], "per_day": p[value_col] / p["days"]})
    df["control"] = df["unit"].map(control).fillna(False).astype(bool)
    df["P"] = df["unit"].map(pt[cfg["P"]])
    df["R"] = df["period"].map(R).fillna(0).astype(int)
    return df


def quantity_exposure(ex, checks):
    """R9: quantity-based exposure and control pools (RS-D4 rule)."""
    v3 = pd.read_csv(C.V3_SHARES)
    sx = v3[(v3["chokepoint"] == "Suez Canal") & (v3["direction"] == "export")].set_index("iso3")
    sm = v3[(v3["chokepoint"] == "Suez Canal") & (v3["direction"] == "import")].set_index("iso3")
    w_q = sx["q_canal"].sum() / sx["q_sea_predict"].sum()
    checks.append(numeric_check("w_q", "Sum q_canal / sum q_sea_predict, Suez Canal rows, v3 export file",
                                "0.1287", w_q, 4, tol=0.0001))
    q = ex[["iso3", "x_q", "A", "B", "D", "E", "F", "in_res_panel", "in_dep_panel", "rsl", "cpa", "hq", "rus"]].copy()
    q["m_q"] = q["iso3"].map(sm["share_q"])
    denom = q[["A", "B", "D", "E", "F"]].sum(axis=1).replace(0, np.nan)
    q["e_res_q"] = (q["D"] * q["x_q"] + q["E"] * q["m_q"] + q["F"] * w_q) / denom
    excluded = q[list(EXCLUDED_FROM_POOL)].any(axis=1)
    rows = []
    for principle, col, panel_col in (("residence", "e_res_q", "in_res_panel"), ("departure", "x_q", "in_dep_panel")):
        base = q[q[panel_col] & q[col].notna()]
        cut = base[col].quantile(1 / 3)
        pool = q[panel_col] & q[col].notna() & (q[col] <= cut) & ~excluded
        q[f"control_q_{principle[:3]}"] = pool
        old = ex.set_index("iso3")["control_res" if principle == "residence" else "control_dep"]
        new_set, old_set = set(q.loc[pool, "iso3"]), set(old[old].index)
        rows.append({"principle": principle, "exposure": col, "n_with_exposure": len(base), "cutoff": cut,
                     "pool_size": len(new_set), "pool": " ".join(sorted(new_set)),
                     "entered_vs_value_pool": " ".join(sorted(new_set - old_set)),
                     "left_vs_value_pool": " ".join(sorted(old_set - new_set))})
    pools = pd.DataFrame(rows)
    pools.to_csv(C.CHECKS / "robustness_r9_pools.csv", index=False)
    print(f"{rel(C.CHECKS / 'robustness_r9_pools.csv')}: " +
          "; ".join(f"{r.principle} {r.pool_size} (cut-off {r.cutoff:.4f})" for r in pools.itertuples()))
    return q.set_index("iso3"), pools


def record(variant, principle, res, description, extra=None):
    """Rows (one per spec) of robustness_economies.csv for one estimated variant."""
    rows = []
    u, agg = res["units"], res["placebo"]
    if agg is not None:
        rob = u[u["robust"]]
        robust_list = " ".join(sorted(rob.index))
        n_pos, n_neg = int((rob["excess_t_S1"] > 0).sum()), int((rob["excess_t_S1"] < 0).sum())
        lo, hi = agg["pct"].min(), agg["pct"].max()
        dates = " ".join(sorted(agg["placebo_date"].unique()))
    else:
        robust_list, n_pos, n_neg, lo, hi, dates = "", np.nan, np.nan, np.nan, np.nan, ""
    for spec in ("S1", "S2"):
        tr = res["main"][spec]
        tot, cf = tr["excess_t"].sum(), tr["cf_t"].sum()
        row = {"variant": variant, "principle": principle, "spec": spec, "description": description,
               "n_economies": res["diags"][spec]["n_units"], "n_control": res["diags"][spec]["n_control_units"],
               "first_treated": tr["period"].min(), "last_treated": tr["period"].max(),
               "excess_Mt": tot / MT, "cf_Mt": cf / MT, "pct": 100 * tot / cf,
               "placebo_dates": dates, "placebo_band_pct_min": lo, "placebo_band_pct_max": hi,
               "placebo_band_Mt_min": lo * cf / 100 / MT, "placebo_band_Mt_max": hi * cf / 100 / MT,
               "n_robust": (n_pos + n_neg) if agg is not None else np.nan,
               "n_robust_positive": n_pos, "n_robust_negative": n_neg, "robust_list": robust_list,
               "cells_not_imputable_main": res["removed"]["main"],
               "cells_not_imputable_placebo": " ".join(f"{k}:{v}" for k, v in res["removed"].items()
                                                       if k != "main" and v)}
        for iso in KEY[principle]:
            row[f"excess_Mt_{iso}"] = u[f"excess_t_{spec}"].get(iso, np.nan) / MT
        row.update(extra or {})
        rows.append(row)
    return rows


def sum_rows(variant, principle, r0, mask_fn, description):
    """Rows for variants that re-sum R0 excess over a subset of months (no new estimation)."""
    rows = []
    for spec in ("S1", "S2"):
        tr = r0["main"][spec]
        t = tr[mask_fn(tr["period"])]
        g = t.groupby("unit")["excess_t"].sum()
        row = {"variant": variant, "principle": principle, "spec": spec, "description": description,
               "n_economies": r0["diags"][spec]["n_units"], "n_control": r0["diags"][spec]["n_control_units"],
               "first_treated": t["period"].min(), "last_treated": t["period"].max(),
               "excess_Mt": t["excess_t"].sum() / MT, "cf_Mt": t["cf_t"].sum() / MT,
               "pct": 100 * t["excess_t"].sum() / t["cf_t"].sum()}
        for iso in KEY[principle]:
            row[f"excess_Mt_{iso}"] = g.get(iso, np.nan) / MT
        rows.append(row)
    return rows


def main():
    t_all = time.perf_counter()
    TABLES.mkdir(parents=True, exist_ok=True)
    checks, out, changes, times = [], [], [], []
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    rr = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")
    R, R_all = rr["R"], rr["R_all"]
    R_sens = ((rr["below_0_90"] == 1) & (rr.index >= m10.R_EPISODE_START)
              & (rr.index <= C.SENS_END_RESIDENCE)).astype(int)
    checks.append(exact_check("R_months", "R = 1 (RS-D15 episode)", ";".join(months("2023-11", "2024-07")),
                              ";".join(R[R == 1].index)))
    checks.append(exact_check("R1_months", "R1: R = 1 under the ratio rule, months up to 2025-10", "(report)",
                              ";".join(R_all[(R_all == 1) & (R_all.index <= C.MAIN_END)].index))
                  | {"pass": True, "abs_diff": ""})
    checks.append(exact_check("R11_months", "R11: R = 1 under the RS-D15 rule, months 2023-01..2026-02",
                              ";".join(months("2023-11", "2024-07")), ";".join(R_sens[R_sens == 1].index)))
    q, pools = quantity_exposure(ex, checks)

    # HQ variants of RS-D3(c): do JPN, SGP or HKG sit in any control pool?
    in_pool = []
    for col, frame in (("control_res", ex.set_index("iso3")), ("control_dep", ex.set_index("iso3")),
                       ("control_q_res", q), ("control_q_dep", q)):
        in_pool += [f"{c} ({col})" for c in HQ_VARIANT_CODES if c in frame.index and bool(frame.loc[c, col])]
    checks.append(exact_check("hq_variants_in_pool", "JPN, SGP or HKG in a control pool (value or quantity)",
                              "(report)", "; ".join(in_pool) or "none") | {"pass": True, "abs_diff": ""})
    hq_run = bool(in_pool)
    print("HQ variants: " + ("JPN/SGP/HKG in a pool: " + "; ".join(in_pool) if hq_run
                             else "none of JPN, SGP, HKG is in a control pool; variants not run"))

    flags = pd.read_csv(C.CHECKS / "anomaly_flags.csv")
    mon = pd.read_csv(C.CHECKS / "anomaly_months.csv")

    for principle, cfg in m10.PRINCIPLES.items():
        drop, last_pre = tuple(cfg["drop"]), cfg["last_pre"]
        variants = []

        def add(vid, desc, df, **kw):
            variants.append((vid, desc, df, kw))

        df0 = make_df(principle, ex, pt, R)
        add("R0", "main (corrected R)", df0, drop=drop, last_pre=last_pre)
        add("R1", "R from the ratio rule over all months", make_df(principle, ex, pt, R_all), drop=drop, last_pre=last_pre)
        eea = set(ex.loc[ex["eea"], "iso3"])
        add("R2", "EEA economies dropped", df0[~df0["unit"].isin(eea)], drop=drop, last_pre=last_pre)
        add("R3", "2020-01..2021-12 dropped; placebo dates 2022-06, 2022-12", df0,
            drop=drop + tuple(months(*C.COVID_EXCL)), last_pre=last_pre, placebo_dates=("2022-06", "2022-12"))
        if principle == "departure":
            add("R4", "2021-11..2022-10 dropped", df0, drop=drop + tuple(months(*C.RECLASS_2022_EXCL)), last_pre=last_pre)
            add("R5", "2023-11 kept (placebo data to 2023-11)", df0, drop=(), last_pre="2023-11")
            add("R6", "2023-09..2023-11 dropped (placebo data to 2023-08)", df0,
                drop=tuple(months("2023-09", "2023-11")), last_pre="2023-08")
        sw = set(mon.loc[(mon["principle"] == principle) & (mon["window"] == "main") & mon["system_wide"], "period"])
        iso_flags = flags[(flags["principle"] == principle) & (flags["window"] == "main") & ~flags["period"].isin(sw)]
        add("R7", f"isolated anomaly flags dropped ({len(iso_flags)} economy-months in the panel scan)",
            make_df(principle, ex, pt, R, exclude_rows=zip(iso_flags["iso3"], iso_flags["period"])),
            drop=drop, last_pre=last_pre)
        add("R8", "RUS dropped", df0[df0["unit"] != "RUS"], drop=drop, last_pre=last_pre)
        qcol = "e_res_q" if principle == "residence" else "x_q"
        add("R9", "quantity-based exposure and control pools",
            make_df(principle, ex, pt, R, keep=set(q.index[q[qcol].notna()]),
                    control=q[f"control_q_{principle[:3]}"]),
            drop=drop, last_pre=last_pre)
        add("R10", "ALL_VESSELSXMISC_FISH values", make_df(principle, ex, pt, R, value_col="value_t_xfish"),
            drop=drop, last_pre=last_pre)
        if principle == "residence":
            add("R11", "window 2019-01..2026-02 (sensitivity-window scan: no system-wide months)",
                make_df(principle, ex, pt, R_sens, window="sens"), drop=drop, last_pre=last_pre,
                last=C.SENS_END_RESIDENCE)

        results = {}
        for vid, desc, df, kw in variants:
            t0 = time.perf_counter()
            res = run_variant(df, panama=True, **kw)
            results[vid] = res
            out += record(vid, principle, res, desc)
            times.append({"variant": vid, "principle": principle, "seconds": time.perf_counter() - t0})
            print(f"{principle:9s} {vid:4s} S1 {res['main']['S1']['excess_t'].sum() / MT:+8.2f} Mt  "
                  f"S2 {res['main']['S2']['excess_t'].sum() / MT:+8.2f} Mt  "
                  f"robust {int(res['units']['robust'].sum()):2d}  ({time.perf_counter() - t0:.1f} s)")

        # robust-list changes against R0
        r0_units = results["R0"]["units"]
        r0_rob = set(r0_units.index[r0_units["robust"]])
        for vid, res in results.items():
            rob = set(res["units"].index[res["units"]["robust"]])
            present = set(res["units"].index)
            lost = sorted(r0_rob - rob)
            changes.append({"variant": vid, "principle": principle, "n_robust": len(rob),
                            "robust_list": " ".join(sorted(rob)),
                            "gained": " ".join(sorted(rob - r0_rob)),
                            "lost": " ".join(lost),
                            "lost_not_estimated": " ".join(c for c in lost if c not in present)})

        # R12, R13: re-sums of R0
        r0 = results["R0"]
        out += sum_rows("R12", principle, r0, lambda p: p != "2025-09", "R0 excess without 2025-09")
        out += sum_rows("R13", principle, r0, lambda p: (p >= "2024-08") & (p <= "2025-10"),
                        "R0 excess over 2024-08..2025-10")

        # R14: leave-one-out of the 10 largest-weight non-control economies (main only)
        w = r0["weights"]
        ctrl = df0.drop_duplicates("unit").set_index("unit")["control"]
        top = w[~w.index.map(ctrl)].sort_values(ascending=False).head(10)
        for iso in top.index:
            t0 = time.perf_counter()
            res = run_variant(df0[df0["unit"] != iso], drop=drop, last_pre=last_pre, panama=True, placebos=False)
            out += record(f"R14-{iso}", principle, res, f"leave out {iso} (weight rank {list(top.index).index(iso) + 1})",
                          extra={"left_out": iso, "left_out_weight_t_per_day": top[iso]})
            times.append({"variant": f"R14-{iso}", "principle": principle, "seconds": time.perf_counter() - t0})

        # consistency of R0 with the main tables
        summ = pd.read_csv(TABLES / "rsd4_summary.csv")
        for spec in ("S1", "S2"):
            ref = summ[(summ["principle"] == principle) & (summ["spec"] == spec)]["excess_Mt"].iloc[0]
            got = r0["main"][spec]["excess_t"].sum() / MT
            checks.append(numeric_check(f"R0_{principle}_{spec}_equals_main",
                                        f"R0 {principle} {spec} total equals rsd4_summary.csv, Mt",
                                        f"{ref:.6f}", got, 6, tol=1e-6))
        units_main = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv")
        checks.append(exact_check(f"R0_{principle}_robust_equals_main", f"R0 {principle} robust list equals rsd4 units",
                                  " ".join(sorted(units_main.loc[units_main["robust"], "iso3"])),
                                  " ".join(sorted(r0_rob))))

    res_df = pd.DataFrame(out)
    res_df.to_csv(TABLES / "robustness_economies.csv", index=False)
    pd.DataFrame(changes).to_csv(TABLES / "robustness_robust_changes.csv", index=False)
    # Run times depend on the machine and the run, so they are printed, not written to a file.
    print("Run times per variant (s):")
    for t in times:
        print(f"  {t['principle']:9s} {t['variant']:8s} {t['seconds']:6.2f}")
    print(f"{rel(TABLES / 'robustness_economies.csv')}: {len(res_df)} rows")
    print(f"{rel(TABLES / 'robustness_robust_changes.csv')}: {len(changes)} rows")
    write_checks(checks, C.CHECKS / "robustness_checks.csv")
    print(f"Run time {time.perf_counter() - t_all:.1f} s")


if __name__ == "__main__":
    main()
