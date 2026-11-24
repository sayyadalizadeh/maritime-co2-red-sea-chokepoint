"""Chokepoint shares from the Verschuur & Hall v3 export and import files.

Outputs
- data/interim/verschuur_v3_shares.csv
- outputs/checks/verschuur_checks.csv
"""

import pandas as pd

import config as C
from common import (exact_check, is_verified, numeric_check, rel,
                    require_verified, write_checks)

# v3 spelling -> PortWatch spelling
NAME_MAP = {"Suez canal": "Suez Canal"}

OUT_COLS = ["iso3", "chokepoint", "direction", "share_v", "share_q",
            "v_canal", "v_sea_predict", "q_canal", "q_sea_predict"]

EXPECTED_SUEZ_EXPORT = {
    "EGY": "0.422", "MYS": "0.179", "SGP": "0.235", "CHN": "0.133", "IND": "0.374",
    "DEU": "0.241", "NLD": "0.226", "ITA": "0.198", "GRC": "0.163", "SAU": "0.191",
    "ZAF": "0.030", "USA": "0.106", "BRA": "0.068", "JPN": "0.129",
}
EXPECTED_NO_V3 = ("ALA ASM ATA ATG BMU CCK COK CXR ESH FLK FRO GGY GLP GRL IMN JEY "
                  "KIR LUX MAF MCO NAM NIU PCN PRI REU SGS SHN SJM SYR VIR WLF").split()


def load(path, direction):
    df = pd.read_csv(path)
    df["chokepoint"] = df["canal"].replace(NAME_MAP)
    df["direction"] = direction
    df = df.rename(columns={"share_canal_v_mar": "share_v", "share_canal_q_mar": "share_q"})
    return df


def main():
    require_verified(C.V3_EXPORT_FILE, C.V3_IMPORT_FILE)
    checks = []

    exp = load(C.V3_EXPORT_FILE, "export")
    imp = load(C.V3_IMPORT_FILE, "import")

    renamed = sorted({k for k in NAME_MAP if k in set(exp["canal"]) | set(imp["canal"])})
    print("Renamed chokepoints: " + "; ".join(f"'{k}' -> '{NAME_MAP[k]}'" for k in renamed))

    shares = pd.concat([exp, imp], ignore_index=True)[OUT_COLS]
    shares = shares.sort_values(["direction", "chokepoint", "iso3"]).reset_index(drop=True)
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    shares.to_csv(C.V3_SHARES, index=False)
    print(f"{rel(C.V3_SHARES)}: {len(shares)} rows")

    for name, df in (("export", exp), ("import", imp)):
        checks.append(exact_check(f"economies_{name}", f"Distinct iso3 in the v3 {name} file",
                                  198, df["iso3"].nunique()))
        checks.append(exact_check(f"duplicates_{name}", f"Rows duplicated on iso3 x chokepoint, {name} file",
                                  0, int(df.duplicated(["iso3", "chokepoint"]).sum())))
        suez = df[df["chokepoint"] == "Suez Canal"]
        missing = sorted(set(df["iso3"]) - set(suez["iso3"]))
        checks.append(exact_check(f"suez_rows_{name}", f"Economies with a Suez Canal row, {name} file "
                                  f"(without one: {' '.join(missing) or 'none'})",
                                  198, suez["iso3"].nunique()))

    pw = pd.read_csv(C.PORTWATCH_FILE, usecols=["portname"], encoding="utf-8-sig")["portname"].unique()
    v3_names = set(shares["chokepoint"])
    checks.append(exact_check("v3_not_in_portwatch", "v3 chokepoint names (after renaming) absent from PortWatch",
                              "", ";".join(sorted(v3_names - set(pw)))))
    checks.append(exact_check("portwatch_not_in_v3", "PortWatch chokepoint names absent from v3",
                              "", ";".join(sorted(set(pw) - v3_names))))

    suez_exp = exp[exp["chokepoint"] == "Suez Canal"].set_index("iso3")
    for iso, e in EXPECTED_SUEZ_EXPORT.items():
        checks.append(numeric_check(f"suez_export_share_{iso}",
                                    f"share_canal_v_mar, Suez Canal, export file, {iso}",
                                    e, suez_exp["share_v"].get(iso), 3))

    w_v = suez_exp["v_canal"].sum() / suez_exp["v_sea_predict"].sum()
    w_q = suez_exp["q_canal"].sum() / suez_exp["q_sea_predict"].sum()
    checks.append(numeric_check("world_suez_export_share_value",
                                "Sum v_canal / sum v_sea_predict over Suez Canal rows of the export file",
                                "0.1643", w_v, 4))
    checks.append(numeric_check("world_suez_export_share_quantity",
                                "Sum q_canal / sum q_sea_predict over Suez Canal rows of the export file",
                                "0.1287", w_q, 4))
    # Same ratio with the denominator over every economy in the file (one value per iso3)
    den = exp.drop_duplicates("iso3")
    w_v_all = suez_exp["v_canal"].sum() / den["v_sea_predict"].sum()
    w_q_all = suez_exp["q_canal"].sum() / den["q_sea_predict"].sum()
    checks.append(numeric_check("world_suez_export_share_value_alldenom",
                                "As above, denominator summed over all economies in the export file",
                                "0.1643", w_v_all, 4))
    checks.append(numeric_check("world_suez_export_share_quantity_alldenom",
                                "As above, denominator summed over all economies in the export file",
                                "0.1287", w_q_all, 4))

    # OECD economies without v3 data (needs the verified OECD extract)
    no_v3_def = ("OECD areas (excl. W, OECD, W_O) with any RES_TOTAL or TER_INT value, ALL_VESSELS, "
                 f"{C.PRE_START}..{C.MAIN_END}, absent from both v3 files")
    if is_verified(C.OECD_FILE) and C.OECD_MONTHLY.exists():
        m = pd.read_csv(C.OECD_MONTHLY, usecols=["area", "vessel", "source", "period"])
        m = m[(m["vessel"] == "ALL_VESSELS") & m["source"].isin(["RES_TOTAL", "TER_INT"])
              & m["period"].between(C.PRE_START, C.MAIN_END) & ~m["area"].isin(C.NON_ECONOMY_AREAS)]
        v3_iso = set(exp["iso3"]) | set(imp["iso3"])
        no_v3 = sorted(set(m["area"]) - v3_iso)
        checks.append(exact_check("oecd_without_v3_count", no_v3_def + "; count", 31, len(no_v3)))
        checks.append(exact_check("oecd_without_v3_list", no_v3_def + "; codes",
                                  " ".join(EXPECTED_NO_V3), " ".join(no_v3)))
    else:
        for name, e in (("oecd_without_v3_count", 31), ("oecd_without_v3_list", " ".join(EXPECTED_NO_V3))):
            checks.append(dict(check=name, definition=no_v3_def, expected=str(e),
                               obtained="not run: OECD raw file not verified", abs_diff="NA",
                               **{"pass": False}))

    write_checks(checks, C.CHECKS / "verschuur_checks.csv")


if __name__ == "__main__":
    main()
