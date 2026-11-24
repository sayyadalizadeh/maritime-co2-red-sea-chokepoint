"""Extract monthly OECD maritime CO2 series and run structural checks.

Outputs
- data/interim/oecd_monthly.csv.gz   area, area_name, vessel, source, period, value_t
- outputs/checks/oecd_coverage.csv   one row per area x source x vessel
- outputs/checks/oecd_checks.csv     expected against obtained values

The script stops if the raw OECD file did not pass the checksum test.
"""

import pandas as pd

import config as C
from common import (exact_check, numeric_check, range_check, rel,
                    require_verified, write_checks)

USECOLS = ["REF_AREA", "Reference area", "FREQ", "VESSEL",
           "VESSEL_EMISSIONS_SOURCE", "TIME_PERIOD", "OBS_VALUE"]

COMPONENTS = {
    "A": "RES_DOM_IN", "B": "RES_DOM_OUT", "C": "NRES_DOM_IN",
    "D": "RES_INT_FROM", "E": "RES_INT_TO", "F": "RES_INT_OUT",
    "G": "NRES_INT_FROM",
}
AGGREGATES = ["RES_TOTAL", "TER_DOM", "TER_INT"]
MAIN_VESSEL = "ALL_VESSELS"
MT = 1e6  # tonnes per Mt


def window_months(start, end):
    return pd.period_range(start, end, freq="M").strftime("%Y-%m").tolist()


def series(m, area, source, vessel=MAIN_VESSEL):
    s = m[(m["area"] == area) & (m["source"] == source) & (m["vessel"] == vessel)]
    return s.set_index("period")["value_t"].sort_index()


def wide(m, sources, vessel=MAIN_VESSEL, areas=None):
    """period x area (or period x source) tables for the main vessel aggregate."""
    s = m[(m["vessel"] == vessel) & (m["source"].isin(sources))]
    if areas is not None:
        s = s[s["area"].isin(areas)]
    return s.pivot_table(index=["area", "period"], columns="source",
                         values="value_t", aggfunc="first")


def main():
    require_verified(C.OECD_FILE)

    checks = []

    # ---- structure (all frequencies) ------------------------------------
    raw = pd.read_csv(C.OECD_FILE, usecols=USECOLS, dtype={"OBS_VALUE": float},
                      low_memory=False)
    checks.append(exact_check("rows_all", "All data rows in the file", 427861, len(raw)))
    checks.append(exact_check("areas", "Distinct REF_AREA codes", 219, raw["REF_AREA"].nunique()))
    by_freq = raw["FREQ"].value_counts()
    for f, exp in (("M", 301378), ("Q", 102346), ("A", 24137)):
        checks.append(exact_check(f"rows_freq_{f}", f"Rows with FREQ == {f}", exp,
                                  int(by_freq.get(f, 0))))

    units = pd.read_csv(C.OECD_FILE, usecols=["UNIT_MEASURE", "UNIT_MULT"], dtype=str)
    unit_vals = "; ".join(sorted(
        (units["UNIT_MEASURE"].fillna("NA") + "/" + units["UNIT_MULT"].fillna("NA")).unique()))
    checks.append(exact_check("units", "Distinct UNIT_MEASURE/UNIT_MULT pairs", "T/0", unit_vals))
    del units

    # ---- monthly extract ------------------------------------------------
    m = raw[raw["FREQ"] == "M"].rename(columns={
        "REF_AREA": "area", "Reference area": "area_name", "VESSEL": "vessel",
        "VESSEL_EMISSIONS_SOURCE": "source", "TIME_PERIOD": "period",
        "OBS_VALUE": "value_t"})
    del raw
    n_missing_value = int(m["value_t"].isna().sum())
    m = m.dropna(subset=["value_t"])
    m = m[["area", "area_name", "vessel", "source", "period", "value_t"]]
    m = m.sort_values(["area", "vessel", "source", "period"]).reset_index(drop=True)
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    m.to_csv(C.OECD_MONTHLY, index=False, compression="gzip")
    print(f"{rel(C.OECD_MONTHLY)}: {len(m)} rows ({n_missing_value} monthly rows with empty value dropped)")

    # ---- coverage -------------------------------------------------------
    win = window_months(C.PRE_START, C.MAIN_END)
    in_win = m[m["period"].isin(win)]
    cov = m.groupby(["area", "source", "vessel"]).agg(
        area_name=("area_name", "first"), first_month=("period", "min"),
        last_month=("period", "max"), n_months=("period", "nunique")).reset_index()
    n_win = in_win.groupby(["area", "source", "vessel"])["period"].nunique()
    cov["n_months_window"] = cov.set_index(["area", "source", "vessel"]).index.map(n_win).fillna(0).astype(int)
    cov["complete_2019_01_2025_10"] = cov["n_months_window"] == len(win)
    pre = window_months(C.PRE_START, C.PRE_END)
    n_pre = m[m["period"].isin(pre)].groupby(["area", "source", "vessel"])["period"].nunique()
    cov["n_months_pre"] = cov.set_index(["area", "source", "vessel"]).index.map(n_pre).fillna(0).astype(int)
    cov = cov[["area", "area_name", "source", "vessel", "first_month", "last_month",
               "n_months", "n_months_window", "complete_2019_01_2025_10", "n_months_pre"]]
    C.CHECKS.mkdir(parents=True, exist_ok=True)
    cov.to_csv(C.CHECKS / "oecd_coverage.csv", index=False)
    print(f"{rel(C.CHECKS / 'oecd_coverage.csv')}: {len(cov)} rows")

    # ---- coverage checks ------------------------------------------------
    w_res = series(m, "W", "RES_TOTAL")
    checks.append(exact_check("W_RES_TOTAL_first", "First month, W RES_TOTAL ALL_VESSELS", "2019-01", w_res.index.min()))
    checks.append(exact_check("W_RES_TOTAL_last", "Last month, W RES_TOTAL ALL_VESSELS", "2026-09", w_res.index.max()))
    checks.append(exact_check("W_RES_TOTAL_n", "Number of months, W RES_TOTAL ALL_VESSELS", 93, len(w_res)))
    mv = m[m["vessel"] == MAIN_VESSEL]
    for code in list(COMPONENTS.values()) + ["TER_DOM", "TER_INT"]:
        last = mv.loc[mv["source"] == code, "period"].max()
        checks.append(exact_check(f"last_month_{code}", f"Latest month of {code} in any area, ALL_VESSELS",
                                  "2026-06", last))

    # ---- world totals ---------------------------------------------------
    year = w_res.index.str[:4]
    annual = w_res.groupby(year).sum() / MT
    for y, exp in zip(range(2019, 2026), ["889.391", "854.614", "893.612", "911.824",
                                          "920.036", "972.682", "985.924"]):
        checks.append(numeric_check(f"W_RES_TOTAL_{y}", f"Sum of monthly W RES_TOTAL ALL_VESSELS in {y}, Mt",
                                    exp, annual.get(str(y)), 3))
    for p, exp in (("2023-11", "75.792"), ("2023-12", "78.055"), ("2024-01", "79.142"),
                   ("2025-09", "86.811"), ("2025-10", "84.096"), ("2026-02", "75.716")):
        checks.append(numeric_check(f"W_RES_TOTAL_{p}", f"W RES_TOTAL ALL_VESSELS in {p}, Mt",
                                    exp, w_res.get(p, float("nan")) / MT, 3))
    w_cont = series(m, "W", "RES_TOTAL", "CONTAINER")
    cont_annual = w_cont.groupby(w_cont.index.str[:4]).sum() / MT
    for y, exp in ((2023, "210.985"), (2024, "245.204"), (2025, "254.296")):
        checks.append(numeric_check(f"W_RES_TOTAL_CONTAINER_{y}", f"Sum of monthly W RES_TOTAL CONTAINER in {y}, Mt",
                                    exp, cont_annual.get(str(y)), 3))

    # ---- economies ------------------------------------------------------
    econ_exp = {
        ("CHE", "RES_TOTAL"): ("39.53", "47.71", "52.88"),
        ("DNK", "RES_TOTAL"): ("45.49", "47.96", "46.95"),
        ("EGY", "TER_INT"): ("25.97", "13.46", "13.22"),
        ("MYS", "TER_INT"): ("47.29", "61.65", "72.28"),
    }
    for (area, src), exps in econ_exp.items():
        s = series(m, area, src)
        ann = s.groupby(s.index.str[:4]).sum() / MT
        for y, exp in zip((2023, 2024, 2025), exps):
            checks.append(numeric_check(f"{area}_{src}_{y}", f"Sum of monthly {area} {src} ALL_VESSELS in {y}, Mt",
                                        exp, ann.get(str(y)), 3))

    # ---- panel counts ---------------------------------------------------
    econ_win = in_win[(in_win["vessel"] == MAIN_VESSEL) & (~in_win["area"].isin(C.NON_ECONOMY_AREAS))]
    n_by = econ_win.groupby(["source", "area"])["period"].nunique()
    complete = {}
    for src, exp_any, exp_comp in (("RES_TOTAL", 159, 140), ("TER_INT", 178, 137)):
        counts = n_by.loc[src] if src in n_by.index.get_level_values(0) else pd.Series(dtype=int)
        complete[src] = set(counts[counts == len(win)].index)
        checks.append(exact_check(f"panel_{src}_any", f"Economies with any {src} value in {C.PRE_START}..{C.MAIN_END}",
                                  exp_any, len(counts)))
        checks.append(exact_check(f"panel_{src}_complete", f"Economies with all {len(win)} months of {src} in the window",
                                  exp_comp, len(complete[src])))
    checks.append(exact_check("panel_both_complete", "Economies complete in both RES_TOTAL and TER_INT",
                              133, len(complete["RES_TOTAL"] & complete["TER_INT"])))
    checks.append(exact_check("CHE_RES_TOTAL_complete", "CHE RES_TOTAL complete in the window",
                              True, "CHE" in complete["RES_TOTAL"]))
    che_ter = int(n_by.get(("TER_INT", "CHE"), 0))
    checks.append(exact_check("CHE_TER_INT_months", "Months with a CHE TER_INT value in the window", 4, che_ter))

    # ---- data features --------------------------------------------------
    econ = mv[~mv["area"].isin(C.NON_ECONOMY_AREAS)]
    res = econ[econ["source"] == "RES_TOTAL"].pivot(index="area", columns="period", values="value_t")
    ter_parts = econ[econ["source"].isin(["TER_DOM", "TER_INT"])].pivot_table(
        index=["area", "period"], columns="source", values="value_t")
    ter = (ter_parts["TER_DOM"] + ter_parts["TER_INT"]).unstack("period")  # NaN if either is missing

    # September anomaly: per-day values, economies complete in the window
    n_dom = econ_win.groupby(["source", "area"])["period"].nunique()
    dom_counts = n_dom.loc["TER_DOM"] if "TER_DOM" in n_dom.index.get_level_values(0) else pd.Series(dtype=int)
    complete_dom = set(dom_counts[dom_counts == len(win)].index)
    panel_res = complete["RES_TOTAL"]
    panel_ter = complete["TER_INT"] & complete_dom

    def sep_ratio(tab, y, panel):
        cols = [f"{y}-08", f"{y}-09", f"{y}-10"]
        if not all(c in tab.columns for c in cols):
            return float("nan")
        t = tab.loc[tab.index.isin(panel), cols]
        aug, sep, oct_ = t[cols[0]] / 31, t[cols[1]] / 30, t[cols[2]] / 31
        return (sep / ((aug + oct_) / 2)).median()

    sep_def = ("Median across economies of per-day Sep / mean(per-day Aug, per-day Oct) "
               "(Aug 31, Sep 30, Oct 31 days); ALL_VESSELS; economies complete in "
               f"{C.PRE_START}..{C.MAIN_END} (residence: RES_TOTAL; territory: TER_DOM and TER_INT); "
               "territory = TER_DOM + TER_INT")
    for basis, tab, panel, exp25, lo, hi in (
            ("residence", res, panel_res, "1.0415", 1.0000, 1.0060),
            ("territory", ter, panel_ter, "1.0519", 0.9762, 1.0071)):
        r = {y: sep_ratio(tab, y, panel) for y in range(2019, 2026)}
        checks.append(numeric_check(f"sep_anomaly_{basis}_2025", sep_def + f"; {len(panel)} economies",
                                    exp25, r[2025], 4, tol=0.0001))
        checks.append(range_check(f"sep_anomaly_{basis}_2019_2024", sep_def + "; range over 2019-2024",
                                  f"{lo:.4f}", f"{hi:.4f}", [r[y] for y in range(2019, 2025)], 4, tol=0.0001))

    # World domestic / international share
    w_dom, w_int = series(m, "W", "TER_DOM"), series(m, "W", "TER_INT")
    share_level = "W"
    if w_dom.empty or w_int.empty:
        share_level = "sum of economies"
        g = econ[econ["source"].isin(["TER_DOM", "TER_INT"])].groupby(["source", "period"])["value_t"].sum()
        w_dom, w_int = g.loc["TER_DOM"], g.loc["TER_INT"]
    dom_share = (w_dom / (w_dom + w_int) * 100).dropna()
    int_share = 100 - dom_share
    d_def = f"TER_DOM / (TER_DOM + TER_INT) x 100, {share_level}, ALL_VESSELS"
    for p, exp in (("2025-12", "26.5"), ("2026-06", "37.1")):
        checks.append(numeric_check(f"world_dom_share_{p}", d_def + f", {p}", exp, dom_share.get(p), 1))
    i_def = f"100 - domestic share, {share_level}, ALL_VESSELS"
    pre = int_share[(int_share.index >= "2019-02") & (int_share.index <= "2021-10")
                    & (int_share.index.str[5:7] != "01")]
    checks.append(range_check("world_int_share_2019_02_2021_10_excl_jan",
                              i_def + "; range 2019-02..2021-10, January months excluded",
                              "73.1", "75.1", pre.tolist(), 1, tol=0.05))
    for p, exp in (("2019-01", "69.3"), ("2020-01", "69.8"), ("2021-01", "70.1")):
        checks.append(numeric_check(f"world_int_share_{p}", i_def + f", {p}", exp, int_share.get(p), 1, tol=0.05))
    checks.append(numeric_check("world_int_share_2021_11", i_def + ", 2021-11", "72.1", int_share.get("2021-11"), 1))
    post = int_share[(int_share.index >= "2021-12") & (int_share.index <= "2022-10")]
    checks.append(range_check("world_int_share_2021_12_2022_10", i_def + "; range 2021-12..2022-10",
                              "64.4", "67.6", post.tolist(), 1, tol=0.05))
    checks.append(numeric_check("world_int_share_2023_11", i_def + ", 2023-11", "62.9",
                                int_share.get("2023-11"), 1, tol=0.05))

    # Residence total against components; world balance
    comp_codes = list(COMPONENTS.values())
    w_comp = mv[(mv["area"] == "W") & (mv["source"].isin(comp_codes + ["RES_TOTAL"]))].pivot(
        index="period", columns="source", values="value_t")
    if all(c in w_comp.columns for c in comp_codes):
        comp_level = "W"
        tab = w_comp
    else:
        comp_level = "sum of economies (W has no components)"
        sub = econ[econ["source"].isin(comp_codes)]
        tab = sub.groupby(["period", "source"])["value_t"].sum().unstack("source")
        tab["RES_TOTAL"] = w_res
    A, B, Cc, D, E, F, G = (tab[COMPONENTS[k]] for k in "ABCDEFG")
    gap = (tab["RES_TOTAL"] / (A + B + D + E + F) - 1) * 100
    gap = gap.dropna()
    nonpos = gap[gap <= 0]
    first_pos_run = gap.index[gap.index > nonpos.index.max()].min() if not nonpos.empty else gap.index.min()
    g_def = f"(RES_TOTAL / (A+B+D+E+F) - 1) x 100, {comp_level}, ALL_VESSELS"
    checks.append(exact_check("res_vs_components_positive_from", g_def + "; first month from which the gap stays > 0",
                              "2025-02", first_pos_run))
    checks.append(numeric_check("res_vs_components_max", g_def + f"; maximum (in {gap.idxmax()})",
                                "0.72", gap.max(), 2))
    checks.append(exact_check("res_vs_components_max_month", g_def + "; month of the maximum", "2025-09", gap.idxmax()))

    bc = (B - Cc).abs().dropna()
    checks.append(exact_check("world_balance_B_eq_C", f"max |B - C| over months <= 0.001 t, {comp_level}",
                              True, bool(bc.max() <= 1e-3) if not bc.empty else "NA"))
    efg = ((E + F) / G - 1).dropna() * 100
    checks.append(range_check("world_balance_EF_over_G", f"((E + F) / G - 1) x 100 by month, {comp_level}; range",
                              0.06, 0.17, efg.tolist(), 2))

    write_checks(checks, C.CHECKS / "oecd_checks.csv")

    # ---- diagnostics (not checks) ---------------------------------------
    sep_anomaly_detail(res, ter, cov)
    world_shares_monthly(dom_share, share_level)
    world_by_vessel(m)


def sep_anomaly_detail(res, ter, cov):
    """September ratio under the check definition and two variants.

    variant per_day: each month divided by its number of days first.
    variant balanced_per_day: per_day, restricted to economies complete in
    2019-01..2025-10 for the series (RES_TOTAL; for territory TER_INT).
    """
    complete = cov[(cov["vessel"] == MAIN_VESSEL) & cov["complete_2019_01_2025_10"]
                   & ~cov["area"].isin(C.NON_ECONOMY_AREAS)]
    rows = []
    for basis, tab, src in (("residence", res, "RES_TOTAL"), ("territory", ter, "TER_INT")):
        bal = set(complete.loc[complete["source"] == src, "area"])
        for y in range(2019, 2026):
            cols = [f"{y}-08", f"{y}-09", f"{y}-10"]
            t = tab[cols].dropna()
            t = t[(t > 0).all(axis=1)]
            ratio = t[cols[1]] / ((t[cols[0]] + t[cols[2]]) / 2)
            per_day = (t[cols[1]] / 30) / ((t[cols[0]] / 31 + t[cols[2]] / 31) / 2)
            rows.append({"basis": basis, "year": y, "n_economies": len(t),
                         "median_ratio": round(ratio.median(), 4),
                         "median_ratio_per_day": round(per_day.median(), 4),
                         "n_economies_balanced": int(t.index.isin(bal).sum()),
                         "median_ratio_balanced_per_day": round(per_day[t.index.isin(bal)].median(), 4)})
    out = pd.DataFrame(rows)
    out.to_csv(C.CHECKS / "oecd_sep_anomaly_detail.csv", index=False)
    print(f"{rel(C.CHECKS / 'oecd_sep_anomaly_detail.csv')}: {len(out)} rows")


def world_shares_monthly(dom_share, level):
    out = pd.DataFrame({"period": dom_share.index,
                        "domestic_share_pct": dom_share.round(2).values,
                        "international_share_pct": (100 - dom_share).round(2).values,
                        "level": level})
    out.to_csv(C.CHECKS / "oecd_world_shares_monthly.csv", index=False)
    print(f"{rel(C.CHECKS / 'oecd_world_shares_monthly.csv')}: {len(out)} rows")


def world_by_vessel(m):
    """World RES_TOTAL by vessel code: coverage, annual sums (Mt), consistency."""
    labels = pd.read_csv(C.OECD_FILE, usecols=["VESSEL", "Vessel"], dtype=str).drop_duplicates()
    labels = labels.groupby("VESSEL")["Vessel"].first()
    w = m[m["area"] == "W"]
    years = ("2023", "2024", "2025")
    rows = []
    for vessel in sorted(w["vessel"].unique()):
        s = w[(w["vessel"] == vessel) & (w["source"] == "RES_TOTAL")]
        s = s.set_index("period")["value_t"].sort_index()
        ann = s.groupby(s.index.str[:4]).sum() / MT
        full = s.groupby(s.index.str[:4]).size()
        row = {"vessel": vessel, "vessel_label": labels.get(vessel, ""),
               "first_month": s.index.min() if len(s) else "",
               "last_month": s.index.max() if len(s) else "", "n_months": len(s)}
        for y in years:
            row[f"mt_{y}"] = round(ann[y], 3) if full.get(y, 0) == 12 else float("nan")
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(C.CHECKS / "oecd_world_by_vessel.csv", index=False)
    print(f"{rel(C.CHECKS / 'oecd_world_by_vessel.csv')}: {len(out)} rows")

    # Consistency: do the ship types add up to the aggregates?
    aggregates = {"ALL_VESSELS", "ALL_VESSELSXMISC_FISH"}
    types = [v for v in w["vessel"].unique() if v not in aggregates]
    res_comp = ["RES_DOM_IN", "RES_DOM_OUT", "RES_INT_FROM", "RES_INT_TO", "RES_INT_OUT"]

    def annual(vessels, sources):
        s = w[w["vessel"].isin(vessels) & w["source"].isin(sources)]
        s = s[s["period"].str[:4].isin(years)]
        return s.groupby(s["period"].str[:4])["value_t"].sum() / MT

    no_fish = [t for t in types if t != "MISC_FISH"]
    comparisons = [
        ("sum of ship types vs ALL_VESSELS", "RES_TOTAL", len(types),
         annual(types, ["RES_TOTAL"]), annual(["ALL_VESSELS"], ["RES_TOTAL"])),
        ("sum of ship types vs ALL_VESSELS", "A+B+D+E+F", len(types),
         annual(types, res_comp), annual(["ALL_VESSELS"], res_comp)),
        ("sum of ship types except MISC_FISH vs ALL_VESSELSXMISC_FISH", "A+B+D+E+F", len(no_fish),
         annual(no_fish, res_comp), annual(["ALL_VESSELSXMISC_FISH"], res_comp)),
        ("ALL_VESSELS minus MISC_FISH vs ALL_VESSELSXMISC_FISH", "A+B+D+E+F", "",
         annual(["ALL_VESSELS"], res_comp) - annual(["MISC_FISH"], res_comp),
         annual(["ALL_VESSELSXMISC_FISH"], res_comp)),
    ]
    crow = []
    for name, measure, n_types, parts, total in comparisons:
        for y in years:
            p, t = parts.get(y, float("nan")), total.get(y, float("nan"))
            crow.append({"comparison": name, "measure": measure, "year": y,
                         "n_types_summed": n_types,
                         "parts_mt": round(p, 3), "aggregate_mt": round(t, 3),
                         "gap_mt": round(p - t, 3), "gap_pct": round((p / t - 1) * 100, 3)})
    cons = pd.DataFrame(crow)
    cons.to_csv(C.CHECKS / "oecd_world_by_vessel_consistency.csv", index=False)
    print(f"{rel(C.CHECKS / 'oecd_world_by_vessel_consistency.csv')}: {len(cons)} rows")


if __name__ == "__main__":
    import time
    t0 = time.perf_counter()
    main()
    elapsed = time.perf_counter() - t0
    try:
        import psutil
        peak = psutil.Process().memory_info().peak_wset / 2**20  # Windows only
        print(f"Run time {elapsed:.1f} s; peak working set {peak:.0f} MiB")
    except (ImportError, AttributeError):
        print(f"Run time {elapsed:.1f} s")
