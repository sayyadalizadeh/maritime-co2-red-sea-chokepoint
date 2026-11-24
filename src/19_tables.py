"""Manuscript tables (CSV) from the existing outputs (no estimate changes).

Main tables in outputs/manuscript_tables/, supplementary tables in
outputs/manuscript_tables/supplementary/, one-line notes in
outputs/manuscript_tables/table_notes.md. File names describe content; final
numbering is assigned when the text is written.
"""

import time

import numpy as np
import pandas as pd

import config as C
from common import rel

T = C.OUTPUTS / "tables"
K = C.CHECKS
OUT = C.OUTPUTS / "manuscript_tables"
SUPP = OUT / "supplementary"
MT = 1e6
NOTES = []

VARIANTS_RUN = {"residence": ["R1", "R2", "R3", "R7", "R8", "R9", "R10", "R11"],
                "departure": ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]}


def write(df, name, note, supplementary=False):
    d = SUPP if supplementary else OUT
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.csv"
    df.to_csv(path, index=False)
    NOTES.append((supplementary, name, len(df), note))
    print(f"{rel(path)}: {len(df)} rows")
    return path


def groups_str(r):
    return " ".join(g.upper() for g in ("rsl", "cpa", "hq", "eea", "rus") if bool(r[g]))


def tab_data_panels():
    man = pd.read_csv(C.DATA / "MANIFEST.csv")
    pc = pd.read_csv(K / "panel_checks.csv", dtype=str).set_index("check")
    ec = pd.read_csv(K / "exposure_checks.csv", dtype=str).set_index("check")
    am = pd.read_csv(K / "anomaly_months.csv")
    rows = []
    src = {"oecd": "OECD", "portwatch": "PortWatch", "verschuur": "Verschuur & Hall v3", "unctad": "UNCTADstat"}
    seen = set()
    for _, r in man.iterrows():
        key = next(k for k in src if k in r["path"])
        if key in seen:
            continue
        seen.add(key)
        rows.append({"section": "source", "item": src[key], "value": r["source"],
                     "detail": f"version {r['version']}; release {r['release_date']}; download {r['download_date']}; "
                               f"licence {r['licence']}", "source_file": "data/MANIFEST.csv"})
    rows += [
        {"section": "window", "item": "pre-crisis", "value": f"{C.PRE_START} to {C.PRE_END}", "source_file": "src/config.py"},
        {"section": "window", "item": "shock month", "value": C.SHOCK_START, "source_file": "src/config.py"},
        {"section": "window", "item": "main estimation end", "value": C.MAIN_END, "source_file": "src/config.py"},
        {"section": "window", "item": "residence sensitivity end", "value": C.SENS_END_RESIDENCE,
         "source_file": "src/config.py"},
    ]
    for p, src_s in (("residence", "RES_TOTAL"), ("departure", "TER_INT")):
        n = pc.loc[f"{p}_economies", "obtained"]
        rows.append({"section": f"panel, {p}", "item": f"economies complete in {src_s}, 2019-01..2025-10",
                     "value": n, "source_file": "outputs/checks/panel_checks.csv"})
        rows.append({"section": f"panel, {p}", "item": "economies with exposure data", "value":
                     ec.loc[f"{p}_n_with_exposure", "obtained"], "source_file": "outputs/checks/exposure_checks.csv"})
        rows.append({"section": f"panel, {p}", "item": "control pool (bottom exposure tercile, excluding RSL, CPA, HQ, RUS)",
                     "value": ec.loc[f"{p}_pool_size", "obtained"],
                     "detail": f"cut-off {ec.loc[f'{p}_cutoff', 'obtained']}",
                     "source_file": "outputs/checks/exposure_checks.csv"})
        sw = am[(am["principle"] == p) & (am["window"] == "main") & am["system_wide"]]["period"].tolist()
        excl = "2023-11 (RS-D14 fixed exclusion)" if p == "departure" else "none"
        rows.append({"section": f"panel, {p}", "item": "excluded months", "value": excl,
                     "detail": "system-wide anomalous months (RS-D14 scan): " + (", ".join(sw) or "none"),
                     "source_file": "outputs/checks/anomaly_months.csv"})
    rows.append({"section": "panel, both", "item": "economies complete in both series",
                 "value": pc.loc["common_economies", "obtained"], "source_file": "outputs/checks/panel_checks.csv"})
    rows.append({"section": "world", "item": "ship types", "value": "10 transit (treated), 8 non-transit (controls); "
                 "CRUISE described only", "source_file": "src/11_rsd2_world.py"})
    rows.append({"section": "Panama term", "item": "restriction months R", "value": "2023-11 to 2024-07",
                 "source_file": "outputs/checks/estimation_checks.csv"})
    return write(pd.DataFrame(rows), "tab_data_panels",
                 "Data sources, windows, panel sizes, control pools and excluded months. Sources: data/MANIFEST.csv, "
                 "src/config.py, outputs/checks/panel_checks.csv, exposure_checks.csv, anomaly_months.csv, "
                 "estimation_checks.csv.")


def tab_system():
    s = pd.read_csv(T / "rsd2_summary.csv")
    t = pd.read_csv(T / "rsd2_types.csv").set_index("vessel")
    tb = pd.read_csv(T / "rsd2_types_B1.csv").set_index("vessel")
    rows = []
    for _, r in s.iterrows():
        rows.append({"run": r["run"], "spec": r["spec"], "scope": "total of treated types",
                     "excess_Mt": r["excess_Mt"], "pct": r["pct"], "excess_2023_Mt": r["excess_2023_Mt"],
                     "excess_2024_Mt": r["excess_2024_Mt"], "excess_2025_Mt": r["excess_2025_Mt"],
                     "placebo_band_Mt_min": r["placebo_band_Mt_min"], "placebo_band_Mt_max": r["placebo_band_Mt_max"],
                     "placebo_band_pct_min": r["placebo_band_pct_min"], "placebo_band_pct_max": r["placebo_band_pct_max"],
                     "robust": r["total_robust"], "excess_panama_normal_Mt": r["excess_panama_normal_Mt"]})
    # S2 yearly sums of CONTAINER: the W0 estimates of 13_robustness_world.py (same data and specification
    # as rsd2_types.csv); the yearly sums must add up to the window total
    wc = pd.read_csv(T / "robustness_world_container.csv").set_index(["variant", "run", "spec"])
    for run, tt in (("main", t), ("B1", tb)):
        c = tt.loc["CONTAINER"]
        for spec in ("S1", "S2"):
            row = {"run": run, "spec": spec, "scope": "CONTAINER", "excess_Mt": c[f"excess_total_t_{spec}"] / MT,
                   "pct": c[f"pct_{spec}"], "robust": bool(c["robust"]),
                   "max_abs_placebo_pct": c["max_abs_placebo"]}
            if spec == "S1":
                row.update({f"excess_{y}_Mt": c[f"excess_{y}_S1"] / MT for y in ("2023", "2024", "2025")})
            else:
                w0 = wc.loc[("W0", run, "S2")]
                years = {f"excess_{y}_Mt": w0[f"container_excess_{y}_Mt"] for y in ("2023", "2024", "2025")}
                gap = abs(sum(years.values()) - row["excess_Mt"])
                if gap > 1e-6:
                    raise RuntimeError(f"tab_system: {run} S2 CONTAINER yearly sums differ from the window total "
                                       f"by {gap:.3g} Mt")
                row.update(years)
            rows.append(row)
    df = pd.DataFrame(rows)
    num = df.select_dtypes("number").columns
    df[num] = df[num].round(3)
    return write(df, "tab_system",
                 "World (W) RES_TOTAL by ship type, RS-D2 main run (transit types treated) and benchmark B1 "
                 "(CONTAINER treated), S1 and S2; excess 2023-12..2025-10 (2023 = December, 2025 = January-October); "
                 "placebo band = [min, max] of the 10 aggregate placebo % applied to the counterfactual total; robust "
                 "per RS-D16; Panama-normal = excess summed over 2024-08..2025-10. Sources: outputs/tables/"
                 "rsd2_summary.csv, rsd2_types.csv, rsd2_types_B1.csv.")


def tab_robust_economies():
    xu = pd.read_csv(T / "xu_gsc.csv").set_index(["principle", "iso3"])
    ch = pd.read_csv(T / "robustness_robust_changes.csv")
    fp = pd.read_csv(T / "false_positive_by_economy.csv").set_index(["principle", "iso3"])
    rows = []
    for p in ("residence", "departure"):
        u = pd.read_csv(T / f"rsd4_{p}_units.csv")
        for _, r in u[u["robust"]].sort_values("excess_total_t_S1").iterrows():
            iso = r["iso3"]
            runs = ch[(ch["principle"] == p) & ch["variant"].isin(VARIANTS_RUN[p])]
            stays = [v for v, lst in zip(runs["variant"], runs["robust_list"].fillna("")) if iso in lst.split()]
            dropped = {v for v, lst in zip(runs["variant"], runs["lost_not_estimated"].fillna(""))
                       if iso in lst.split()}
            x = xu.loc[(p, iso)]
            rows.append({"principle": p, "iso3": iso, "groups": groups_str(r),
                         "S1_excess_Mt": r["excess_total_t_S1"] / MT, "S1_pct": r["pct_S1"],
                         "S2_excess_Mt": r["excess_total_t_S2"] / MT, "S2_pct": r["pct_S2"],
                         "max_abs_placebo_pct": r["max_abs_placebo"],
                         "xu_excess_Mt": x["excess_Mt"], "xu_pct": x["pct"], "xu_exceeds_placebo": bool(x["exceeds_placebo"]),
                         "robust_in_variants": f"{len(stays)} of {len(VARIANTS_RUN[p])}",
                         "variants_not_robust": " ".join(v + (" (not estimated)" if v in dropped else "")
                                                         for v in VARIANTS_RUN[p] if v not in stays),
                         "n_dates_pseudo_robust": int(fp.loc[(p, iso), "n_dates_pseudo_robust"])})
    df = pd.DataFrame(rows)
    num = df.select_dtypes("number").columns
    df[num] = df[num].round(2)
    return write(df, "tab_robust_economies",
                 "Economies robust (RS-D16) under either principle, R0: S1 and S2 window excess (Mt, % of "
                 "counterfactual), max |placebo %| over the 10 placebo runs, Xu (2017) generalized synthetic control "
                 "(RS-D20, r from 0..5), and the number of robustness variants R1-R11 run for that principle in which "
                 "the economy stays robust (residence: R1 R2 R3 R7 R8 R9 R10 R11; departure: R1-R10; an economy "
                 "dropped by a variant counts as not robust), and the number of placebo dates (0-5) at which the "
                 "economy is pseudo-robust in the false-positive calibration (RS-D23). Sources: outputs/tables/"
                 "rsd4_<principle>_units.csv, xu_gsc.csv, robustness_robust_changes.csv, "
                 "false_positive_by_economy.csv.")


def tab_rq3():
    c = pd.read_csv(T / "rq3_coefficients.csv")
    c = c[c["variant"] == "weighted"]
    terms = ["const", "x_v", "e_res", "hq", "rsl", "cpa"]
    rows = []
    for term in terms + ["n", "r2"]:
        row = {"term": term}
        for p in ("departure", "residence"):
            for spec in ("S1", "S2"):
                s = c[(c["principle"] == p) & (c["spec"] == spec)]
                if term in ("n", "r2"):
                    row[f"{p}_{spec}"] = f"{s[term].iloc[0]:.0f}" if term == "n" else f"{s[term].iloc[0]:.3f}"
                else:
                    s = s[s["term"] == term]
                    row[f"{p}_{spec}"] = f"{s['coef'].iloc[0]:.3f} ({s['se_hc3'].iloc[0]:.3f})" if len(s) else ""
        rows.append(row)
    return write(pd.DataFrame(rows), "tab_rq3",
                 "RQ3 (RS-D18): weighted least squares of the window excess % (R0) on exposure and group indicators, "
                 "non-control economies, weights = window counterfactual of the same specification; coefficient "
                 "(HC3 standard error). Associations, not causal effects. Source: outputs/tables/rq3_coefficients.csv.")


def supplementary():
    for p in ("residence", "departure"):
        u = pd.read_csv(T / f"rsd4_{p}_units.csv")
        write(u, f"stab_economies_{p}", f"All economy results, {p} principle, R0 (S1, S2, by year, 10 placebo %, "
              f"max |placebo %|, robust). Source: outputs/tables/rsd4_{p}_units.csv.", True)
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    r9 = pd.read_csv(K / "robustness_r9_pools.csv")
    write(ex, "stab_exposure", "Exposure measures (x_v, x_q, m_v, Bab el-Mandeb share), pre-crisis component sums "
          "A, B, D, E, F (t), e_res, panel and group flags, control pools. Source: data/interim/exposure.csv "
          "(src/07_exposure.py).", True)
    write(r9, "stab_control_pools_quantity", "Control pools under quantity-based exposure (R9) and changes against "
          "the value-based pools. Source: outputs/checks/robustness_r9_pools.csv.", True)
    write(pd.read_csv(T / "robustness_economies.csv"), "stab_robustness_economies",
          "Robustness variants R0-R14, economies, both principles, S1 and S2. Source: outputs/tables/"
          "robustness_economies.csv.", True)
    write(pd.read_csv(T / "robustness_robust_changes.csv"), "stab_robustness_robust_changes",
          "Robust economies gained and lost against R0 per variant. Source: outputs/tables/robustness_robust_changes.csv.",
          True)
    rw = pd.read_csv(T / "robustness_world.csv")
    wc = pd.read_csv(T / "robustness_world_container.csv")
    wc = wc[wc["spec"] == "S1"].set_index(["variant", "run"])["container_max_abs_placebo_pct"]
    # maximum |placebo %| of CONTAINER over the placebo runs of each estimated variant (W0-W2);
    # W3 and W4 re-sum W0 and have no placebo runs of their own (empty)
    rw["container_max_abs_placebo_pct"] = [wc.get((v, r), np.nan) for v, r in zip(rw["variant"], rw["run"])]
    write(rw, "stab_robustness_world",
          "Robustness variants W0-W4, world, main run and B1. Source: outputs/tables/robustness_world.csv.", True)
    write(pd.read_csv(T / "rq3_coefficients.csv"), "stab_rq3_variants",
          "RQ3 coefficients, all variants (weighted, unweighted, weighted excluding counterfactual < 1 Mt), S1 and S2, "
          "HC3 SE and 95% intervals. Source: outputs/tables/rq3_coefficients.csv.", True)
    write(pd.read_csv(T / "rq3_decomposition.csv"), "stab_rq3_decomposition",
          "Excess by group and by exposure tercile, and the robust share of gross gains and losses. Source: "
          "outputs/tables/rq3_decomposition.csv.", True)
    write(pd.read_csv(T / "within_eea.csv"), "stab_within_eea",
          "Within-EEA estimates (RS-D19) per EEA economy with R0 values. Source: outputs/tables/within_eea.csv.", True)
    write(pd.read_csv(T / "within_eea_summary.csv"), "stab_within_eea_summary",
          "Within-EEA totals, placebo bands and robust lists. Source: outputs/tables/within_eea_summary.csv.", True)
    xu = pd.concat([pd.read_csv(T / "xu_gsc.csv").assign(r_grid="0-5 (main)"),
                    pd.read_csv(T / "xu_gsc_r8.csv").assign(r_grid="0-8 (sensitivity)")], ignore_index=True)
    write(xu, "stab_xu", "Xu (2017) generalized synthetic control (RS-D20) for the R0 robust economies, r chosen by "
          "cross-validation from 0..5 (main) and 0..8 (sensitivity). Sources: outputs/tables/xu_gsc.csv, xu_gsc_r8.csv.",
          True)
    cv = pd.concat([pd.read_csv(K / "xu_gsc_cv.csv").assign(r_grid="0-5"),
                    pd.read_csv(K / "xu_gsc_cv_r8.csv").assign(r_grid="0-8")], ignore_index=True)
    write(cv, "stab_xu_cv", "Cross-validation mean squared prediction error by r. Sources: outputs/checks/xu_gsc_cv.csv, "
          "xu_gsc_cv_r8.csv.", True)
    write(pd.read_csv(T / "false_positive_calibration.csv"), "stab_false_positive",
          "False-positive calibration of the robust rule (RS-D23): for each principle and placebo date p, the "
          "non-control economies that pass the RS-D16 rule when the S1 and S2 placebo % at p are treated as the main "
          "result and the other four dates (S1, S2; 8 runs) as placebos; summary rows give the mean and maximum count, "
          "the actual R0 robust count and the number of dates whose count is >= the actual count. The actual rule uses "
          "a 23-month window and 10 placebo runs, the pseudo version windows of at most 12 months and 8 runs. Source: "
          "outputs/tables/false_positive_calibration.csv.", True)
    write(pd.read_csv(T / "rsd2_dose_check.csv"), "stab_dose_check",
          "RS-D2 dose check by ship-type category. Source: outputs/tables/rsd2_dose_check.csv.", True)
    flags = pd.read_csv(K / "anomaly_flags.csv")
    mon = pd.read_csv(K / "anomaly_months.csv")
    rows = []
    for (p, w), g in flags.groupby(["principle", "window"], sort=False):
        sw = mon[(mon["principle"] == p) & (mon["window"] == w) & mon["system_wide"]]["period"].tolist()
        rows.append({"principle": p, "window": w, "flagged_economy_months": len(g),
                     "economies_with_a_flag": g["iso3"].nunique(), "system_wide_months": ", ".join(sw) or "none",
                     "isolated_flags": int((~g["period"].isin(sw)).sum()),
                     "isolated_flags_larger_half": int((~g["period"].isin(sw) & g["larger_half"]).sum())})
    write(pd.DataFrame(rows), "stab_anomaly_flags_summary",
          "RS-D14 anomaly scan: flags per principle and window. Sources: outputs/checks/anomaly_flags.csv, "
          "anomaly_months.csv.", True)


def write_notes():
    lines = ["# Table notes", "", "One line per table: source and definitions. Excess is in Mt CO2 over 2023-12..2025-10 "
             "unless stated; % is excess as a share of the counterfactual.", ""]
    for supp in (False, True):
        lines += ["## " + ("Supplementary tables" if supp else "Main tables"), ""]
        lines += [f"- `{name}.csv` ({n} rows): {note}" for s, name, n, note in NOTES if s == supp]
        lines.append("")
    (OUT / "table_notes.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{rel(OUT / 'table_notes.md')} written")


def main():
    t0 = time.perf_counter()
    tab_data_panels()
    tab_system()
    tab_robust_economies()
    tab_rq3()
    supplementary()
    write_notes()
    print(f"Run time {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
