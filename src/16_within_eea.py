"""Within-EEA check (RS-D19).

Panel: the EEA economies of each principle's panel with exposure data.
Control pool: economies at or below the within-EEA tercile cut-off of the
principle's exposure (pandas quantile(1/3)), excluding HQ economies.
Estimator: RS-D15 S1 and S2 with the Panama term; RS-D16 placebos and robust
rule within this panel (run through common.run_variant).

Outputs
- outputs/tables/within_eea.csv
- outputs/tables/within_eea_summary.csv
- outputs/checks/within_eea_checks.csv
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import exact_check, numeric_check, rel, run_variant, write_checks

m10 = importlib.import_module("10_rsd4_economies")
m12 = importlib.import_module("12_robustness_economies")

TABLES = C.OUTPUTS / "tables"
MT = 1e6
EXPOSURE = {"residence": "e_res", "departure": "x_v"}
REF = {
    "residence": dict(n=24, cut="0.1174", pool="ESP HRV ISL ITA MLT NOR PRT SWE", S1=("16.54", "3.63"),
                      S2=("21.79", "4.84"), robust="BEL EST FRA LTU", units={}),
    "departure": dict(n=24, cut="0.1438", pool="BEL HRV IRL ISL NOR POL PRT SVN", S1=("-0.17", "-0.11"),
                      S2=("15.37", "11.34"), robust="GRC",
                      units={"ESP": dict(S1_Mt="6.65", S1_pct="16.96", S2_pct="35.56", max_abs_placebo="18.06")}),
}


def main():
    t_all = time.perf_counter()
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    R = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")["R"]
    rows, summary, checks = [], [], []

    for principle, cfg in m10.PRINCIPLES.items():
        t0 = time.perf_counter()
        col = EXPOSURE[principle]
        panel_col = "in_res_panel" if principle == "residence" else "in_dep_panel"
        e = ex[ex["eea"] & ex[panel_col] & ex[col].notna()].set_index("iso3")
        cut = e[col].quantile(1 / 3)
        control = (e[col] <= cut) & ~e["hq"]
        pool = sorted(control.index[control])
        df = m12.make_df(principle, ex, pt, R, keep=set(e.index), control=control)
        res = run_variant(df, drop=tuple(cfg["drop"]), last_pre=cfg["last_pre"], panama=True)
        u, agg = res["units"], res["placebo"]

        r0 = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv").set_index("iso3")
        for iso in sorted(e.index):
            row = {"principle": principle, "iso3": iso, col: e.loc[iso, col], "hq": bool(e.loc[iso, "hq"]),
                   "control_within_eea": bool(control[iso])}
            if iso in u.index:
                row.update({"excess_S1_Mt": u.loc[iso, "excess_t_S1"] / MT, "pct_S1": u.loc[iso, "pct_S1"],
                            "excess_S2_Mt": u.loc[iso, "excess_t_S2"] / MT, "pct_S2": u.loc[iso, "pct_S2"],
                            "max_abs_placebo": u.loc[iso, "max_abs_placebo"], "robust": bool(u.loc[iso, "robust"])})
            row.update({"R0_control": bool(r0.loc[iso, "control"]),
                        "R0_excess_S1_Mt": r0.loc[iso, "excess_total_t_S1"] / MT, "R0_pct_S1": r0.loc[iso, "pct_S1"],
                        "R0_excess_S2_Mt": r0.loc[iso, "excess_total_t_S2"] / MT, "R0_pct_S2": r0.loc[iso, "pct_S2"],
                        "R0_max_abs_placebo": r0.loc[iso, "max_abs_placebo"], "R0_robust": bool(r0.loc[iso, "robust"])})
            rows.append(row)

        robust = sorted(u.index[u["robust"]])
        tot = {s: res["main"][s]["excess_t"].sum() for s in ("S1", "S2")}
        cf = {s: res["main"][s]["cf_t"].sum() for s in ("S1", "S2")}
        for spec in ("S1", "S2"):
            summary.append({"principle": principle, "spec": spec, "n_economies": len(e), "n_control": len(pool),
                            "cutoff": cut, "control_pool": " ".join(pool),
                            "excess_Mt": tot[spec] / MT, "cf_Mt": cf[spec] / MT, "pct": 100 * tot[spec] / cf[spec],
                            "placebo_band_pct_min": agg["pct"].min(), "placebo_band_pct_max": agg["pct"].max(),
                            "placebo_band_Mt_min": agg["pct"].min() * cf[spec] / 100 / MT,
                            "placebo_band_Mt_max": agg["pct"].max() * cf[spec] / 100 / MT,
                            "n_robust": len(robust), "robust_list": " ".join(robust),
                            "gamma_panama": res["diags"][spec]["gamma"],
                            "weighted_r2": res["diags"][spec]["weighted_r2"]})

        ref = REF[principle]
        d = f"within-EEA {principle}"
        checks.append(exact_check(f"{principle}_n", f"{d}: EEA economies with exposure data", ref["n"], len(e)))
        checks.append(numeric_check(f"{principle}_cutoff", f"{d}: quantile(1/3) of {col}", ref["cut"], cut, 4, tol=0.0001))
        checks.append(exact_check(f"{principle}_pool", f"{d}: control pool", ref["pool"], " ".join(pool)))
        for spec in ("S1", "S2"):
            checks.append(numeric_check(f"{principle}_{spec}_Mt", f"{d}: total excess {spec}, Mt", ref[spec][0],
                                        tot[spec] / MT, 2, tol=0.05))
            checks.append(numeric_check(f"{principle}_{spec}_pct", f"{d}: total excess {spec}, %", ref[spec][1],
                                        100 * tot[spec] / cf[spec], 2, tol=0.02))
        checks.append(exact_check(f"{principle}_robust", f"{d}: robust economies", ref["robust"], " ".join(robust)))
        for iso, vals in ref["units"].items():
            got = {"S1_Mt": u.loc[iso, "excess_t_S1"] / MT, "S1_pct": u.loc[iso, "pct_S1"],
                   "S2_pct": u.loc[iso, "pct_S2"], "max_abs_placebo": u.loc[iso, "max_abs_placebo"]}
            for k, v in vals.items():
                checks.append(numeric_check(f"{principle}_{iso}_{k}", f"{d}: {iso} {k}", v, got[k], 2,
                                            tol=0.05 if k.endswith("Mt") else 0.02))
        print(f"{principle}: {len(e)} EEA economies, cut-off {cut:.4f}, pool {len(pool)}; "
              f"S1 {tot['S1'] / MT:+.2f} Mt, S2 {tot['S2'] / MT:+.2f} Mt; robust {' '.join(robust) or 'none'} "
              f"({time.perf_counter() - t0:.1f} s)")

    pd.DataFrame(rows).to_csv(TABLES / "within_eea.csv", index=False)
    pd.DataFrame(summary).to_csv(TABLES / "within_eea_summary.csv", index=False)
    print(f"{rel(TABLES / 'within_eea.csv')}: {len(rows)} rows")
    write_checks(checks, C.CHECKS / "within_eea_checks.csv")
    print(f"Run time {time.perf_counter() - t_all:.1f} s")


if __name__ == "__main__":
    main()
