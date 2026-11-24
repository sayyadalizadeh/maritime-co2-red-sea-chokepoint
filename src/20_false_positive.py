"""False-positive calibration of the robust rule (RS-D23).

No re-estimation: the calibration uses the placebo percentages already in
outputs/tables/rsd4_<principle>_units.csv (main run R0).

For each principle and each placebo date p (2020-12, 2021-06, 2021-12, 2022-06,
2022-12), over the non-control economies:
- pseudo-main result: the economy's placebo % at p, in S1 and in S2;
- pseudo-placebos: its placebo % at the other four dates, in S1 and S2 (8 values);
- pseudo-robust at p: the S1 and S2 values at p have the same sign, and
  min(|S1 at p|, |S2 at p|) > max |pseudo-placebo %| (the RS-D16 rule).

The actual rule uses a 23-month window and 10 placebo runs; the pseudo version
uses windows of at most 12 months and 8 runs.

Outputs
- outputs/tables/false_positive_calibration.csv
- outputs/tables/false_positive_by_economy.csv
- outputs/checks/false_positive_checks.csv
"""

import importlib

import numpy as np
import pandas as pd

import config as C
from common import exact_check, numeric_check, rel, write_checks

imp = importlib.import_module("09_imputation")

TABLES = C.OUTPUTS / "tables"
PRINCIPLES = ("residence", "departure")
DATES = list(imp.PLACEBO_DATES)
SPECS = ("S1", "S2")

# Reference values from an independent computation: counts by date, mean, max, actual robust count
REF = {"residence": ([2, 0, 5, 4, 7], "3.6", 7, 11),
       "departure": ([2, 1, 7, 2, 4], "3.2", 7, 9)}
N_NONCONTROL = {"residence": 96, "departure": 88}


def col(p, spec):
    return f"placebo_{p}_{spec}"


def pseudo_robust(u, p):
    """Boolean Series over the economies of u: pseudo-robust at placebo date p."""
    others = [col(q, s) for q in DATES if q != p for s in SPECS]
    max_pseudo = u[others].abs().max(axis=1)
    return imp.robust(u[col(p, "S1")], u[col(p, "S2")], max_pseudo)


def main():
    cal_rows, eco_rows, checks = [], [], []
    for pr in PRINCIPLES:
        u = pd.read_csv(TABLES / f"rsd4_{pr}_units.csv")
        u = u[~u["control"].astype(bool)].set_index("iso3").sort_index()
        pcols = [col(p, s) for p in DATES for s in SPECS]
        checks.append(exact_check(f"{pr}: non-control economies", "rows of rsd4 units with control = False",
                                  N_NONCONTROL[pr], len(u)))
        checks.append(exact_check(f"{pr}: placebo % finite", "non-finite values in the 10 placebo columns",
                                  0, int((~np.isfinite(u[pcols].to_numpy())).sum())))
        # The rule applied to the actual columns reproduces the stored robust flag
        actual = imp.robust(u["pct_S1"], u["pct_S2"], u[pcols].abs().max(axis=1))
        checks.append(exact_check(f"{pr}: rule reproduces stored robust flag",
                                  "economies where the recomputed RS-D16 flag differs from column robust",
                                  0, int((actual != u["robust"].astype(bool)).sum())))
        n_actual = int(u["robust"].astype(bool).sum())

        flags = pd.DataFrame({p: pseudo_robust(u, p) for p in DATES})
        counts = []
        for i, p in enumerate(DATES):
            lst = flags.index[flags[p]].tolist()
            counts.append(len(lst))
            cal_rows.append({"principle": pr, "row": "date", "placebo_date": p, "n_pseudo_robust": len(lst),
                             "pseudo_robust_list": " ".join(lst), "mean_count": np.nan, "max_count": np.nan,
                             "actual_robust": np.nan, "n_dates_count_ge_actual": np.nan})
            checks.append(exact_check(f"{pr}: pseudo-robust count at {p}", "RS-D23 count, non-control economies",
                                      REF[pr][0][i], len(lst)))
        mean_c, max_c = float(np.mean(counts)), int(max(counts))
        n_ge = int(sum(c >= n_actual for c in counts))
        cal_rows.append({"principle": pr, "row": "summary", "placebo_date": "all", "n_pseudo_robust": np.nan,
                         "pseudo_robust_list": "", "mean_count": mean_c, "max_count": max_c,
                         "actual_robust": n_actual, "n_dates_count_ge_actual": n_ge})
        checks.append(numeric_check(f"{pr}: mean count", "mean of the five pseudo-robust counts",
                                    REF[pr][1], mean_c, 1))
        checks.append(exact_check(f"{pr}: max count", "maximum of the five pseudo-robust counts", REF[pr][2], max_c))
        checks.append(exact_check(f"{pr}: actual robust count", "R0 robust non-control economies (rsd4 units)",
                                  REF[pr][3], n_actual))

        n_dates = flags.sum(axis=1).astype(int)
        for iso in u.index:
            eco_rows.append({"principle": pr, "iso3": iso, "n_dates_pseudo_robust": int(n_dates[iso]),
                             "pseudo_robust_dates": " ".join(p for p in DATES if flags.loc[iso, p]),
                             "actual_robust": bool(u.loc[iso, "robust"])})

    cal = pd.DataFrame(cal_rows)
    for c in ("n_pseudo_robust", "max_count", "actual_robust", "n_dates_count_ge_actual"):
        cal[c] = cal[c].astype("Int64")
    eco = pd.DataFrame(eco_rows)
    for df, name in ((cal, "false_positive_calibration.csv"), (eco, "false_positive_by_economy.csv")):
        df.to_csv(TABLES / name, index=False)
        print(f"{rel(TABLES / name)}: {len(df)} rows")
    print(cal.to_string(index=False))
    write_checks(checks, C.CHECKS / "false_positive_checks.csv")


if __name__ == "__main__":
    main()
