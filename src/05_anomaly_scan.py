"""Pre-specified anomaly scan (RS-D14).

For each principle and window:
- panel: economies complete in the window (ALL_VESSELS; residence = RES_TOTAL,
  departure = TER_INT);
- per-day values; log of the value over the economy's centred seven-month
  rolling median (at least four months); flag if |log ratio| > 0.4;
- larger half: mean per-day value over the window strictly above the panel
  median of these means;
- a month is system-wide anomalous if at least four larger-half economies
  are flagged; other flagged economy-months are isolated.

Outputs
- outputs/checks/anomaly_flags.csv    one row per flagged economy-month
- outputs/checks/anomaly_months.csv   one row per principle x window x month
- outputs/checks/anomaly_checks.csv   expected against obtained values
"""

import numpy as np
import pandas as pd

import config as C
from common import (complete_economies, days_in, exact_check, load_oecd_monthly,
                    months, rel, write_checks)

THRESHOLD = 0.4
ROLL_WINDOW = 7
ROLL_MIN = 4
MIN_LARGER_HALF = 4

RUNS = [  # principle, source, window label, start, end
    ("residence", "RES_TOTAL", "main", C.PRE_START, C.MAIN_END),
    ("departure", "TER_INT", "main", C.PRE_START, C.MAIN_END),
    ("residence", "RES_TOTAL", "residence sensitivity", C.PRE_START, C.SENS_END_RESIDENCE),
]

EXPECTED_DEP_NOV23 = "AGO BGD DNK EGY GIN MLT MUS MYS QAT SGP"


def scan(m, source, start, end):
    """Return the per economy-month scan table for one principle and window."""
    panel = complete_economies(m, source, start, end)
    s = m[(m["source"] == source) & m["area"].isin(panel) & m["period"].isin(months(start, end))]
    s = s[["area", "period", "value_t"]].rename(columns={"area": "iso3"})
    s = s.sort_values(["iso3", "period"]).reset_index(drop=True)
    s["per_day"] = s["value_t"] / days_in(s["period"]).values
    s["rolling_median"] = (s.groupby("iso3")["per_day"]
                           .transform(lambda x: x.rolling(ROLL_WINDOW, center=True, min_periods=ROLL_MIN).median()))
    with np.errstate(divide="ignore"):
        s["log_ratio"] = np.log(s["per_day"] / s["rolling_median"])
    s["flag"] = s["log_ratio"].abs() > THRESHOLD
    means = s.groupby("iso3")["per_day"].mean()
    larger = set(means[means > means.median()].index)
    s["larger_half"] = s["iso3"].isin(larger)
    return s, len(panel), len(larger)


def main():
    m = load_oecd_monthly("ALL_VESSELS")
    flags, month_rows, checks = [], [], []

    for principle, source, window, start, end in RUNS:
        s, n_panel, n_larger = scan(m, source, start, end)
        by_month = s.groupby("period").agg(
            n_flagged_larger_half=("flag", lambda f: int((f & s.loc[f.index, "larger_half"]).sum())),
            n_flagged_all=("flag", "sum")).reset_index()
        by_month["n_flagged_all"] = by_month["n_flagged_all"].astype(int)
        by_month["system_wide"] = by_month["n_flagged_larger_half"] >= MIN_LARGER_HALF
        by_month.insert(0, "window", window)
        by_month.insert(0, "principle", principle)
        month_rows.append(by_month)

        f = s[s["flag"]].copy()
        f.insert(0, "window", window)
        f.insert(0, "principle", principle)
        flags.append(f)

        sw = by_month.loc[by_month["system_wide"], "period"].tolist()
        n_isolated = int((~f["period"].isin(sw)).sum())
        print(f"{principle:9s} {window:21s} panel={n_panel} larger_half={n_larger} "
              f"flags={len(f)} system_wide={sw or 'none'} isolated={n_isolated}")

        tag = f"{principle}_{window.replace(' ', '_')}"
        defn = f"{principle}, {window} window {start}..{end}, {n_panel} economies"
        checks.append(exact_check(f"{tag}_n_flags", defn + "; flagged economy-months", "", len(f)) | {"pass": True,
                      "expected": "(report)", "abs_diff": ""})
        checks.append(exact_check(f"{tag}_n_isolated", defn + "; isolated flags (not in a system-wide month)",
                                  "", n_isolated) | {"pass": True, "expected": "(report)", "abs_diff": ""})
        if window == "main":
            exp_sw = "2023-11" if principle == "departure" else "none"
            checks.append(exact_check(f"{tag}_system_wide_months", defn + "; system-wide months",
                                      exp_sw, ";".join(sw) or "none"))
            if principle == "departure":
                nov = f[(f["period"] == "2023-11") & f["larger_half"]]
                checks.append(exact_check(f"{tag}_2023_11_larger_half", defn + "; larger-half flagged economies in 2023-11",
                                          EXPECTED_DEP_NOV23, " ".join(sorted(nov["iso3"]))))

    flags = pd.concat(flags, ignore_index=True)
    flags = flags[["principle", "window", "iso3", "period", "value_t", "per_day",
                   "rolling_median", "log_ratio", "larger_half"]]
    flags.to_csv(C.CHECKS / "anomaly_flags.csv", index=False)
    print(f"{rel(C.CHECKS / 'anomaly_flags.csv')}: {len(flags)} rows")

    mon = pd.concat(month_rows, ignore_index=True)
    mon.to_csv(C.CHECKS / "anomaly_months.csv", index=False)
    print(f"{rel(C.CHECKS / 'anomaly_months.csv')}: {len(mon)} rows")

    write_checks(checks, C.CHECKS / "anomaly_checks.csv")


if __name__ == "__main__":
    main()
