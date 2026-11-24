"""Two descriptive PortWatch tables (inputs for the RS-D2 and RS-D6 specifications).

Outputs
- outputs/checks/portwatch_relative_transits.csv
    monthly mean daily transits and capacity by vessel type, each divided by
    its own 2019-01..2023-11 mean, for four chokepoints, 2019-01..2026-10
- outputs/checks/portwatch_pre_crisis_shares.csv
    each vessel type's share of total transits and capacity, 2019-01..2023-11
    means of monthly means, Suez Canal and Bab el-Mandeb Strait
"""

import pandas as pd

import config as C
from common import months, rel, require_verified

CHOKEPOINTS = ["Suez Canal", "Bab el-Mandeb Strait", "Cape of Good Hope", "Panama Canal"]
TYPES = ["container", "dry_bulk", "general_cargo", "roro", "tanker", "cargo", "total"]
PRE = months(C.PRE_START, C.PRE_END)


def cols(t):
    """Monthly column names for transits and capacity of one vessel type."""
    cap = "capacity_per_day_mean" if t == "total" else f"capacity_{t}_per_day_mean"
    return f"n_{t}_per_day_mean", cap


def main():
    require_verified(C.PORTWATCH_FILE)
    mon = pd.read_csv(C.PORTWATCH_MONTHLY)
    mon = mon[mon["portname"].isin(CHOKEPOINTS)]

    rows = []
    for cp, g in mon.groupby("portname"):
        g = g.set_index("period").sort_index()
        pre = g.loc[g.index.isin(PRE)]
        for t in TYPES:
            n_col, c_col = cols(t)
            rel_n = g[n_col] / pre[n_col].mean()
            rel_c = g[c_col] / pre[c_col].mean()
            rows.append(pd.DataFrame({"chokepoint": cp, "period": g.index, "vessel_type": t,
                                      "n_rel": rel_n.round(6).values, "capacity_rel": rel_c.round(6).values,
                                      "partial_month": g["partial_month"].values}))
    out = pd.concat(rows, ignore_index=True)
    out["chokepoint"] = pd.Categorical(out["chokepoint"], CHOKEPOINTS, ordered=True)
    out = out.sort_values(["chokepoint", "vessel_type", "period"]).reset_index(drop=True)
    out.to_csv(C.CHECKS / "portwatch_relative_transits.csv", index=False)
    print(f"{rel(C.CHECKS / 'portwatch_relative_transits.csv')}: {len(out)} rows")

    rows = []
    for cp in ("Suez Canal", "Bab el-Mandeb Strait"):
        pre = mon[(mon["portname"] == cp) & mon["period"].isin(PRE)]
        n_tot, c_tot = (pre[c].mean() for c in cols("total"))
        for t in TYPES[:5]:
            n_col, c_col = cols(t)
            rows.append({"chokepoint": cp, "vessel_type": t,
                         "n_per_day_pre_mean": round(pre[n_col].mean(), 3),
                         "n_share": round(pre[n_col].mean() / n_tot, 4),
                         "capacity_per_day_pre_mean": round(pre[c_col].mean(), 1),
                         "capacity_share": round(pre[c_col].mean() / c_tot, 4)})
        five = pd.DataFrame(rows[-5:])
        rows.append({"chokepoint": cp, "vessel_type": "sum of five types",
                     "n_per_day_pre_mean": round(five["n_per_day_pre_mean"].sum(), 3),
                     "n_share": round(five["n_share"].sum(), 4),
                     "capacity_per_day_pre_mean": round(five["capacity_per_day_pre_mean"].sum(), 1),
                     "capacity_share": round(five["capacity_share"].sum(), 4)})
        rows.append({"chokepoint": cp, "vessel_type": "total",
                     "n_per_day_pre_mean": round(n_tot, 3), "n_share": 1.0,
                     "capacity_per_day_pre_mean": round(c_tot, 1), "capacity_share": 1.0})
    sh = pd.DataFrame(rows)
    sh.to_csv(C.CHECKS / "portwatch_pre_crisis_shares.csv", index=False)
    print(f"{rel(C.CHECKS / 'portwatch_pre_crisis_shares.csv')}: {len(sh)} rows")


if __name__ == "__main__":
    main()
