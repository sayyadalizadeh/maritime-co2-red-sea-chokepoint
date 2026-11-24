"""Further robustness variants (RS-D33).

1. R15 (economies, both principles) and W5 (world, main run and B1): the main estimates re-summed
   over 2024-01..2025-10 (December 2023 left out). The R0 / W0 fits are recomputed with the same
   data and specification (no new estimation choice; the totals are checked against
   rsd4_summary.csv and rsd2_summary.csv) and re-summed. Robust flags are recomputed against the
   existing placebo maxima (max_abs_placebo of the units files; for totals, the maximum
   |aggregate placebo %| of the main run).
2. R16: stricter control pools, re-estimated with S1 and S2, the Panama term, the RS-D16 placebos
   and robust rule (common.run_variant).
   - Departure: the RS-D4 pool restricted to economies with m_v at or below the tercile cut-off
     of m_v over the departure panel with exposure data.
   - Residence: the RS-D4 pool restricted to economies with both x_v and m_v at or below their
     tercile cut-offs over the residence panel with exposure data.
   Economies leaving the pool become treated units; the panels are unchanged.
3. RQ3 leave-one-out: for each principle, weighted S1 and S2 (15_rq3_associations.wls_hc3, R0
   sample), each RSL economy of the RQ3 sample dropped in turn; RSL coefficient, HC3 SE and 95%
   interval. RQ3 is descriptive.
4. PPML at system level: Poisson pseudo-maximum likelihood (design.ppml, iteratively reweighted
   least squares) on per-day values, unweighted, with type x calendar-month and month effects (S1)
   and type trends (S2), on untreated observations; counterfactual = exp(fitted), no smearing;
   RS-D16 placebos and rule. Runs: main (transit types treated) and B1 (CONTAINER treated).
   Check: on a noise-free simulated panel with no effect the PPML excess is zero; over 50 noisy
   simulated panels with no effect (fixed seeds) the mean excess % lies within +-1% of zero.
5. Container monthly path from existing outputs (outputs/figures/fig_world_container_data.csv:
   observed, S1 and S2 per-day values of the RS-D2 main run): monthly excess (Mt, %) S1 and S2,
   2023-12..2025-10, and means for 2023-12..2024-07 and 2024-08..2025-10. No figure: the monthly
   S1 % is already drawn in sfig_container_event, so a separate figure would duplicate it.
6. Checks of the two additions to existing tables: the S2 yearly container rows of tab_system.csv and the
   container placebo column of stab_robustness_world.csv.

Outputs
- outputs/tables/revision_variants_economies.csv, revision_variants_units.csv,
  revision_variants_world.csv, rq3_leave_one_out.csv, ppml_world.csv, ppml_world_types.csv,
  ppml_simulation.csv, container_monthly.csv
- outputs/checks/revision_checks.csv (rows starting with 'variants_' and 'section8_')
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
import design as D
from common import rel, run_variant, update_checks

imp = importlib.import_module("09_imputation")
m10 = importlib.import_module("10_rsd4_economies")
m11 = importlib.import_module("11_rsd2_world")
m12 = importlib.import_module("12_robustness_economies")
m15 = importlib.import_module("15_rq3_associations")

TABLES = C.OUTPUTS / "tables"
MT = 1e6
CHECKS_FILE = C.CHECKS / "revision_checks.csv"
R15_START = "2024-01"
PERIOD_A = ("2023-12", "2024-07")
PERIOD_B = ("2024-08", "2025-10")
SIM_SEED = 20261123
SIM_REPS = 50
SIM_NOISE = 0.05


def chk(name, definition, expected, obtained, ok):
    return {"check": name, "definition": definition, "expected": str(expected), "obtained": str(obtained),
            "abs_diff": "", "pass": bool(ok)}


def changes(new, old):
    return " ".join(sorted(new - old)), " ".join(sorted(old - new))


# ---------------------------------------------------------------------------
# 1. R15 and W5
# ---------------------------------------------------------------------------
def r15(ex, pt, R, checks, econ_rows, unit_rows):
    summ = pd.read_csv(TABLES / "rsd4_summary.csv").set_index(["principle", "spec"])
    pl = pd.read_csv(TABLES / "rsd4_placebo_aggregate.csv")
    for principle, cfg in m10.PRINCIPLES.items():
        df = m12.make_df(principle, ex, pt, R)
        res = run_variant(df, drop=tuple(cfg["drop"]), last_pre=cfg["last_pre"], panama=True, placebos=False)
        u = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv").set_index("iso3")
        nc = u[~u["control"].astype(bool)]
        r0 = set(nc.index[nc["robust"].astype(bool)])
        g = {}
        for spec in imp.SPECS:
            tr = res["main"][spec]
            ref = summ.loc[(principle, spec), "excess_Mt"]
            checks.append(chk(f"variants_R15_{principle}_{spec}_R0", f"R15 {principle} {spec}: recomputed R0 total "
                              "equals rsd4_summary.csv (Mt, |diff| <= 1e-6)", f"{ref:.6f}",
                              f"{tr['excess_t'].sum() / MT:.6f}", abs(tr["excess_t"].sum() / MT - ref) <= 1e-6))
            t = tr[tr["period"] >= R15_START]
            g[spec] = t.groupby("unit")[["excess_t", "cf_t"]].sum()
            g[spec]["pct"] = 100 * g[spec]["excess_t"] / g[spec]["cf_t"]
        rob = imp.robust(g["S1"]["pct"], g["S2"]["pct"], nc["max_abs_placebo"].reindex(g["S1"].index))
        rset = set(rob.index[rob])
        gained, lost = changes(rset, r0)
        a = pl[pl["principle"] == principle]["pct"]
        for spec in imp.SPECS:
            gg = g[spec]
            cf = gg["cf_t"].sum()
            e = g["S1"]["excess_t"]
            econ_rows.append({"variant": "R15", "principle": principle, "spec": spec,
                              "description": "R0 excess re-summed over 2024-01..2025-10",
                              "n_economies": len(u), "n_control": int(u["control"].sum()),
                              "excess_Mt": gg["excess_t"].sum() / MT, "cf_Mt": cf / MT,
                              "pct": 100 * gg["excess_t"].sum() / cf,
                              "placebo_band_pct_min": a.min(), "placebo_band_pct_max": a.max(),
                              "placebo_band_Mt_min": a.min() * cf / 100 / MT, "placebo_band_Mt_max": a.max() * cf / 100 / MT,
                              "gross_gains_S1_Mt": e[e > 0].sum() / MT, "gross_losses_S1_Mt": e[e < 0].sum() / MT,
                              "n_robust": len(rset), "robust_list": " ".join(sorted(rset)),
                              "robust_list_R0": " ".join(sorted(r0)), "gained_vs_R0": gained, "lost_vs_R0": lost,
                              "pool_size": int(u["control"].sum()), "pool": "", "pool_left_vs_R0": ""})
        for iso in g["S1"].index:
            unit_rows.append({"variant": "R15", "principle": principle, "iso3": iso,
                              "excess_Mt_S1": g["S1"].loc[iso, "excess_t"] / MT, "pct_S1": g["S1"].loc[iso, "pct"],
                              "excess_Mt_S2": g["S2"].loc[iso, "excess_t"] / MT, "pct_S2": g["S2"].loc[iso, "pct"],
                              "max_abs_placebo": nc.loc[iso, "max_abs_placebo"], "robust": bool(rob[iso]),
                              "robust_R0": iso in r0})
        print(f"R15 {principle}: S1 {econ_rows[-2]['excess_Mt']:+.2f} Mt, S2 {econ_rows[-1]['excess_Mt']:+.2f} Mt; "
              f"robust {len(rset)} (gained {gained or '-'}; lost {lost or '-'})")


def w5(checks, world_rows):
    summ = pd.read_csv(TABLES / "rsd2_summary.csv").set_index(["run", "spec"])
    w = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w[(w["period"] >= C.PRE_START) & (w["period"] <= C.MAIN_END)]
    base = w[w["vessel"].isin(m11.TRANSIT + m11.NON_TRANSIT)].rename(columns={"vessel": "unit"})
    for run, treated, f in (("main", set(m11.TRANSIT), "rsd2_types.csv"), ("B1", {"CONTAINER"}, "rsd2_types_B1.csv")):
        df = base.copy()
        df["control"] = ~df["unit"].isin(treated)
        res = run_variant(df, last_pre=m11.LAST_PRE, placebos=False)
        t = pd.read_csv(TABLES / f).set_index("vessel")
        g, tot = {}, {}
        for spec in imp.SPECS:
            tr = res["main"][spec]
            ref = summ.loc[(run, spec), "excess_Mt"]
            checks.append(chk(f"variants_W5_{run}_{spec}_W0", f"W5 {run} {spec}: recomputed W0 total equals "
                              "rsd2_summary.csv (Mt, |diff| <= 1e-6)", f"{ref:.6f}", f"{tr['excess_t'].sum() / MT:.6f}",
                              abs(tr["excess_t"].sum() / MT - ref) <= 1e-6))
            tt = tr[tr["period"] >= R15_START]
            g[spec] = tt.groupby("unit")[["excess_t", "cf_t"]].sum()
            g[spec]["pct"] = 100 * g[spec]["excess_t"] / g[spec]["cf_t"]
            tot[spec] = (tt["excess_t"].sum(), tt["cf_t"].sum())
        rob = imp.robust(g["S1"]["pct"], g["S2"]["pct"], t["max_abs_placebo"].reindex(g["S1"].index))
        mx = summ.loc[(run, "S1"), "max_abs_placebo_pct"]
        p1, p2 = 100 * tot["S1"][0] / tot["S1"][1], 100 * tot["S2"][0] / tot["S2"][1]
        total_rob = bool(imp.robust(p1, p2, mx))
        r0 = set(t.index[t["robust"].astype(bool)])
        rset = set(rob.index[rob])
        gained, lost = changes(rset, r0)
        for spec in imp.SPECS:
            e, cf = tot[spec]
            world_rows.append({"variant": "W5", "run": run, "spec": spec, "unit": "TOTAL (treated types)",
                               "excess_Mt": e / MT, "cf_Mt": cf / MT, "pct": 100 * e / cf,
                               "max_abs_placebo_pct": mx, "robust": total_rob,
                               "robust_W0": bool(summ.loc[(run, spec), "total_robust"]),
                               "robust_types": " ".join(sorted(rset)), "robust_types_W0": " ".join(sorted(r0)),
                               "gained_vs_W0": gained, "lost_vs_W0": lost})
        for v in sorted(g["S1"].index):
            for spec in imp.SPECS:
                world_rows.append({"variant": "W5", "run": run, "spec": spec, "unit": v,
                                   "excess_Mt": g[spec].loc[v, "excess_t"] / MT, "cf_Mt": g[spec].loc[v, "cf_t"] / MT,
                                   "pct": g[spec].loc[v, "pct"], "max_abs_placebo_pct": t.loc[v, "max_abs_placebo"],
                                   "robust": bool(rob[v]), "robust_W0": bool(t.loc[v, "robust"])})
        c = [r for r in world_rows if r["run"] == run and r["unit"] == "CONTAINER"]
        print(f"W5 {run}: total S1 {p1:+.2f}%, S2 {p2:+.2f}% (robust {total_rob}); CONTAINER S1 {c[0]['pct']:+.2f}%, "
              f"S2 {c[1]['pct']:+.2f}%, robust {c[0]['robust']}")


# ---------------------------------------------------------------------------
# 2. R16
# ---------------------------------------------------------------------------
def r16(ex, pt, R, checks, econ_rows, unit_rows):
    e = ex.set_index("iso3")
    for principle, cfg in m10.PRINCIPLES.items():
        panel = e[e["in_res_panel" if principle == "residence" else "in_dep_panel"] & e[cfg["exposure"]].notna()]
        old = e[cfg["control"]].astype(bool)
        cut_m = panel["m_v"].quantile(1 / 3)
        keep = panel["m_v"] <= cut_m
        cuts = f"m_v cut-off {cut_m:.6f}"
        if principle == "residence":
            cut_x = panel["x_v"].quantile(1 / 3)
            keep &= panel["x_v"] <= cut_x
            cuts = f"x_v cut-off {cut_x:.6f}; " + cuts
        new = old & keep.reindex(old.index, fill_value=False).astype(bool)
        new_set, old_set = set(new.index[new]), set(old.index[old])
        df = m12.make_df(principle, ex, pt, R, control=new)
        res = run_variant(df, drop=tuple(cfg["drop"]), last_pre=cfg["last_pre"], panama=True)
        uu, agg = res["units"], res["placebo"]
        rob = set(uu.index[uu["robust"]])
        u0 = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv")
        r0 = set(u0.loc[u0["robust"].astype(bool), "iso3"])
        gained, lost = changes(rob, r0)
        checks.append(chk(f"variants_R16_{principle}_pool", f"R16 {principle}: stricter pool is a subset of the RS-D4 "
                          f"pool ({cuts})", "subset", f"{len(new_set)} of {len(old_set)}", new_set <= old_set))
        checks.append(chk(f"variants_R16_{principle}_placebo_runs", f"R16 {principle}: placebo runs", 10, len(agg),
                          len(agg) == 10))
        for spec in imp.SPECS:
            tr = res["main"][spec]
            tot, cf = tr["excess_t"].sum(), tr["cf_t"].sum()
            ex1 = uu["excess_t_S1"]
            econ_rows.append({"variant": "R16", "principle": principle, "spec": spec,
                              "description": "stricter control pool (" + cuts + ")",
                              "n_economies": res["diags"][spec]["n_units"],
                              "n_control": res["diags"][spec]["n_control_units"],
                              "excess_Mt": tot / MT, "cf_Mt": cf / MT, "pct": 100 * tot / cf,
                              "placebo_band_pct_min": agg["pct"].min(), "placebo_band_pct_max": agg["pct"].max(),
                              "placebo_band_Mt_min": agg["pct"].min() * cf / 100 / MT,
                              "placebo_band_Mt_max": agg["pct"].max() * cf / 100 / MT,
                              "gross_gains_S1_Mt": ex1[ex1 > 0].sum() / MT, "gross_losses_S1_Mt": ex1[ex1 < 0].sum() / MT,
                              "n_robust": len(rob), "robust_list": " ".join(sorted(rob)),
                              "robust_list_R0": " ".join(sorted(r0)), "gained_vs_R0": gained, "lost_vs_R0": lost,
                              "pool_size": len(new_set), "pool": " ".join(sorted(new_set)),
                              "pool_left_vs_R0": " ".join(sorted(old_set - new_set))})
        for iso in uu.index:
            unit_rows.append({"variant": "R16", "principle": principle, "iso3": iso,
                              "excess_Mt_S1": uu.loc[iso, "excess_t_S1"] / MT, "pct_S1": uu.loc[iso, "pct_S1"],
                              "excess_Mt_S2": uu.loc[iso, "excess_t_S2"] / MT, "pct_S2": uu.loc[iso, "pct_S2"],
                              "max_abs_placebo": uu.loc[iso, "max_abs_placebo"], "robust": bool(uu.loc[iso, "robust"]),
                              "robust_R0": iso in r0})
        print(f"R16 {principle}: pool {len(new_set)} (was {len(old_set)}), S1 {econ_rows[-2]['excess_Mt']:+.2f} Mt, "
              f"S2 {econ_rows[-1]['excess_Mt']:+.2f} Mt, robust {len(rob)} (gained {gained or '-'}; lost {lost or '-'})")


# ---------------------------------------------------------------------------
# 3. RQ3 leave-one-out
# ---------------------------------------------------------------------------
def rq3_loo(ex, checks):
    e = ex.set_index("iso3")
    rows = []
    ref = pd.read_csv(TABLES / "rq3_coefficients.csv")
    for principle in ("departure", "residence"):
        u = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv")
        u = u[~u["control"]].copy()
        u[m15.EXPOSURE[principle]] = u["iso3"].map(e[m15.EXPOSURE[principle]])
        regs = m15.REGRESSORS[principle]
        rsl = sorted(u.loc[u["rsl"], "iso3"])
        for spec in ("S1", "S2"):
            cfcol = "cf_total_t" if spec == "S1" else "cf_total_t_S2"
            for left in [None] + rsl:
                d = u if left is None else u[u["iso3"] != left]
                X = np.column_stack([np.ones(len(d))] + [d[r].astype(float).to_numpy() for r in regs])
                b, se, r2, _ = m15.wls_hc3(d[f"pct_{spec}"].to_numpy(), X, d[cfcol].to_numpy() / MT)
                i = 1 + regs.index("rsl")
                rows.append({"principle": principle, "spec": spec, "left_out": left or "none (full sample)",
                             "n": len(d), "n_rsl": int(d["rsl"].sum()), "rsl_members": " ".join(sorted(d.loc[d["rsl"], "iso3"])),
                             "rsl_coef": b[i], "rsl_se_hc3": se[i], "ci95_lo": b[i] - 1.96 * se[i],
                             "ci95_hi": b[i] + 1.96 * se[i], "r2": r2})
                if left is None:
                    rr = ref[(ref["principle"] == principle) & (ref["spec"] == spec) & (ref["variant"] == "weighted")
                             & (ref["term"] == "rsl")].iloc[0]
                    checks.append(chk(f"variants_rq3_{principle}_{spec}_full", f"RQ3 leave-one-out {principle} {spec}: "
                                      "full-sample RSL coefficient equals rq3_coefficients.csv (|diff| <= 1e-9)",
                                      f"{rr['coef']:.6f}", f"{b[i]:.6f}", abs(b[i] - rr["coef"]) <= 1e-9))
        print(f"RQ3 leave-one-out {principle}: RSL members in the sample {' '.join(rsl)}")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. PPML
# ---------------------------------------------------------------------------
def ppml_impute(df, shock, last, spec):
    d, untreated, treated = D.prepare(df, shock, (), last)
    X, _ = D.fe_design(d, untreated, spec, panama=False)
    beta, it, dev, score = D.ppml(X[untreated], d.loc[untreated, "per_day"].to_numpy())
    tr = d.loc[treated, ["unit", "period", "days", "value_t", "per_day"]].copy()
    tr["cf_per_day"] = np.exp(X[treated] @ beta)
    tr["cf_t"] = tr["cf_per_day"] * tr["days"]
    tr["excess_t"] = (tr["per_day"] - tr["cf_per_day"]) * tr["days"]
    return tr.reset_index(drop=True), {"iterations": it, "deviance": dev, "max_rel_score": score}


def ppml_world(checks):
    w = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w[(w["period"] >= C.PRE_START) & (w["period"] <= C.MAIN_END)]
    base = w[w["vessel"].isin(m11.TRANSIT + m11.NON_TRANSIT)].rename(columns={"vessel": "unit"})
    base = base[["unit", "period", "days", "value_t", "per_day"]].reset_index(drop=True)
    total_rows, type_rows = [], []
    for run, treated in (("main", set(m11.TRANSIT)), ("B1", {"CONTAINER"})):
        df = base.copy()
        df["control"] = ~df["unit"].isin(treated)
        main, diag = {}, {}
        for spec in imp.SPECS:
            main[spec], diag[spec] = ppml_impute(df, C.SHOCK_START, C.MAIN_END, spec)
            checks.append(chk(f"variants_ppml_{run}_{spec}_converged", f"PPML {run} {spec}: IRLS converged (max |score| "
                              "/ sum(y) <= 1e-8)", "<= 1e-8", f"{diag[spec]['max_rel_score']:.3g} after "
                              f"{diag[spec]['iterations']} iterations", diag[spec]["max_rel_score"] <= 1e-8))
        unit_pl, agg = {}, []
        for p in imp.PLACEBO_DATES:
            end = min(imp.add_months(p, 11), m11.LAST_PRE)
            for spec in imp.SPECS:
                tr, dg = ppml_impute(df, p, end, spec)
                if dg["max_rel_score"] > 1e-8:
                    raise RuntimeError(f"PPML placebo {run} {p} {spec} did not converge")
                g = tr.groupby("unit")[["excess_t", "cf_t"]].sum()
                unit_pl[f"placebo_{p}_{spec}"] = 100 * g["excess_t"] / g["cf_t"]
                agg.append({"placebo_date": p, "spec": spec, "pct": 100 * tr["excess_t"].sum() / tr["cf_t"].sum()})
        unit_pl, agg = pd.DataFrame(unit_pl), pd.DataFrame(agg)
        checks.append(chk(f"variants_ppml_{run}_placebo_runs", f"PPML {run}: placebo runs (5 dates x S1, S2)", 10,
                          len(agg), len(agg) == 10))
        g = {s: main[s].groupby("unit")[["excess_t", "cf_t"]].sum() for s in imp.SPECS}
        for v in sorted(g["S1"].index):
            p1 = 100 * g["S1"].loc[v, "excess_t"] / g["S1"].loc[v, "cf_t"]
            p2 = 100 * g["S2"].loc[v, "excess_t"] / g["S2"].loc[v, "cf_t"]
            mx = unit_pl.loc[v].abs().max()
            type_rows.append({"run": run, "vessel": v, "excess_Mt_S1": g["S1"].loc[v, "excess_t"] / MT, "pct_S1": p1,
                              "excess_Mt_S2": g["S2"].loc[v, "excess_t"] / MT, "pct_S2": p2,
                              "cf_Mt_S1": g["S1"].loc[v, "cf_t"] / MT,
                              **{c: unit_pl.loc[v, c] for c in unit_pl.columns},
                              "max_abs_placebo": mx, "robust": bool(imp.robust(p1, p2, mx))})
        tot = {s: (main[s]["excess_t"].sum(), main[s]["cf_t"].sum()) for s in imp.SPECS}
        pct = {s: 100 * tot[s][0] / tot[s][1] for s in imp.SPECS}
        mxa = agg["pct"].abs().max()
        for spec in imp.SPECS:
            total_rows.append({"run": run, "spec": spec, "treated_types": " ".join(sorted(treated)),
                               "excess_Mt": tot[spec][0] / MT, "cf_Mt": tot[spec][1] / MT, "pct": pct[spec],
                               "placebo_band_pct_min": agg["pct"].min(), "placebo_band_pct_max": agg["pct"].max(),
                               "max_abs_placebo_pct": mxa,
                               "total_robust": bool(imp.robust(pct["S1"], pct["S2"], mxa)),
                               "container_excess_Mt": g[spec].loc["CONTAINER", "excess_t"] / MT,
                               "container_pct": 100 * g[spec].loc["CONTAINER", "excess_t"] / g[spec].loc["CONTAINER", "cf_t"],
                               "container_robust": [r for r in type_rows if r["run"] == run
                                                    and r["vessel"] == "CONTAINER"][0]["robust"],
                               "iterations": diag[spec]["iterations"], "max_rel_score": diag[spec]["max_rel_score"]})
        print(f"PPML {run}: S1 {pct['S1']:+.2f}%, S2 {pct['S2']:+.2f}%, max |placebo| {mxa:.2f}%; CONTAINER S1 "
              f"{total_rows[-2]['container_pct']:+.2f}%, S2 {total_rows[-1]['container_pct']:+.2f}%, "
              f"robust {total_rows[-1]['container_robust']}")
    return pd.DataFrame(total_rows), pd.DataFrame(type_rows)


def simulate(seed, s=SIM_NOISE):
    """A world-like panel with no effect: 18 units, 2019-01..2025-10, 10 treated from 2023-12.

    log level = unit x calendar-month effect + common month effect (random walk) + noise; the
    multiplicative noise exp(e), e ~ N(-s^2/2, s^2), has mean one, so the conditional mean has no
    treatment effect. With s = 0 the panel follows the S1 model exactly.
    """
    rng = np.random.default_rng(seed)
    per = pd.period_range(C.PRE_START, C.MAIN_END, freq="M")
    units = [f"U{i:02d}" for i in range(18)]
    level = rng.uniform(np.log(2e3), np.log(6e5), size=len(units))
    season = rng.normal(0, 0.05, size=(len(units), 12))
    b = np.cumsum(rng.normal(0, 0.02, size=len(per)))
    rows = []
    for i, u in enumerate(units):
        e = rng.normal(-s ** 2 / 2, s, size=len(per)) if s > 0 else np.zeros(len(per))
        mu = np.exp(level[i] + season[i, per.month - 1] + b + e)
        for p, v in zip(per, mu):
            rows.append({"unit": u, "period": p.strftime("%Y-%m"), "days": p.days_in_month, "per_day": v})
    df = pd.DataFrame(rows)
    df["value_t"] = df["per_day"] * df["days"]
    df["control"] = ~df["unit"].isin(units[:10])
    return df


def ppml_simulation(checks):
    """(a) one noise-free panel with no effect: the excess must be zero (implementation check);
    (b) SIM_REPS panels with noise: the mean excess % over panels must lie within +-1% (bias check).
    The spread of single noisy panels depends on the chosen noise level and is reported, not tested."""
    rows = []
    for k, s in [(0, 0.0)] + [(k, SIM_NOISE) for k in range(SIM_REPS)]:
        df = simulate(SIM_SEED + k, s)
        for spec in imp.SPECS:
            tr, dg = ppml_impute(df, C.SHOCK_START, C.MAIN_END, spec)
            rows.append({"panel": "noise-free" if s == 0 else "noisy", "replication": k, "seed": SIM_SEED + k,
                         "noise_sd": s, "spec": spec, "pct": 100 * tr["excess_t"].sum() / tr["cf_t"].sum(),
                         "iterations": dg["iterations"]})
    sim = pd.DataFrame(rows)
    nf = sim[sim["panel"] == "noise-free"]
    checks.append(chk("variants_ppml_simulation_noise_free", f"PPML on a noise-free simulated panel with no effect "
                      f"(seed {SIM_SEED}): total excess of treated units, % (S1; S2), |pct| <= 1e-6", "0",
                      "; ".join(f"{v:.2e}" for v in nf["pct"]), bool((nf["pct"].abs() <= 1e-6).all())))
    ns = sim[sim["panel"] == "noisy"]
    for spec in imp.SPECS:
        v = ns[ns["spec"] == spec]["pct"]
        checks.append(chk(f"variants_ppml_simulation_mean_{spec}", f"PPML {spec}, {SIM_REPS} noisy simulated panels "
                          f"with no effect (noise sd {SIM_NOISE}): mean total excess % within +-1 (single panels: "
                          f"{int((v.abs() > 1).sum())} of {len(v)} outside +-1%, max |pct| {v.abs().max():.3f}, "
                          f"sd {v.std():.3f})", "|mean| <= 1", f"{v.mean():.4f}", abs(v.mean()) <= 1))
        print(f"PPML simulation {spec}: noise-free {nf[nf['spec'] == spec]['pct'].iloc[0]:.2e}%; noisy mean "
              f"{v.mean():+.4f}%, sd {v.std():.4f}, max |pct| {v.abs().max():.4f}%, {int((v.abs() > 1).sum())} of "
              f"{len(v)} outside +-1%")
    return sim


# ---------------------------------------------------------------------------
# 5. Container monthly path
# ---------------------------------------------------------------------------
def container_monthly(checks):
    d = pd.read_csv(C.OUTPUTS / "figures" / "fig_world_container_data.csv")
    d = d[d["period"] >= C.SHOCK_START].copy()
    t = pd.read_csv(TABLES / "rsd2_types.csv").set_index("vessel").loc["CONTAINER"]
    out = pd.DataFrame({"row": "month", "period": d["period"]})
    for spec, col in (("S1", "s1_kt_per_day"), ("S2", "s2_kt_per_day")):
        out[f"excess_Mt_{spec}"] = ((d["observed_kt_per_day"] - d[col]) * d["days"] / 1e3).to_numpy()
        out[f"cf_Mt_{spec}"] = (d[col] * d["days"] / 1e3).to_numpy()
        out[f"pct_{spec}"] = 100 * out[f"excess_Mt_{spec}"] / out[f"cf_Mt_{spec}"]
        diff = abs(out[f"excess_Mt_{spec}"].sum() - t[f"excess_total_t_{spec}"] / MT)
        checks.append(chk(f"variants_container_monthly_{spec}", f"container monthly path {spec}: sum over 2023-12.."
                          "2025-10 equals rsd2_types.csv CONTAINER excess (Mt, |diff| <= 1e-6)",
                          f"{t[f'excess_total_t_{spec}'] / MT:.6f}", f"{out[f'excess_Mt_{spec}'].sum():.6f}", diff <= 1e-6))
    checks.append(chk("variants_container_monthly_n", "container monthly path: months 2023-12..2025-10", 23, len(out),
                      len(out) == 23))
    summ = []
    for label, (a, b) in (("mean 2023-12..2024-07", PERIOD_A), ("mean 2024-08..2025-10", PERIOD_B),
                          ("window 2023-12..2025-10", (C.SHOCK_START, C.MAIN_END))):
        s = out[(out["period"] >= a) & (out["period"] <= b)]
        r = {"row": label, "period": f"{a}..{b}", "n_months": len(s)}
        for spec in imp.SPECS:
            r[f"excess_Mt_{spec}"] = s[f"excess_Mt_{spec}"].mean()
            r[f"cf_Mt_{spec}"] = s[f"cf_Mt_{spec}"].mean()
            r[f"pct_{spec}"] = s[f"pct_{spec}"].mean()
            r[f"period_pct_{spec}"] = 100 * s[f"excess_Mt_{spec}"].sum() / s[f"cf_Mt_{spec}"].sum()
            r[f"period_total_Mt_{spec}"] = s[f"excess_Mt_{spec}"].sum()
        summ.append(r)
    out["n_months"] = 1
    return pd.concat([out, pd.DataFrame(summ)], ignore_index=True)


# ---------------------------------------------------------------------------
# 6. Checks of the section 8 additions
# ---------------------------------------------------------------------------
def section8_checks():
    rows = []
    ts = pd.read_csv(C.OUTPUTS / "manuscript_tables" / "tab_system.csv")
    for run in ("main", "B1"):
        r = ts[(ts["run"] == run) & (ts["spec"] == "S2") & (ts["scope"] == "CONTAINER")].iloc[0]
        ys = r["excess_2023_Mt"] + r["excess_2024_Mt"] + r["excess_2025_Mt"]
        rows.append(chk(f"section8_tab_system_{run}_S2_years", f"tab_system.csv {run} S2 CONTAINER: yearly sums "
                        "(2023, 2024, 2025; rounded to 3 decimals) add up to the window total within rounding (0.002 Mt)",
                        f"{r['excess_Mt']:.3f}", f"{ys:.3f}", abs(ys - r["excess_Mt"]) <= 0.002))
    rw = pd.read_csv(C.OUTPUTS / "manuscript_tables" / "supplementary" / "stab_robustness_world.csv")
    v = rw[(rw["variant"] == "W1") & (rw["run"] == "main")]["container_max_abs_placebo_pct"].iloc[0]
    rows.append(chk("section8_W1_container_placebo", "stab_robustness_world.csv W1 main: container max |placebo %| "
                    "rounded to one decimal equals the 10.1% quoted in the manuscript", "10.1", f"{v:.1f}",
                    f"{v:.1f}" == "10.1"))
    rt = pd.read_csv(TABLES / "rsd2_types.csv").set_index("vessel")
    v0 = rw[(rw["variant"] == "W0") & (rw["run"] == "main")]["container_max_abs_placebo_pct"].iloc[0]
    rows.append(chk("section8_W0_container_placebo", "stab_robustness_world.csv W0 main: container max |placebo %| "
                    "equals rsd2_types.csv CONTAINER max_abs_placebo", f"{rt.loc['CONTAINER', 'max_abs_placebo']:.6f}",
                    f"{v0:.6f}", abs(v0 - rt.loc["CONTAINER", "max_abs_placebo"]) <= 1e-9))
    return rows


def main():
    t_all = time.perf_counter()
    checks = []
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    R = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")["R"]

    econ_rows, unit_rows, world_rows = [], [], []
    r15(ex, pt, R, checks, econ_rows, unit_rows)
    w5(checks, world_rows)
    r16(ex, pt, R, checks, econ_rows, unit_rows)
    pd.DataFrame(econ_rows).to_csv(TABLES / "revision_variants_economies.csv", index=False)
    pd.DataFrame(unit_rows).to_csv(TABLES / "revision_variants_units.csv", index=False)
    pd.DataFrame(world_rows).to_csv(TABLES / "revision_variants_world.csv", index=False)

    rq3_loo(ex, checks).to_csv(TABLES / "rq3_leave_one_out.csv", index=False)

    t0 = time.perf_counter()
    tot, types = ppml_world(checks)
    tot.to_csv(TABLES / "ppml_world.csv", index=False)
    types.to_csv(TABLES / "ppml_world_types.csv", index=False)
    ppml_simulation(checks).to_csv(TABLES / "ppml_simulation.csv", index=False)
    print(f"PPML: {time.perf_counter() - t0:.1f} s")

    container_monthly(checks).to_csv(TABLES / "container_monthly.csv", index=False)
    for f in ("revision_variants_economies.csv", "revision_variants_units.csv", "revision_variants_world.csv",
              "rq3_leave_one_out.csv", "ppml_world.csv", "ppml_world_types.csv", "ppml_simulation.csv",
              "container_monthly.csv"):
        print(f"{rel(TABLES / f)} written")
    update_checks(checks, CHECKS_FILE, "variants_")
    update_checks(section8_checks(), CHECKS_FILE, "section8_")
    print(f"Run time {time.perf_counter() - t_all:.1f} s")


if __name__ == "__main__":
    main()
