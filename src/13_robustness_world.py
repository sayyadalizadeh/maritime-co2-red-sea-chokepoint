"""Robustness variants for the world estimates by ship type (RS-D2), using 09_imputation unchanged.

Variants, applied to the main run (transit types treated) and to B1 (CONTAINER treated):
  W0  none (main)                         full
  W1  MISC_FISH removed from the controls full
  W2  2020-01..2021-12 dropped            full, placebo dates 2022-06 and 2022-12
  W3  W0 excess without 2025-09           no new estimation
  W4  W0 excess over 2024-08..2025-10     no new estimation

Outputs
- outputs/tables/robustness_world.csv
- outputs/tables/robustness_world_types.csv (W0 per type, with S2 counterfactuals; input for the dose check)
- outputs/tables/robustness_world_container.csv (CONTAINER per estimated variant, run and specification:
  excess by year and the maximum |placebo %| over the variant's placebo runs; input for 19_tables.py)
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import months, numeric_check, rel, run_variant, write_checks

m11 = importlib.import_module("11_rsd2_world")

TABLES = C.OUTPUTS / "tables"
MT = 1e6


def main():
    t_all = time.perf_counter()
    w = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w[(w["period"] >= C.PRE_START) & (w["period"] <= C.MAIN_END)]
    base = w[w["vessel"].isin(m11.TRANSIT + m11.NON_TRANSIT)].rename(columns={"vessel": "unit"})
    rows, checks, type_rows, container_rows = [], [], [], []
    summ = pd.read_csv(TABLES / "rsd2_summary.csv")

    for run, treated in (("main", set(m11.TRANSIT)), ("B1", {"CONTAINER"})):
        df = base.copy()
        df["control"] = ~df["unit"].isin(treated)
        variants = [
            ("W0", "main", df, {}),
            ("W1", "MISC_FISH removed from the controls", df[df["unit"] != "MISC_FISH"], {}),
            ("W2", "2020-01..2021-12 dropped; placebo dates 2022-06, 2022-12", df,
             {"drop": tuple(months(*C.COVID_EXCL)), "placebo_dates": ("2022-06", "2022-12")}),
        ]
        results = {}
        for vid, desc, d, kw in variants:
            t0 = time.perf_counter()
            res = run_variant(d, last_pre=m11.LAST_PRE, **kw)
            results[vid] = res
            agg, u = res["placebo"], res["units"]
            max_abs = agg["pct"].abs().max()
            for spec in ("S1", "S2"):
                tr = res["main"][spec]
                tot, cf = tr["excess_t"].sum(), tr["cf_t"].sum()
                pcts = {s: 100 * res["main"][s]["excess_t"].sum() / res["main"][s]["cf_t"].sum() for s in ("S1", "S2")}
                rows.append({
                    "variant": vid, "run": run, "spec": spec, "description": desc,
                    "n_types": res["diags"][spec]["n_units"], "n_control_types": res["diags"][spec]["n_control_units"],
                    "excess_Mt": tot / MT, "cf_Mt": cf / MT, "pct": 100 * tot / cf,
                    "placebo_dates": " ".join(sorted(agg["placebo_date"].unique())),
                    "placebo_band_pct_min": agg["pct"].min(), "placebo_band_pct_max": agg["pct"].max(),
                    "placebo_band_Mt_min": agg["pct"].min() * cf / 100 / MT,
                    "placebo_band_Mt_max": agg["pct"].max() * cf / 100 / MT,
                    "total_robust": bool(np.sign(pcts["S1"]) == np.sign(pcts["S2"])
                                         and min(abs(pcts["S1"]), abs(pcts["S2"])) > max_abs),
                    "container_excess_Mt": u[f"excess_t_{spec}"]["CONTAINER"] / MT,
                    "container_pct": u[f"pct_{spec}"]["CONTAINER"],
                    "container_robust": bool(u["robust"]["CONTAINER"]),
                })
            for spec in ("S1", "S2"):
                c = res["main"][spec]
                c = c[c["unit"] == "CONTAINER"]
                yr = c.groupby(c["period"].str[:4])["excess_t"].sum()
                container_rows.append({
                    "variant": vid, "run": run, "spec": spec,
                    "container_excess_Mt": c["excess_t"].sum() / MT,
                    **{f"container_excess_{y}_Mt": yr.get(y, 0.0) / MT for y in ("2023", "2024", "2025")},
                    "container_max_abs_placebo_pct": u["max_abs_placebo"]["CONTAINER"],
                    "placebo_runs": int(u.filter(like="placebo_").shape[1])})
            print(f"{run:4s} {vid}: S1 {rows[-2]['excess_Mt']:+.2f} Mt, S2 {rows[-1]['excess_Mt']:+.2f} Mt, "
                  f"total robust {rows[-1]['total_robust']}, CONTAINER robust {rows[-1]['container_robust']} "
                  f"({time.perf_counter() - t0:.1f} s)")

        w0 = results["W0"]
        for vid, desc, mask in (("W3", "W0 excess without 2025-09", lambda p: p != "2025-09"),
                                ("W4", "W0 excess over 2024-08..2025-10", lambda p: (p >= "2024-08") & (p <= "2025-10"))):
            for spec in ("S1", "S2"):
                tr = w0["main"][spec]
                t = tr[mask(tr["period"])]
                c = t[t["unit"] == "CONTAINER"]
                rows.append({"variant": vid, "run": run, "spec": spec, "description": desc,
                             "n_types": w0["diags"][spec]["n_units"],
                             "n_control_types": w0["diags"][spec]["n_control_units"],
                             "excess_Mt": t["excess_t"].sum() / MT, "cf_Mt": t["cf_t"].sum() / MT,
                             "pct": 100 * t["excess_t"].sum() / t["cf_t"].sum(),
                             "container_excess_Mt": c["excess_t"].sum() / MT,
                             "container_pct": 100 * c["excess_t"].sum() / c["cf_t"].sum()})

        # W0 must equal the main tables
        for spec in ("S1", "S2"):
            ref = summ[(summ["run"] == run) & (summ["spec"] == spec)]["excess_Mt"].iloc[0]
            checks.append(numeric_check(f"W0_{run}_{spec}_equals_main", f"W0 {run} {spec} total equals rsd2_summary.csv, Mt",
                                        f"{ref:.6f}", w0["main"][spec]["excess_t"].sum() / MT, 6, tol=1e-6))
        if run == "main":
            u = w0["units"]
            for vessel in u.index:
                type_rows.append({"vessel": vessel, **{c: u.loc[vessel, c] for c in
                                  ("excess_t_S1", "excess_t_S2", "cf_t_S1", "cf_t_S2", "pct_S1", "pct_S2", "robust")}})

    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "robustness_world.csv", index=False)
    pd.DataFrame(type_rows).to_csv(TABLES / "robustness_world_types.csv", index=False)
    pd.DataFrame(container_rows).to_csv(TABLES / "robustness_world_container.csv", index=False)
    print(f"{rel(TABLES / 'robustness_world_container.csv')}: {len(container_rows)} rows")
    print(f"{rel(TABLES / 'robustness_world.csv')}: {len(out)} rows")
    write_checks(checks, C.CHECKS / "robustness_world_checks.csv")
    print(f"Run time {time.perf_counter() - t_all:.1f} s")


if __name__ == "__main__":
    main()
