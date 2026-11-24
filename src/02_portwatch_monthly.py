"""Build monthly PortWatch chokepoint series and run checks.

Monthly values are the mean of daily values per chokepoint and month.

Outputs
- data/interim/portwatch_monthly.csv.gz
- outputs/checks/portwatch_checks.csv
"""

import pandas as pd

import config as C
from common import exact_check, numeric_check, rel, require_verified, write_checks

TYPES = {"container": "container", "dry bulk": "dry_bulk", "general cargo": "general_cargo",
         "roro": "roro", "tanker": "tanker", "total": "total"}


def main():
    require_verified(C.PORTWATCH_FILE)
    checks = []

    d = pd.read_csv(C.PORTWATCH_FILE, encoding="utf-8-sig")
    d["date"] = pd.to_datetime(d["date"], format="%Y/%m/%d")
    checks.append(exact_check("rows", "Daily rows", 79940, len(d)))
    checks.append(exact_check("first_date", "First date", "2019-01-01", d["date"].min().strftime("%Y-%m-%d")))
    checks.append(exact_check("last_date", "Last date", "2026-10-25", d["date"].max().strftime("%Y-%m-%d")))
    checks.append(exact_check("chokepoints", "Distinct portid", 28, d["portid"].nunique()))
    days = d.groupby("portid")["date"].nunique()
    checks.append(exact_check("days_per_chokepoint", "Distinct dates per chokepoint (min-max)",
                              "2855-2855", f"{days.min()}-{days.max()}"))
    checks.append(exact_check("duplicate_days", "Rows duplicated on portid x date", 0,
                              int(d.duplicated(["portid", "date"]).sum())))

    value_cols = [c for c in d.columns if c.startswith("n_") or c.startswith("capacity")]
    d["period"] = d["date"].dt.strftime("%Y-%m")
    g = d.groupby(["portid", "portname", "period"])
    mon = g[value_cols].mean().add_suffix("_per_day_mean")
    mon["days_observed"] = g["date"].nunique()
    mon = mon.reset_index()
    mon["days_in_month"] = pd.PeriodIndex(mon["period"], freq="M").days_in_month
    mon["partial_month"] = mon["days_observed"] < mon["days_in_month"]
    mon = mon.sort_values(["portid", "period"], key=lambda s: s.str.replace("chokepoint", "").str.zfill(3)
                          if s.name == "portid" else s).reset_index(drop=True)
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    mon.to_csv(C.PORTWATCH_MONTHLY, index=False, compression="gzip")
    print(f"{rel(C.PORTWATCH_MONTHLY)}: {len(mon)} rows")

    checks.append(exact_check("monthly_rows", "Rows in the monthly table", 2632, len(mon)))
    oct26 = mon.loc[mon["period"] == "2026-10", "days_observed"]
    checks.append(exact_check("days_observed_2026_10", "Days observed in 2026-10 (min-max over chokepoints)",
                              "25-25", f"{oct26.min()}-{oct26.max()}"))
    partial = sorted(mon.loc[mon["partial_month"], "period"].unique())
    checks.append(exact_check("partial_months", "Months flagged as partial", "2026-10", ";".join(partial)))

    def annual(name, col):
        s = mon[mon["portname"] == name].set_index("period")[f"{col}_per_day_mean"]
        return s, s.groupby(s.index.str[:4]).mean()

    _, suez_tot = annual("Suez Canal", "n_total")
    _, suez_con = annual("Suez Canal", "n_container")
    ann_def = "Mean of monthly means of daily transits, Suez Canal"
    for y, exp in zip(("2023", "2024", "2025"), ("73.7", "39.6", "38.5")):
        checks.append(numeric_check(f"suez_n_total_{y}", f"{ann_def}, n_total, {y}", exp, suez_tot.get(y), 1))
    for y, exp in zip(("2023", "2024", "2025"), ("19.1", "8.7", "9.2")):
        checks.append(numeric_check(f"suez_n_container_{y}", f"{ann_def}, n_container, {y}", exp, suez_con.get(y), 1))

    exp_change = {"container": "-54", "dry bulk": "-41", "tanker": "-44",
                  "general cargo": "-29",  # reference value computed from unrounded annual means
                  "roro": "-82",  # reference value computed from unrounded annual means
                  "total": "-46"}
    suez_daily = d[d["portname"] == "Suez Canal"]
    detail = []
    for label, exp in exp_change.items():
        col = f"n_{TYPES[label]}"
        _, a = annual("Suez Canal", col)
        chg = (a["2024"] / a["2023"] - 1) * 100
        yd = suez_daily.groupby(suez_daily["date"].dt.year)[col].mean()
        detail.append({"vessel_type": TYPES[label], "expected_pct": exp,
                       "annual_2023_mean_of_monthly_means": round(a["2023"], 3),
                       "annual_2024_mean_of_monthly_means": round(a["2024"], 3),
                       "change_pct_mean_of_monthly_means": round(chg, 3),
                       "change_pct_mean_of_daily_values": round((yd[2024] / yd[2023] - 1) * 100, 3)})
        checks.append(numeric_check(f"suez_change_2024_vs_2023_{TYPES[label]}",
                                    f"(annual 2024 / annual 2023 - 1) x 100, Suez Canal, n_{TYPES[label]}, %",
                                    exp, chg, 0))
    pd.DataFrame(detail).to_csv(C.CHECKS / "portwatch_suez_change_detail.csv", index=False)
    print(f"{rel(C.CHECKS / 'portwatch_suez_change_detail.csv')}: {len(detail)} rows")

    hz, hz_ann = annual("Strait of Hormuz", "n_total")
    base = hz_ann["2025"]
    checks.append(numeric_check("hormuz_n_total_2025", "Mean of monthly means, Strait of Hormuz, n_total, 2025",
                                "85.5", base, 1))
    for p, exp in (("2025-10", "5"), ("2025-11", "-21"), ("2025-12", "-35"), ("2026-01", "-32"),
                   ("2026-02", "-8"), ("2026-03", "-96")):
        checks.append(numeric_check(f"hormuz_change_{p}",
                                    f"(monthly mean / 2025 mean - 1) x 100, Strait of Hormuz, n_total, {p}, %",
                                    exp, (hz.get(p) / base - 1) * 100, 0))

    write_checks(checks, C.CHECKS / "portwatch_checks.csv")


if __name__ == "__main__":
    main()
