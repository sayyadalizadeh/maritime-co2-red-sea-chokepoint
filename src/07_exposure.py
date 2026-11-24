"""Exposure measures and control pools (RS-D3, RS-D4, RS-D13).

Departure principle: x_v = v3 Suez Canal export share (value); x_q by quantity.
Residence principle: e_res = (D*x_v + E*m_v + F*w) / (A + B + D + E + F), with
components summed over the pre-crisis months (ALL_VESSELS) and absent
component-months counted as zero (RS-D13). w is the world-average Suez export
share over the v3 export file.

Control pool per principle: economies of that principle's panel with exposure
data at or below the tercile cut-off (pandas quantile(1/3), linear), excluding
RSL, CPA, HQ and RUS.

Outputs
- data/interim/exposure.csv
- outputs/checks/exposure_checks.csv
- outputs/checks/exposure_summary.csv
- outputs/checks/exposure_identity_gaps.csv
"""

import numpy as np
import pandas as pd

import config as C
from common import (complete_economies, exact_check, group_flags, load_oecd_monthly,
                    months, numeric_check, rel, write_checks)

COMP = {"A": "RES_DOM_IN", "B": "RES_DOM_OUT", "D": "RES_INT_FROM",
        "E": "RES_INT_TO", "F": "RES_INT_OUT"}
EXPECTED_E_RES = {"CHE": "0.1363", "DNK": "0.1383", "FRA": "0.1327", "DEU": "0.1393",
                  "CHN": "0.0932", "SGP": "0.1403", "MYS": "0.0807", "EGY": "0.1212",
                  "GRC": "0.1387", "USA": "0.0842", "JPN": "0.0914", "NOR": "0.1169"}
EXCLUDED_FROM_POOL = ("rsl", "cpa", "hq", "rus")


def main():
    checks = []
    m = load_oecd_monthly("ALL_VESSELS")
    res_panel = complete_economies(m, "RES_TOTAL", C.PRE_START, C.MAIN_END)
    dep_panel = complete_economies(m, "TER_INT", C.PRE_START, C.MAIN_END)

    # ---- v3 shares -----------------------------------------------------
    v3 = pd.read_csv(C.V3_SHARES)
    suez_x = v3[(v3["chokepoint"] == "Suez Canal") & (v3["direction"] == "export")].set_index("iso3")
    suez_m = v3[(v3["chokepoint"] == "Suez Canal") & (v3["direction"] == "import")].set_index("iso3")
    bem_x = v3[(v3["chokepoint"] == "Bab el-Mandeb Strait") & (v3["direction"] == "export")].set_index("iso3")
    w = suez_x["v_canal"].sum() / suez_x["v_sea_predict"].sum()
    checks.append(numeric_check("w", "Sum v_canal / sum v_sea_predict, Suez Canal rows, v3 export file",
                                "0.1643", w, 4, tol=0.0001))

    # ---- pre-crisis components (absent = 0) -----------------------------
    pre = months(C.PRE_START, C.PRE_END)
    econ = sorted(set(res_panel) | set(dep_panel))
    mp = m[m["period"].isin(pre) & ~m["area"].isin(C.NON_ECONOMY_AREAS)]
    comp = (mp[mp["source"].isin(COMP.values())]
            .pivot_table(index=["area", "period"], columns="source", values="value_t", aggfunc="first"))
    comp = comp.reindex(columns=list(COMP.values())).fillna(0.0)
    comp.columns = list(COMP.keys())

    # identity gaps: |RES_TOTAL / (A+B+D+E+F) - 1| > 1% in pre-crisis months
    tot = mp[mp["source"] == "RES_TOTAL"].set_index(["area", "period"])["value_t"]
    ident = pd.DataFrame({"res_total_t": tot}).join(comp, how="left").fillna({k: 0.0 for k in COMP})
    ident["sum_abdef_t"] = ident[list(COMP)].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ident["gap_pct"] = (ident["res_total_t"] / ident["sum_abdef_t"] - 1) * 100
    gaps = ident[ident["gap_pct"].abs() > 1].reset_index().rename(columns={"area": "iso3"})
    gaps["in_res_panel"] = gaps["iso3"].isin(res_panel)
    gaps = gaps[["iso3", "period", "res_total_t", "A", "B", "D", "E", "F", "sum_abdef_t", "gap_pct", "in_res_panel"]]
    gaps.to_csv(C.CHECKS / "exposure_identity_gaps.csv", index=False)
    print(f"{rel(C.CHECKS / 'exposure_identity_gaps.csv')}: {len(gaps)} economy-months "
          f"({int(gaps['in_res_panel'].sum())} in the residence panel)")
    checks.append(exact_check("identity_gaps_all", "Pre-crisis economy-months (any economy with RES_TOTAL) with "
                              "|RES_TOTAL/(A+B+D+E+F) - 1| > 1%", "(report)", len(gaps))
                  | {"pass": True, "abs_diff": ""})
    checks.append(exact_check("identity_gaps_res_panel", "As above, economies of the residence panel",
                              "(report)", int(gaps["in_res_panel"].sum())) | {"pass": True, "abs_diff": ""})

    sums = comp.groupby(level="area").sum()

    # ---- exposure table --------------------------------------------------
    ex = pd.DataFrame({"iso3": econ})
    ex["x_v"] = ex["iso3"].map(suez_x["share_v"])
    ex["x_q"] = ex["iso3"].map(suez_x["share_q"])
    ex["m_v"] = ex["iso3"].map(suez_m["share_v"])
    ex["bem_x_v"] = ex["iso3"].map(bem_x["share_v"])
    for k in COMP:
        ex[k] = ex["iso3"].map(sums[k]).fillna(0.0)
    denom = ex[list(COMP)].sum(axis=1)
    ex["e_res"] = (ex["D"] * ex["x_v"] + ex["E"] * ex["m_v"] + ex["F"] * w) / denom.replace(0, np.nan)
    ex["in_res_panel"] = ex["iso3"].isin(res_panel)
    ex["in_dep_panel"] = ex["iso3"].isin(dep_panel)
    ex = pd.concat([ex, group_flags(ex["iso3"])], axis=1)
    excluded = ex[list(EXCLUDED_FROM_POOL)].any(axis=1)

    pools = {}
    for principle, col, panel_col, n_exp, cut_exp, pool_exp in (
            ("residence", "e_res", "in_res_panel", 125, "0.0619", 29),
            ("departure", "x_v", "in_dep_panel", 122, "0.0692", 34)):
        base = ex[ex[panel_col] & ex[col].notna()]
        cut = base[col].quantile(1 / 3)
        pool = ex[panel_col] & ex[col].notna() & (ex[col] <= cut) & ~excluded
        ex[f"control_{principle[:3]}"] = pool
        pools[principle] = sorted(ex.loc[pool, "iso3"])
        missing = sorted(ex.loc[ex[panel_col] & ex[col].isna(), "iso3"])
        d = f"{principle} panel, exposure {col}"
        checks.append(exact_check(f"{principle}_n_with_exposure", f"{d}: economies with exposure data "
                                  f"(missing: {' '.join(missing) or 'none'})", n_exp, len(base)))
        checks.append(numeric_check(f"{principle}_cutoff", f"{d}: quantile(1/3), linear interpolation",
                                    cut_exp, cut, 4, tol=0.0001))
        checks.append(exact_check(f"{principle}_pool_size", f"{d}: at or below the cut-off, excluding RSL, CPA, HQ, RUS",
                                  pool_exp, len(pools[principle])))

    for iso, e in EXPECTED_E_RES.items():
        val = ex.loc[ex["iso3"] == iso, "e_res"]
        checks.append(numeric_check(f"e_res_{iso}", f"e_res, {iso}", e,
                                    val.iloc[0] if len(val) else None, 4, tol=0.0001))

    cols = ["iso3", "x_v", "x_q", "m_v", "bem_x_v", "A", "B", "D", "E", "F", "e_res", "hq",
            "in_res_panel", "in_dep_panel", "rsl", "cpa", "eea", "rus", "control_res", "control_dep"]
    ex[cols].to_csv(C.INTERIM / "exposure.csv", index=False)
    print(f"{rel(C.INTERIM / 'exposure.csv')}: {len(ex)} economies")
    for p, codes in pools.items():
        print(f"control pool {p} ({len(codes)}): {' '.join(codes)}")

    # ---- descriptive summary ---------------------------------------------
    rows = []
    for measure, panel_col, pool_col in (("x_v", "in_dep_panel", "control_dep"),
                                         ("e_res", "in_res_panel", "control_res")):
        base = ex[ex[panel_col] & ex[measure].notna()]
        groups = {"RSL": base["rsl"], "CPA": base["cpa"], "HQ": base["hq"], "EEA": base["eea"],
                  "RUS": base["rus"], "control pool": base[pool_col]}
        groups["others"] = ~pd.concat(list(groups.values()), axis=1).any(axis=1)
        groups["all"] = pd.Series(True, index=base.index)
        for g, mask in groups.items():
            v = base.loc[mask, measure]
            rows.append({"measure": measure, "panel": panel_col.replace("in_", "").replace("_panel", ""),
                         "group": g, "n": len(v), "mean": round(v.mean(), 4), "median": round(v.median(), 4),
                         "min": round(v.min(), 4), "max": round(v.max(), 4),
                         "members": " ".join(sorted(base.loc[mask, "iso3"])) if g != "all" else ""})
    summ = pd.DataFrame(rows)
    common = ex[ex["in_res_panel"] & ex["in_dep_panel"]]
    for a, b in (("x_v", "e_res"), ("x_v", "bem_x_v")):
        cc = common[[a, b]].dropna()
        rho = cc[a].corr(cc[b], method="spearman")
        summ = pd.concat([summ, pd.DataFrame([{"measure": f"spearman({a}, {b})", "panel": "common",
                                               "group": "all", "n": len(cc), "spearman_rho": round(rho, 4)}])],
                         ignore_index=True)
    summ.to_csv(C.CHECKS / "exposure_summary.csv", index=False)
    print(f"{rel(C.CHECKS / 'exposure_summary.csv')}: {len(summ)} rows")

    write_checks(checks, C.CHECKS / "exposure_checks.csv")


if __name__ == "__main__":
    main()
