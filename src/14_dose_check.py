"""RS-D2 dose check: pre-crisis Suez transits per ship (and per DWT) against world excess by category.

d_c = PortWatch Suez Canal mean daily transits 2019-01..2023-11 x 365 / UNCTAD world number
of ships of the category on 1 January 2023 (UNCTADstat file, year 2023).
DWT version: PortWatch Suez mean daily capacity x 365 / UNCTAD world DWT (thousands x 1000).
Excess: W0 world S1 and S2, summed over the category's OECD types. No regression.

A category is skipped when a needed UNCTAD ship-type label is missing.

Outputs
- outputs/tables/rsd2_dose_check.csv
- outputs/checks/unctad_ship_types.csv (every ship-type label in the file)
"""

import pandas as pd

import config as C
from common import months, rel, require_verified

TABLES = C.OUTPUTS / "tables"
MT = 1e6
YEAR = 2023

CATEGORIES = {
    "container": dict(unctad=["Container ships"], pw=["container"], oecd=["CONTAINER"]),
    "dry bulk": dict(unctad=["Bulk carriers"], pw=["dry_bulk"], oecd=["BULK_CARRIER"]),
    "tanker": dict(unctad=["Oil tankers", "Chemical tankers", "Liquefied gas carriers"], pw=["tanker"],
                   oecd=["OIL_TANKER", "CHEM_TANKER", "LIQ_GAS_TANKER", "OTHER_LIQ_TANKER"]),
    "general cargo": dict(unctad=["General cargo"], pw=["general_cargo", "roro"],
                          oecd=["GEN_CARGO", "REFRIG_BULK", "RO_RO", "VEHICLE"]),
}


def main():
    require_verified(C.UNCTAD_FLEET_FILE)
    u = pd.read_csv(C.UNCTAD_FLEET_FILE, dtype={"Economy": str}, low_memory=False)
    labels = u[["ShipType", "ShipType Label"]].drop_duplicates().sort_values("ShipType")
    labels.to_csv(C.CHECKS / "unctad_ship_types.csv", index=False)
    print(f"{rel(C.CHECKS / 'unctad_ship_types.csv')}: {' | '.join(labels['ShipType Label'])}")
    world = u[(u["Economy Label"] == "World") & (u["Year"] == YEAR)].set_index("ShipType Label")

    pw = pd.read_csv(C.PORTWATCH_MONTHLY)
    suez = pw[(pw["portname"] == "Suez Canal") & pw["period"].isin(months(C.PRE_START, C.PRE_END))]
    types = pd.read_csv(TABLES / "robustness_world_types.csv").set_index("vessel")

    rows = []
    for cat, m in CATEGORIES.items():
        missing = [lab for lab in m["unctad"] if lab not in world.index]
        row = {"category": cat, "unctad_labels": " + ".join(m["unctad"]),
               "portwatch_columns": " + ".join(m["pw"]), "oecd_types": " ".join(m["oecd"])}
        if missing:
            row["status"] = "skipped: UNCTAD label(s) not in the file: " + ", ".join(missing)
            rows.append(row)
            continue
        ships = world.loc[m["unctad"], "Number of ships"].sum()
        dwt = world.loc[m["unctad"], "Dead weight tons in thousands"].sum() * 1000
        transits = sum(suez[f"n_{c}_per_day_mean"].mean() for c in m["pw"])
        capacity = sum(suez[f"capacity_{c}_per_day_mean"].mean() for c in m["pw"])
        t = types.loc[m["oecd"]]
        row.update({
            "status": "computed",
            "unctad_ships_2023": ships, "unctad_dwt_2023_t": dwt,
            "suez_transits_per_day_pre": transits, "suez_capacity_per_day_pre": capacity,
            "d_c_transits_per_ship_year": transits * 365 / ships,
            "d_c_dwt_capacity_per_dwt_year": capacity * 365 / dwt,
            "excess_Mt_S1": t["excess_t_S1"].sum() / MT, "excess_Mt_S2": t["excess_t_S2"].sum() / MT,
            "pct_S1": 100 * t["excess_t_S1"].sum() / t["cf_t_S1"].sum(),
            "pct_S2": 100 * t["excess_t_S2"].sum() / t["cf_t_S2"].sum(),
        })
        rows.append(row)

    out = pd.DataFrame(rows)
    ok = out["status"] == "computed"
    for col, name in (("d_c_transits_per_ship_year", "rank_d_c"), ("d_c_dwt_capacity_per_dwt_year", "rank_d_c_dwt"),
                      ("pct_S1", "rank_pct_S1"), ("pct_S2", "rank_pct_S2")):
        out.loc[ok, name] = out.loc[ok, col].rank(ascending=False).astype(int)
    out.to_csv(TABLES / "rsd2_dose_check.csv", index=False)
    print(f"{rel(TABLES / 'rsd2_dose_check.csv')}: {len(out)} rows")
    print(out[["category", "status", "d_c_transits_per_ship_year", "d_c_dwt_capacity_per_dwt_year",
               "excess_Mt_S1", "pct_S1", "excess_Mt_S2", "pct_S2"]].to_string(index=False))


if __name__ == "__main__":
    main()
