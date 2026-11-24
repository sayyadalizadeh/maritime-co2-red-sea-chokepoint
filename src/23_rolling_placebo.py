"""Equal-length placebo inference (RS-D31) and gross gains and losses against placebos (RS-D32).

Rolling placebo dates p, each run with the same 23-month treated window as the main estimate:
data up to p + 22 months, treated = non-control units from p, S1 and S2, the main control pools,
the RS-D15 estimator (09_imputation.fit_impute) with the Panama term for economies.
- RES_TOTAL (residence): p = 2021-01..2022-01 (13 dates); data end at most 2023-11.
- TER_INT (departure): p = 2021-01..2021-12 (12 dates); data end at most 2023-10, 2023-11 excluded.
- RES_INT (21_like_for_like.py): its RS-D14 scan excludes 2023-11, so its last usable pre-crisis
  month is 2023-10 and p + 22 <= 2023-10 holds for p = 2021-01..2021-12 (12 dates).
- World by ship type, main run (transit types treated) and B1 (CONTAINER treated):
  p = 2021-01..2022-01 (13 dates).

RS-D31 (supplementary inference; the RS-D16 rule stays the main rule)
1. Equal-length rule: max |placebo %| over all rolling runs (dates x S1, S2); robust when the
   main S1 and S2 % have the same sign and min(|S1 %|, |S2 %|) exceeds it. Applied to economies,
   ship types and totals.
2. Unit p-values (economies, per series and specification s):
   sigma_u = root mean square of the unit's rolling placebo %; z_u = main % / sigma_u;
   null draws: placebo % at date p / sigma_u computed without date p, pooled over all non-control
   units and dates; p_u,s = (1 + number of null |z| >= |z_u|) / (1 + number of null draws);
   p_u = max(p_u,S1, p_u,S2); S1 and S2 must agree in sign.
3. Benjamini-Hochberg at q = 0.10 over the non-control units of each series. A unit whose S1 and
   S2 signs differ enters with p = 1. The list is reported as candidates with q x its size as the
   expected number of false discoveries.

RS-D32: for each rolling date, S1, and each economy series: positive and negative placebo excess
summed over non-control units, as % of the summed placebo counterfactual; compared with the actual
S1 gross gains and losses as % of the summed S1 counterfactual of the non-control units.

Outputs
- outputs/tables/rolling_placebo_runs.csv, rolling_placebo_units.csv, rolling_placebo_system.csv,
  rolling_placebo_bh.csv, rolling_placebo_gross.csv
- outputs/checks/revision_checks.csv (rows starting with 'rolling_')
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import months, rel, update_checks

imp = importlib.import_module("09_imputation")
m10 = importlib.import_module("10_rsd4_economies")
m11 = importlib.import_module("11_rsd2_world")

TABLES = C.OUTPUTS / "tables"
CHECKS_FILE = C.CHECKS / "revision_checks.csv"
MT = 1e6
Q = 0.10
WINDOW_EXTRA = 22
FIRST_DATE, LAST_DATE = "2021-01", "2022-01"


def dates_for(last_usable):
    return [p for p in months(FIRST_DATE, LAST_DATE) if imp.add_months(p, WINDOW_EXTRA) <= last_usable]


def economy_setups():
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    R = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")["R"]
    lp = pd.read_csv(C.INTERIM / "like_for_like_panel.csv.gz")
    lr = pd.read_csv(C.INTERIM / "like_for_like_runs.csv", keep_default_na=False).set_index("series")
    ri = lp[lp["series"] == "RES_INT"].drop(columns="series").reset_index(drop=True)
    ri["control"] = ri["control"].astype(bool)
    lfl_u = pd.read_csv(TABLES / "like_for_like_units.csv")
    return {
        "RES_TOTAL": dict(df=m10.build_df(m10.PRINCIPLES["residence"], ex, pt, R), drop=(), last="2023-11",
                          units=pd.read_csv(TABLES / "rsd4_residence_units.csv")),
        "TER_INT": dict(df=m10.build_df(m10.PRINCIPLES["departure"], ex, pt, R), drop=("2023-11",), last="2023-10",
                        units=pd.read_csv(TABLES / "rsd4_departure_units.csv")),
        "RES_INT": dict(df=ri, drop=tuple(lr.loc["RES_INT", "drop"].split()), last=lr.loc["RES_INT", "last_pre"],
                        units=lfl_u[lfl_u["series"] == "RES_INT"].drop(columns="series")),
    }


def world_setups():
    w = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w[(w["period"] >= C.PRE_START) & (w["period"] <= C.MAIN_END)]
    base = w[w["vessel"].isin(m11.TRANSIT + m11.NON_TRANSIT)].rename(columns={"vessel": "unit"})
    base = base[["unit", "period", "days", "value_t", "per_day"]].reset_index(drop=True)
    out = {}
    for run, treated, f in (("main", set(m11.TRANSIT), "rsd2_types.csv"), ("B1", {"CONTAINER"}, "rsd2_types_B1.csv")):
        df = base.copy()
        df["control"] = ~df["unit"].isin(treated)
        out[run] = dict(df=df, drop=(), last=m11.LAST_PRE, units=pd.read_csv(TABLES / f))
    return out


def rolling_runs(name, s, panama):
    """All rolling runs of one analysis: unit rows and aggregate rows."""
    rows = []
    dates = dates_for(s["last"])
    for p in dates:
        end = min(imp.add_months(p, WINDOW_EXTRA), s["last"])
        for spec in imp.SPECS:
            tr, _, _ = imp.fit_impute(s["df"], shock=p, drop=s["drop"], last=end, spec=spec, panama=panama)
            if not np.isfinite(tr["excess_t"]).all():
                raise RuntimeError(f"{name}: non-finite excess in rolling run {p} {spec}")
            n_months = tr["period"].nunique()
            g = tr.groupby("unit")[["excess_t", "cf_t"]].sum()
            for u, r in g.iterrows():
                rows.append({"analysis": name, "placebo_date": p, "spec": spec, "last_period": end,
                             "n_treated_months": n_months, "level": "unit", "unit": u, "excess_t": r["excess_t"],
                             "cf_t": r["cf_t"], "pct": 100 * r["excess_t"] / r["cf_t"]})
            rows.append({"analysis": name, "placebo_date": p, "spec": spec, "last_period": end,
                         "n_treated_months": n_months, "level": "aggregate", "unit": "TOTAL",
                         "excess_t": tr["excess_t"].sum(), "cf_t": tr["cf_t"].sum(),
                         "pct": 100 * tr["excess_t"].sum() / tr["cf_t"].sum()})
    return pd.DataFrame(rows), dates


def unit_pvalues(P_main, P):
    """RS-D31 p-values for one specification.

    P_main: Series of main % by unit; P: DataFrame units x dates of placebo %.
    Returns DataFrame (sigma, z, p) and the number of null draws.
    """
    A = P.to_numpy(dtype=float)
    n_u, n_d = A.shape
    sigma = np.sqrt(np.mean(A ** 2, axis=1))
    z = P_main.reindex(P.index).to_numpy(dtype=float) / sigma
    sq = A ** 2
    loo = np.sqrt((sq.sum(axis=1, keepdims=True) - sq) / (n_d - 1))
    null = np.abs(A / loo).ravel()
    null.sort()
    n_null = len(null)
    ge = n_null - np.searchsorted(null, np.abs(z), side="left")
    p = (1 + ge) / (1 + n_null)
    return pd.DataFrame({"sigma": sigma, "z": z, "p": p}, index=P.index), n_null


def bh_stepup(p, q):
    """Benjamini-Hochberg: the largest k with p_(k) <= k q / m; returns a boolean array."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    ok = p[order] <= q * np.arange(1, m + 1) / m
    k = int(np.max(np.nonzero(ok)[0]) + 1) if ok.any() else 0
    sel = np.zeros(m, dtype=bool)
    sel[order[:k]] = True
    return sel


def bh_adjusted(p, q):
    """Second computation: BH-adjusted p-values (running minimum from the top) <= q."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    order = np.argsort(p, kind="mergesort")
    scaled = p[order] * m / np.arange(1, m + 1)
    adj_sorted = np.minimum(np.minimum.accumulate(scaled[::-1])[::-1], 1.0)
    adj = np.empty(m)
    adj[order] = adj_sorted
    return adj <= q, adj


def main():
    t_all = time.perf_counter()
    checks, run_frames = [], []
    unit_rows, sys_rows, bh_rows, gross_rows = [], [], [], []

    # ---- economies ---------------------------------------------------------------
    for name, s in economy_setups().items():
        t0 = time.perf_counter()
        runs, dates = rolling_runs(name, s, panama=True)
        run_frames.append(runs)
        n_runs = runs.groupby(["placebo_date", "spec"]).ngroups
        checks.append({"check": f"rolling_{name}_runs", "definition": f"{name}: rolling runs = dates x S1, S2 "
                       f"({dates[0]}..{dates[-1]})", "expected": str(2 * len(dates)), "obtained": str(n_runs),
                       "abs_diff": "", "pass": n_runs == 2 * len(dates)})
        nm = runs["n_treated_months"].unique()
        checks.append({"check": f"rolling_{name}_window_length", "definition": f"{name}: treated months in every "
                       "rolling run", "expected": "23", "obtained": " ".join(map(str, sorted(nm))), "abs_diff": "",
                       "pass": list(nm) == [23]})
        u = s["units"].set_index("iso3")
        nc = u[~u["control"].astype(bool)].copy()
        ur = runs[runs["level"] == "unit"]
        P = {spec: ur[ur["spec"] == spec].pivot(index="unit", columns="placebo_date", values="pct").reindex(nc.index)
             for spec in imp.SPECS}
        n_missing = int(sum(P[sp].isna().sum().sum() for sp in imp.SPECS))
        checks.append({"check": f"rolling_{name}_complete", "definition": f"{name}: missing unit placebo % (non-control "
                       "units x runs)", "expected": "0", "obtained": str(n_missing), "abs_diff": "",
                       "pass": n_missing == 0})
        allP = pd.concat([P["S1"], P["S2"]], axis=1)
        nc["max_abs_rolling"] = allP.abs().max(axis=1)
        nc["robust_equal_length"] = imp.robust(nc["pct_S1"], nc["pct_S2"], nc["max_abs_rolling"])
        pv, nnull = {}, {}
        for spec in imp.SPECS:
            pv[spec], nnull[spec] = unit_pvalues(nc[f"pct_{spec}"], P[spec])
        nc["sign_agree"] = np.sign(nc["pct_S1"]) == np.sign(nc["pct_S2"])
        p_u = np.maximum(pv["S1"]["p"], pv["S2"]["p"])
        p_bh = np.where(nc["sign_agree"], p_u, 1.0)
        sel = bh_stepup(p_bh, Q)
        sel2, adj = bh_adjusted(p_bh, Q)
        checks.append({"check": f"rolling_{name}_bh_reproduced", "definition": f"{name}: BH step-up list equals the "
                       "list from BH-adjusted p-values (second computation)", "expected": "identical",
                       "obtained": f"{int(sel.sum())} vs {int(sel2.sum())}", "abs_diff": "",
                       "pass": bool((sel == sel2).all())})
        allp = np.concatenate([pv["S1"]["p"].to_numpy(), pv["S2"]["p"].to_numpy()])
        checks.append({"check": f"rolling_{name}_p_in_range", "definition": f"{name}: unit p-values in (0, 1]",
                       "expected": "(0, 1]", "obtained": f"{allp.min():.4g}-{allp.max():.4g}", "abs_diff": "",
                       "pass": bool((allp > 0).all() and (allp <= 1).all())})
        for iso in nc.index:
            r = nc.loc[iso]
            unit_rows.append({
                "series": name, "iso3": iso, "rsl": r["rsl"], "cpa": r["cpa"], "hq": r["hq"], "eea": r["eea"],
                "pct_S1": r["pct_S1"], "pct_S2": r["pct_S2"],
                "excess_Mt_S1": r["excess_total_t_S1"] / MT, "excess_Mt_S2": r["excess_total_t_S2"] / MT,
                "max_abs_placebo_rsd16": r["max_abs_placebo"], "robust_rsd16": bool(r["robust"]),
                "n_rolling_runs": 2 * len(dates), "max_abs_rolling": r["max_abs_rolling"],
                "robust_equal_length": bool(r["robust_equal_length"]),
                "sigma_S1": pv["S1"].loc[iso, "sigma"], "z_S1": pv["S1"].loc[iso, "z"], "p_S1": pv["S1"].loc[iso, "p"],
                "sigma_S2": pv["S2"].loc[iso, "sigma"], "z_S2": pv["S2"].loc[iso, "z"], "p_S2": pv["S2"].loc[iso, "p"],
                "p_u": p_u.loc[iso], "sign_agree": bool(r["sign_agree"]),
                "p_bh_input": float(p_bh[list(nc.index).index(iso)]),
                "bh_adjusted_p": float(adj[list(nc.index).index(iso)]),
                "bh_candidate": bool(sel[list(nc.index).index(iso)])})
        cands = sorted(nc.index[sel])
        rob16, robeq = set(nc.index[nc["robust"].astype(bool)]), set(nc.index[nc["robust_equal_length"]])
        bh_rows.append({"series": name, "placebo_dates": f"{dates[0]}..{dates[-1]}", "n_dates": len(dates),
                        "m_noncontrol": len(nc), "n_sign_disagree": int((~nc["sign_agree"]).sum()),
                        "n_null_S1": nnull["S1"], "n_null_S2": nnull["S2"], "q": Q,
                        "n_candidates": len(cands), "expected_false_discoveries": Q * len(cands),
                        "candidates": " ".join(cands),
                        "n_robust_rsd16": len(rob16), "robust_rsd16": " ".join(sorted(rob16)),
                        "n_robust_equal_length": len(robeq), "robust_equal_length": " ".join(sorted(robeq)),
                        "equal_length_gained": " ".join(sorted(robeq - rob16)),
                        "equal_length_lost": " ".join(sorted(rob16 - robeq))})
        checks.append({"check": f"rolling_{name}_null_size", "definition": f"{name}: null draws per specification = "
                       "non-control units x dates", "expected": str(len(nc) * len(dates)),
                       "obtained": f"{nnull['S1']}; {nnull['S2']}", "abs_diff": "",
                       "pass": nnull["S1"] == nnull["S2"] == len(nc) * len(dates)})

        # totals (net) under the equal-length rule
        ag = runs[runs["level"] == "aggregate"]
        main_pct = {sp: 100 * nc[f"excess_total_t_{sp}"].sum() / nc["cf_total_t" if sp == "S1" else "cf_total_t_S2"].sum()
                    for sp in imp.SPECS}
        mx = ag["pct"].abs().max()
        sys_rows.append({"analysis": name, "unit": "TOTAL (net, economies)", "pct_S1": main_pct["S1"],
                         "pct_S2": main_pct["S2"], "n_rolling_runs": len(ag), "max_abs_rolling": mx,
                         "rolling_pct_min": ag["pct"].min(), "rolling_pct_max": ag["pct"].max(),
                         "robust_equal_length": bool(imp.robust(main_pct["S1"], main_pct["S2"], mx)),
                         "robust_rsd16": np.nan})

        # RS-D32 gross
        cf_act = nc["cf_total_t"].sum()
        e1 = nc["excess_total_t_S1"]
        act = {"gains": 100 * e1[e1 > 0].sum() / cf_act, "losses": 100 * e1[e1 < 0].sum() / cf_act}
        s1 = ur[(ur["spec"] == "S1") & ur["unit"].isin(nc.index)]
        pg = []
        for p, g in s1.groupby("placebo_date"):
            cf = g["cf_t"].sum()
            pg.append({"series": name, "row": "placebo", "placebo_date": p,
                       "gains_pct": 100 * g.loc[g["excess_t"] > 0, "excess_t"].sum() / cf,
                       "losses_pct": 100 * g.loc[g["excess_t"] < 0, "excess_t"].sum() / cf,
                       "gains_Mt": g.loc[g["excess_t"] > 0, "excess_t"].sum() / MT,
                       "losses_Mt": g.loc[g["excess_t"] < 0, "excess_t"].sum() / MT, "cf_Mt": cf / MT})
        pg = pd.DataFrame(pg)
        rank_g = 1 + int((pg["gains_pct"] > act["gains"]).sum())
        rank_l = 1 + int((pg["losses_pct"] < act["losses"]).sum())
        gross_rows += pg.to_dict("records")
        gross_rows.append({"series": name, "row": "actual", "placebo_date": "main (2023-12)",
                           "gains_pct": act["gains"], "losses_pct": act["losses"],
                           "gains_Mt": e1[e1 > 0].sum() / MT, "losses_Mt": e1[e1 < 0].sum() / MT,
                           "cf_Mt": cf_act / MT, "max_placebo_gains_pct": pg["gains_pct"].max(),
                           "max_abs_placebo_losses_pct": pg["losses_pct"].abs().max(),
                           "rank_gains_of_n": f"{rank_g} of {len(pg) + 1}",
                           "rank_losses_of_n": f"{rank_l} of {len(pg) + 1}"})
        print(f"{name}: {len(dates)} dates, robust (equal length) {len(robeq)}: {' '.join(sorted(robeq))}; "
              f"BH candidates {len(cands)}: {' '.join(cands)}; gross rank gains {rank_g}, losses {rank_l} of "
              f"{len(pg) + 1} ({time.perf_counter() - t0:.1f} s)")

    # ---- world ---------------------------------------------------------------------
    summ = pd.read_csv(TABLES / "rsd2_summary.csv").set_index(["run", "spec"])
    for run, s in world_setups().items():
        t0 = time.perf_counter()
        runs, dates = rolling_runs(f"world_{run}", s, panama=False)
        run_frames.append(runs)
        n_runs = runs.groupby(["placebo_date", "spec"]).ngroups
        checks.append({"check": f"rolling_world_{run}_runs", "definition": f"world {run}: rolling runs = dates x S1, S2 "
                       f"({dates[0]}..{dates[-1]})", "expected": str(2 * len(dates)), "obtained": str(n_runs),
                       "abs_diff": "", "pass": n_runs == 2 * len(dates)})
        nm = runs["n_treated_months"].unique()
        checks.append({"check": f"rolling_world_{run}_window_length", "definition": f"world {run}: treated months in "
                       "every rolling run", "expected": "23", "obtained": " ".join(map(str, sorted(nm))),
                       "abs_diff": "", "pass": list(nm) == [23]})
        t = s["units"].set_index("vessel")
        ur = runs[runs["level"] == "unit"]
        mx = ur.groupby("unit")["pct"].apply(lambda x: x.abs().max())
        for v in t.index:
            sys_rows.append({"analysis": f"world {run}", "unit": v, "pct_S1": t.loc[v, "pct_S1"],
                             "pct_S2": t.loc[v, "pct_S2"], "n_rolling_runs": int((ur["unit"] == v).sum()),
                             "max_abs_rolling": mx[v],
                             "rolling_pct_min": ur.loc[ur["unit"] == v, "pct"].min(),
                             "rolling_pct_max": ur.loc[ur["unit"] == v, "pct"].max(),
                             "robust_equal_length": bool(imp.robust(t.loc[v, "pct_S1"], t.loc[v, "pct_S2"], mx[v])),
                             "max_abs_placebo_rsd16": t.loc[v, "max_abs_placebo"], "robust_rsd16": bool(t.loc[v, "robust"])})
        ag = runs[runs["level"] == "aggregate"]
        mxa = ag["pct"].abs().max()
        p1, p2 = summ.loc[(run, "S1"), "pct"], summ.loc[(run, "S2"), "pct"]
        sys_rows.append({"analysis": f"world {run}", "unit": "TOTAL (treated types)", "pct_S1": p1, "pct_S2": p2,
                         "n_rolling_runs": len(ag), "max_abs_rolling": mxa, "rolling_pct_min": ag["pct"].min(),
                         "rolling_pct_max": ag["pct"].max(),
                         "robust_equal_length": bool(imp.robust(p1, p2, mxa)),
                         "max_abs_placebo_rsd16": summ.loc[(run, "S1"), "max_abs_placebo_pct"],
                         "robust_rsd16": bool(summ.loc[(run, "S1"), "total_robust"])})
        print(f"world {run}: {len(dates)} dates ({time.perf_counter() - t0:.1f} s)")

    # ---- write -------------------------------------------------------------------------
    runs_all = pd.concat(run_frames, ignore_index=True)
    runs_all.to_csv(TABLES / "rolling_placebo_runs.csv", index=False)
    units = pd.DataFrame(unit_rows)
    units.to_csv(TABLES / "rolling_placebo_units.csv", index=False)
    sysd = pd.DataFrame(sys_rows)
    sysd = sysd[["analysis", "unit", "pct_S1", "pct_S2", "n_rolling_runs", "max_abs_rolling", "rolling_pct_min",
                 "rolling_pct_max", "robust_equal_length", "max_abs_placebo_rsd16", "robust_rsd16"]]
    sysd.to_csv(TABLES / "rolling_placebo_system.csv", index=False)
    pd.DataFrame(bh_rows).to_csv(TABLES / "rolling_placebo_bh.csv", index=False)
    pd.DataFrame(gross_rows).to_csv(TABLES / "rolling_placebo_gross.csv", index=False)

    # p-values recomputed independently (loop form) for one series as a check
    u = units[units["series"] == "TER_INT"].set_index("iso3")
    ur = runs_all[(runs_all["analysis"] == "TER_INT") & (runs_all["level"] == "unit") & (runs_all["spec"] == "S1")]
    P = ur.pivot(index="unit", columns="placebo_date", values="pct").reindex(u.index)
    null = []
    for iso in P.index:
        for d in P.columns:
            others = P.loc[iso].drop(d)
            null.append(abs(P.loc[iso, d] / np.sqrt(np.mean(others ** 2))))
    null = np.array(null)
    p_loop = [(1 + np.sum(null >= abs(u.loc[i, "pct_S1"] / np.sqrt(np.mean(P.loc[i] ** 2))))) / (1 + len(null))
              for i in u.index]
    d = float(np.max(np.abs(np.array(p_loop) - u["p_S1"].to_numpy())))
    checks.append({"check": "rolling_pvalues_reproduced", "definition": "TER_INT S1 unit p-values recomputed with an "
                   "explicit loop (max |difference|)", "expected": "0", "obtained": f"{d:.3g}", "abs_diff": f"{d:.3g}",
                   "pass": d < 1e-12})
    for f in ("rolling_placebo_runs.csv", "rolling_placebo_units.csv", "rolling_placebo_system.csv",
              "rolling_placebo_bh.csv", "rolling_placebo_gross.csv"):
        print(f"{rel(TABLES / f)} written")
    update_checks(checks, CHECKS_FILE, "rolling_")
    print(f"Run time {time.perf_counter() - t_all:.1f} s")


if __name__ == "__main__":
    main()
