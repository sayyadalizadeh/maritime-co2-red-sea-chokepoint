"""Analysis panels for both accounting principles and the world by ship type.

Outputs
- data/interim/panel_residence.csv.gz
- data/interim/panel_departure.csv.gz
- data/interim/panel_common.csv
- data/interim/world_by_vessel.csv.gz
- outputs/checks/panel_checks.csv
"""

import pandas as pd

import config as C
from common import (complete_economies, days_in, exact_check, group_flags,
                    load_oecd_monthly, months, rel, write_checks)

MAIN = months(C.PRE_START, C.MAIN_END)
SENS = months(C.PRE_START, C.SENS_END_RESIDENCE)


def between(period, lo, hi):
    return (period >= lo) & (period <= hi)


def anomaly_columns(panel, principle, window, suffix=""):
    """System-wide and isolated anomaly flags from the RS-D14 scan outputs."""
    flags = pd.read_csv(C.CHECKS / "anomaly_flags.csv", dtype={"period": str})
    mon = pd.read_csv(C.CHECKS / "anomaly_months.csv", dtype={"period": str})
    f = flags[(flags["principle"] == principle) & (flags["window"] == window)]
    sw = set(mon.loc[(mon["principle"] == principle) & (mon["window"] == window) & mon["system_wide"], "period"])
    win = MAIN if window == "main" else SENS
    key = set(zip(f["iso3"], f["period"]))
    in_win = panel["period"].isin(win)
    flagged = pd.Series([(i, p) in key for i, p in zip(panel["iso3"], panel["period"])], index=panel.index)
    panel[f"anomaly_system_wide{suffix}"] = in_win & panel["period"].isin(sw)
    panel[f"anomaly_isolated{suffix}"] = in_win & flagged & ~panel["period"].isin(sw)
    return panel


def build(m_all, m_xfish, source, principle):
    main_econ = complete_economies(m_all, source, C.PRE_START, C.MAIN_END)
    s = m_all[(m_all["source"] == source) & m_all["area"].isin(main_econ)]
    if principle == "residence":
        sens_econ = complete_economies(m_all, source, C.PRE_START, C.SENS_END_RESIDENCE)
        keep = s["period"].isin(MAIN) | (s["area"].isin(sens_econ) & s["period"].isin(SENS))
    else:
        sens_econ = []
        keep = s["period"].isin(MAIN)
    p = s[keep][["area", "period", "value_t"]].rename(columns={"area": "iso3"})
    xf = m_xfish[m_xfish["source"] == source][["area", "period", "value_t"]]
    xf = xf.rename(columns={"area": "iso3", "value_t": "value_t_xfish"})
    p = p.merge(xf, on=["iso3", "period"], how="left")
    p = p.sort_values(["iso3", "period"]).reset_index(drop=True)

    p["year"] = p["period"].str[:4].astype(int)
    p["month"] = p["period"].str[5:7].astype(int)
    p["days"] = days_in(p["period"]).values
    p["per_day"] = p["value_t"] / p["days"]
    p["post"] = p["period"] >= C.SHOCK_START
    p["in_main_window"] = p["period"].isin(MAIN)
    p["in_sens_window"] = p["iso3"].isin(sens_econ) & p["period"].isin(SENS)
    p = pd.concat([p, group_flags(p["iso3"])], axis=1)
    p = anomaly_columns(p, principle, "main")
    if principle == "residence":
        p = anomaly_columns(p, principle, "residence sensitivity", suffix="_sens")
    p["covid_excl"] = between(p["period"], *C.COVID_EXCL)
    if principle == "departure":
        p["excl_rsd14"] = p["period"] == "2023-11"
        p["excl_rsd14_robust"] = between(p["period"], "2023-09", "2023-11")
        p["reclass2022_excl"] = between(p["period"], *C.RECLASS_2022_EXCL)

    cols = ["iso3", "period", "year", "month", "days", "value_t", "per_day", "value_t_xfish",
            "post", "in_main_window", "in_sens_window", "rsl", "cpa", "hq", "eea", "rus",
            "anomaly_system_wide", "anomaly_isolated"]
    cols += ["anomaly_system_wide_sens", "anomaly_isolated_sens"] if principle == "residence" else []
    cols += ["covid_excl"]
    cols += ["excl_rsd14", "excl_rsd14_robust", "reclass2022_excl"] if principle == "departure" else []
    return p[cols], main_econ, sens_econ


def main():
    m = load_oecd_monthly(vessel=None)
    m_all = m[m["vessel"] == "ALL_VESSELS"]
    m_xfish = m[m["vessel"] == "ALL_VESSELSXMISC_FISH"]
    checks = []
    panels = {}

    for principle, source, n_exp, rsl_exp, cpa_exp in (("residence", "RES_TOTAL", 140, 4, 20),
                                                       ("departure", "TER_INT", 137, 4, 20)):
        p, econ, sens_econ = build(m_all, m_xfish, source, principle)
        panels[principle] = (p, econ)
        out = C.INTERIM / f"panel_{principle}.csv.gz"
        p.to_csv(out, index=False, compression="gzip")
        print(f"{rel(out)}: {len(p)} rows, {len(econ)} economies (sensitivity window: {len(sens_econ)})")

        main_rows = p[p["in_main_window"]]
        d = f"{principle} panel ({source}, ALL_VESSELS)"
        checks.append(exact_check(f"{principle}_economies", f"{d}: economies complete in {C.PRE_START}..{C.MAIN_END}",
                                  n_exp, len(econ)))
        checks.append(exact_check(f"{principle}_rows_main", f"{d}: rows in the main window = economies x {len(MAIN)}",
                                  len(econ) * len(MAIN), len(main_rows)))
        checks.append(exact_check(f"{principle}_missing_main", f"{d}: missing value_t in the main window",
                                  0, int(main_rows["value_t"].isna().sum())))
        if principle == "residence":
            checks.append(exact_check("residence_economies_sens",
                                      f"{d}: economies complete in {C.PRE_START}..{C.SENS_END_RESIDENCE}",
                                      "(report)", len(sens_econ)) | {"pass": True, "abs_diff": ""})
            sens_rows = p[p["in_sens_window"]]
            checks.append(exact_check("residence_rows_sens", f"{d}: rows in the sensitivity window = economies x {len(SENS)}",
                                      len(sens_econ) * len(SENS), len(sens_rows)))
        checks.append(exact_check(f"{principle}_xfish_missing_main",
                                  f"{d}: main-window rows without a published ALL_VESSELSXMISC_FISH value",
                                  "(report)", int(main_rows["value_t_xfish"].isna().sum())) | {"pass": True, "abs_diff": ""})
        members = main_rows.drop_duplicates("iso3")
        for g, exp in (("rsl", rsl_exp), ("cpa", cpa_exp)):
            codes = sorted(members.loc[members[g], "iso3"])
            checks.append(exact_check(f"{principle}_{g}_members", f"{d}: {g.upper()} members in the panel ({' '.join(codes)})",
                                      exp, len(codes)))
        for g in ("hq", "eea", "rus"):
            codes = sorted(members.loc[members[g], "iso3"])
            checks.append(exact_check(f"{principle}_{g}_members", f"{d}: {g.upper()} members in the panel ({' '.join(codes)})",
                                      "(report)", len(codes)) | {"pass": True, "abs_diff": ""})

    common = sorted(set(panels["residence"][1]) & set(panels["departure"][1]))
    pc = pd.DataFrame({"iso3": common})
    names = m_all.drop_duplicates("area").set_index("area")["area_name"]
    pc.insert(1, "area_name", pc["iso3"].map(names))
    pc = pd.concat([pc, group_flags(pc["iso3"])], axis=1)
    pc.to_csv(C.INTERIM / "panel_common.csv", index=False)
    print(f"{rel(C.INTERIM / 'panel_common.csv')}: {len(pc)} economies")
    checks.append(exact_check("common_economies", "Economies complete in both RES_TOTAL and TER_INT", 133, len(pc)))

    # World by ship type
    w = m[(m["area"] == "W") & (m["source"] == "RES_TOTAL") & (m["vessel"] != "ALL_VESSELSXMISC_FISH")]
    w = w[between(w["period"], C.PRE_START, "2026-09")][["vessel", "period", "value_t"]]
    wide = w.pivot(index="period", columns="vessel", values="value_t")
    types = [v for v in wide.columns if v != "ALL_VESSELS"]
    built = (wide["ALL_VESSELS"] - wide["MISC_FISH"]).rename("value_t").reset_index()
    built["vessel"] = "ALL_VESSELSXMISC_FISH_built"
    wv = pd.concat([w, built[["vessel", "period", "value_t"]]], ignore_index=True)
    wv = wv.sort_values(["vessel", "period"]).reset_index(drop=True)
    wv["days"] = days_in(wv["period"]).values
    wv["per_day"] = wv["value_t"] / wv["days"]
    wv = wv[["vessel", "period", "days", "value_t", "per_day"]]
    wv.to_csv(C.INTERIM / "world_by_vessel.csv.gz", index=False, compression="gzip")
    print(f"{rel(C.INTERIM / 'world_by_vessel.csv.gz')}: {len(wv)} rows")

    signed = wide[types].sum(axis=1) - wide["ALL_VESSELS"]
    gap = signed.abs()
    gaps = pd.DataFrame({"period": wide.index, "sum_types_t": wide[types].sum(axis=1).values,
                         "all_vessels_t": wide["ALL_VESSELS"].values, "gap_t": signed.round(3).values,
                         "gap_pct": (signed / wide["ALL_VESSELS"] * 100).round(5).values})
    gaps.to_csv(C.CHECKS / "world_type_sum_gaps.csv", index=False)
    print(f"{rel(C.CHECKS / 'world_type_sum_gaps.csv')}: {len(gaps)} rows")
    checks.append(exact_check("world_n_types", "Ship types for W RES_TOTAL (ALL_VESSELS and ALL_VESSELSXMISC_FISH excluded)",
                              19, len(types)))
    checks.append(exact_check("world_months", "Months of W RES_TOTAL, 2019-01..2026-09, every type",
                              93, int(wide[types + ["ALL_VESSELS"]].notna().all(axis=1).sum())))
    # The type-sum check stops at 2026-06, the last month of the components;
    # the gap file covers every month.
    g26 = gap[gap.index <= "2026-06"]
    checks.append(dict(check="world_type_sum_gap",
                       definition="max over months 2019-01..2026-06 of |sum of 19 types - ALL_VESSELS|, W RES_TOTAL, tonnes",
                       expected="<= 0.001", obtained=f"{g26.max():.6f}", abs_diff="",
                       **{"pass": bool(g26.max() <= 0.001)}))
    bad = gaps.loc[gap.values > 0.001, "period"].tolist()
    checks.append(exact_check("world_type_sum_gap_months", "Months of 2019-01..2026-09 with |gap| > 0.001 t "
                              "(after the last component month; see world_type_sum_gaps.csv)", "", ";".join(bad))
                  | {"expected": "(report)", "pass": True, "abs_diff": ""})

    write_checks(checks, C.CHECKS / "panel_checks.csv")


if __name__ == "__main__":
    main()
