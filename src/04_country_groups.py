"""Write the country-group reference table and check member coverage.

Outputs
- data/reference/country_groups.csv   iso3, group, rule
- outputs/checks/group_coverage.csv   per member: OECD presence, complete
                                      RES_TOTAL and TER_INT in the window,
                                      pre-crisis months of components
                                      A, B, D, E, F, G, presence in v3
"""

import pandas as pd

import config as C
from common import is_verified, rel

NOT_RUN = "not run: OECD raw file not verified"

# Components whose pre-crisis coverage is reported (window 2019-01..2023-11, ALL_VESSELS)
PRE_COMPONENTS = {"A": "RES_DOM_IN", "B": "RES_DOM_OUT", "D": "RES_INT_FROM",
                  "E": "RES_INT_TO", "F": "RES_INT_OUT", "G": "NRES_INT_FROM"}


def main():
    rows = [{"iso3": iso, "group": grp, "rule": rule}
            for grp, (members, rule) in C.COUNTRY_GROUP_DEFS.items() for iso in members]
    groups = pd.DataFrame(rows)
    C.REFERENCE.mkdir(parents=True, exist_ok=True)
    groups.to_csv(C.COUNTRY_GROUPS, index=False)
    print(f"{rel(C.COUNTRY_GROUPS)}: {len(groups)} rows")

    cov = groups[["iso3", "group"]].copy()

    # v3 presence
    if C.V3_SHARES.exists():
        v3 = pd.read_csv(C.V3_SHARES, usecols=["iso3", "direction"])
        exp_iso = set(v3.loc[v3["direction"] == "export", "iso3"])
        imp_iso = set(v3.loc[v3["direction"] == "import", "iso3"])
        cov["in_v3_export"] = cov["iso3"].isin(exp_iso)
        cov["in_v3_import"] = cov["iso3"].isin(imp_iso)
    else:
        cov["in_v3_export"] = cov["in_v3_import"] = "not run: v3 shares missing"

    # OECD presence and completeness
    pre_cols = [f"n_months_pre_{k}" for k in PRE_COMPONENTS]
    if is_verified(C.OECD_FILE) and C.OECD_MONTHLY.exists():
        # presence: any row (any frequency) in the raw file
        areas = set(pd.read_csv(C.OECD_FILE, usecols=["REF_AREA"], dtype=str)["REF_AREA"])
        m = pd.read_csv(C.OECD_MONTHLY, usecols=["area", "vessel", "source", "period"])
        m = m[m["vessel"] == "ALL_VESSELS"]
        n_win = len(pd.period_range(C.PRE_START, C.MAIN_END, freq="M"))
        w = m[m["period"].between(C.PRE_START, C.MAIN_END)]
        n = w.groupby(["source", "area"])["period"].nunique()
        p = m[m["period"].between(C.PRE_START, C.PRE_END)]
        n_pre = p.groupby(["source", "area"])["period"].nunique()
        cov["in_oecd_areas"] = cov["iso3"].isin(areas)
        for src in ("RES_TOTAL", "TER_INT"):
            months = cov["iso3"].map(lambda a: int(n.get((src, a), 0)))
            cov[f"n_months_{src}"] = months
            cov[f"complete_{src}"] = months == n_win
        for k, src in PRE_COMPONENTS.items():
            cov[f"n_months_pre_{k}"] = cov["iso3"].map(lambda a: int(n_pre.get((src, a), 0)))
    else:
        for col in ["in_oecd_areas", "n_months_RES_TOTAL", "complete_RES_TOTAL",
                    "n_months_TER_INT", "complete_TER_INT"] + pre_cols:
            cov[col] = NOT_RUN

    cols = ["iso3", "group", "in_oecd_areas", "complete_RES_TOTAL", "n_months_RES_TOTAL",
            "complete_TER_INT", "n_months_TER_INT"] + pre_cols + ["in_v3_export", "in_v3_import"]
    cov = cov[cols]
    C.CHECKS.mkdir(parents=True, exist_ok=True)
    cov.to_csv(C.CHECKS / "group_coverage.csv", index=False)
    print(f"{rel(C.CHECKS / 'group_coverage.csv')}: {len(cov)} rows")


if __name__ == "__main__":
    main()
