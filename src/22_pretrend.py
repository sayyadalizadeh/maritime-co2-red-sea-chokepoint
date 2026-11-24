"""Pre-trend tests (RS-D30), following Test 1 of Borusyak et al. (2024).

The S1 model of RS-D15 is fitted on untreated observations only, extended by terms W; the RS-D15
weights are used (the unit's mean per-day value up to 2023-11). Economies keep the Panama term,
as in the main model; the system-level runs have none. The fixed effects are partialled out
(Frisch-Waugh-Lovell, design.wls_fwl).

(a) Aggregate test. W_h = treated unit x 1[t = 2023-12 - h], h = 1..12 (departure: h = 2..12,
    2023-11 being excluded). gamma = 0 is tested with a cluster-robust Wald test, clusters = units:
        V = G / (G - 1) * B M B,  B = (W~' Omega W~)^-1,  M = sum_g s_g s_g',
        s_g = sum over the observations of unit g of W~_i * omega_i * e_i,
    W~ = W with the fixed effects partialled out, e = residuals of the extended model. When the
    rank of V is below the number of terms (fewer clusters than terms), the Wald statistic uses
    the Moore-Penrose inverse and df = rank(V). Reported: gamma_h as % (exp(gamma_h) - 1) with
    95% intervals exp(gamma_h +- 1.96 se) - 1; Wald statistic, df and chi-squared p-value; and the
    F form (Wald / df on df and G - 1 degrees of freedom).
    Runs: (1) container ships, treated = CONTAINER, controls = the eight non-transit types;
    (2) the ten cargo (transit) types treated, the eight non-transit types as controls;
    (3) residence (RES_TOTAL) and (4) departure (TER_INT), non-control economies treated, main
    panels and control pools.

(b) Per-unit test. W = 1[unit u] x 1[t in the last 12 pre-crisis months] (residence and system
    level: 2022-12..2023-11; departure: 2022-12..2023-10, 11 months). Units: the R0 robust
    economies of both principles (main panels) and container ships (RS-D2 main run: 18 types,
    transit types treated). Standard error: Newey-West, Bartlett kernel, 3 lags, from unit u's
    scores W~_t * omega_t * e_t over its pre-crisis months in time order (departure: 2023-11
    absent, the series is taken in order), weights 1 - l / 4 for lags l = 1..3; denominator the
    full W~' Omega W~. p-value from the
    normal distribution; flag = p < 0.05.

Outputs
- outputs/tables/pretrend_aggregate.csv, pretrend_units.csv
- outputs/checks/revision_checks.csv (rows starting with 'pretrend_')
"""

import importlib
import time

import numpy as np
import pandas as pd
from scipy import stats

import config as C
import design as D
from common import rel, update_checks

imp = importlib.import_module("09_imputation")
m10 = importlib.import_module("10_rsd4_economies")
m11 = importlib.import_module("11_rsd2_world")

TABLES = C.OUTPUTS / "tables"
CHECKS_FILE = C.CHECKS / "revision_checks.csv"
H_MAX = 12
NW_LAGS = 3
Z95 = 1.959963984540054


def world_table(treated, units):
    w = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w[(w["period"] >= C.PRE_START) & (w["period"] <= C.MAIN_END) & w["vessel"].isin(units)]
    df = w.rename(columns={"vessel": "unit"})[["unit", "period", "days", "value_t", "per_day"]].copy()
    df["control"] = ~df["unit"].isin(treated)
    return df.reset_index(drop=True)


def economy_table(principle):
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    R = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")["R"]
    return m10.build_df(m10.PRINCIPLES[principle], ex, pt, R)


def runs():
    """name -> (table, drop, panama)."""
    return {
        "container": (world_table({"CONTAINER"}, ["CONTAINER"] + m11.NON_TRANSIT), (), False),
        "cargo_types": (world_table(set(m11.TRANSIT), m11.TRANSIT + m11.NON_TRANSIT), (), False),
        "residence": (economy_table("residence"), tuple(m10.PRINCIPLES["residence"]["drop"]), True),
        "departure": (economy_table("departure"), tuple(m10.PRINCIPLES["departure"]["drop"]), True),
    }


def untreated_design(df, drop, panama):
    d, untreated, _ = D.prepare(df, C.SHOCK_START, drop, C.MAIN_END)
    du = d[untreated].reset_index(drop=True)
    wts = D.unit_weights(du)
    Z, names = D.fe_design(du, np.ones(len(du), dtype=bool), "S1", panama)
    w = du["unit"].map(wts).to_numpy()
    y = np.log(du["per_day"].to_numpy())
    return du, Z, names, w, y


def aggregate_test(name, df, drop, panama):
    du, Z, _, w, y = untreated_design(df, drop, panama)
    hs = [h for h in range(1, H_MAX + 1) if add_months(C.SHOCK_START, -h) not in drop]
    per = [add_months(C.SHOCK_START, -h) for h in hs]
    treated_unit = ~du["control"].astype(bool).to_numpy()
    W = np.column_stack([(treated_unit & (du["period"].to_numpy() == p)).astype(float) for p in per])
    gamma, W_t, e, _ = D.wls_fwl(Z, W, y, w)
    units = du["unit"].to_numpy()
    G = len(np.unique(units))
    scores = pd.DataFrame(W_t * (w * e)[:, None]).groupby(units).sum().to_numpy()
    meat = scores.T @ scores
    bread = np.linalg.inv(W_t.T @ (w[:, None] * W_t))
    V = G / (G - 1) * bread @ meat @ bread
    rank = int(np.linalg.matrix_rank(V))
    Vinv = np.linalg.inv(V) if rank == len(hs) else np.linalg.pinv(V)
    wald = float(gamma @ Vinv @ gamma)
    p_chi = float(stats.chi2.sf(wald, rank))
    F = wald / rank
    p_F = float(stats.f.sf(F, rank, G - 1))
    se = np.sqrt(np.diag(V))
    rows = []
    for h, p, g, s in zip(hs, per, gamma, se):
        rows.append({"test": name, "row": "h", "h": h, "period": p, "gamma": g, "se_cluster": s,
                     "pct": 100 * np.expm1(g), "ci95_lo_pct": 100 * np.expm1(g - Z95 * s),
                     "ci95_hi_pct": 100 * np.expm1(g + Z95 * s)})
    rows.append({"test": name, "row": "joint", "n_clusters": G,
                 "n_treated_units": int(du.loc[treated_unit, "unit"].nunique()), "n_obs": len(du),
                 "n_terms": len(hs), "rank_V": rank, "wald_chi2": wald, "df": rank, "p_chi2": p_chi,
                 "F": F, "df1": rank, "df2": G - 1, "p_F": p_F,
                 "note": ("rank of the cluster-robust covariance below the number of terms; Wald statistic with the "
                          "Moore-Penrose inverse, df = rank" if rank < len(hs) else "")})
    print(f"(a) {name}: G = {G}, terms {len(hs)}, rank {rank}, Wald {wald:.3f}, p = {p_chi:.4f}, "
          f"F p = {p_F:.4f}")
    return rows


def add_months(period, k):
    return imp.add_months(period, k)


def newey_west(s, lags):
    s = np.asarray(s, dtype=float)
    S = float(s @ s)
    for l in range(1, lags + 1):
        S += 2 * (1 - l / (lags + 1)) * float(s[l:] @ s[:-l])
    return S


def unit_test(name, df, drop, panama, unit, last_pre):
    du, Z, _, w, y = untreated_design(df, drop, panama)
    # the last 12 pre-crisis calendar months (2022-12..2023-11) without excluded months
    win = [p for p in imp_months(add_months(C.SHOCK_START, -12), add_months(C.SHOCK_START, -1)) if p not in drop]
    W = ((du["unit"].to_numpy() == unit) & du["period"].isin(win).to_numpy()).astype(float)
    gamma, W_t, e, _ = D.wls_fwl(Z, W, y, w)
    W_t = W_t[:, 0]
    own = ((du["unit"] == unit) & (du["period"] <= last_pre)).to_numpy()
    order = np.argsort(du.loc[own, "period"].to_numpy())
    s = (W_t * w * e)[own][order]
    denom = float(W_t @ (w * W_t))
    se = np.sqrt(newey_west(s, NW_LAGS)) / denom
    g = float(gamma[0])
    z = g / se
    p = float(2 * stats.norm.sf(abs(z)))
    return {"set": name, "unit": unit, "window": f"{win[0]}..{win[-1]}", "n_window_months": len(win),
            "n_pre_months_unit": int(own.sum()), "gamma": g, "pct": 100 * np.expm1(g), "se_nw": se,
            "pct_ci95_lo": 100 * np.expm1(g - Z95 * se), "pct_ci95_hi": 100 * np.expm1(g + Z95 * se),
            "z": z, "p_value": p, "pretrend_flag": p < 0.05}


def imp_months(a, b):
    return pd.period_range(a, b, freq="M").strftime("%Y-%m").tolist()


def design_check(df, drop, panama, label, checks):
    """The design and solver reproduce fit_impute's S1 counterfactual."""
    import scipy.sparse as sp
    from scipy.sparse.linalg import splu
    d, untreated, treated = D.prepare(df, C.SHOCK_START, drop, C.MAIN_END)
    X, _ = D.fe_design(d, untreated, "S1", panama)
    wts = D.unit_weights(d)
    w = d["unit"].map(wts).to_numpy()
    y = np.log(d["per_day"].to_numpy())
    Xu, wu, yu = X[untreated], w[untreated], y[untreated]
    beta = splu((Xu.T @ sp.diags(wu) @ Xu).tocsc()).solve(Xu.T @ (wu * yu))
    fit = X @ beta
    s_u = pd.Series(np.exp(yu - fit[untreated])).groupby(d.loc[untreated, "unit"].to_numpy()).mean()
    cf = np.exp(fit[treated]) * d.loc[treated, "unit"].map(s_u).to_numpy()
    tr, _, _ = imp.fit_impute(df, shock=C.SHOCK_START, drop=drop, last=C.MAIN_END, spec="S1", panama=panama)
    ref = tr.sort_values(["unit", "period"])["cf_per_day"].to_numpy()
    diff = float(np.max(np.abs(cf / ref - 1)))
    checks.append({"check": f"pretrend_design_{label}", "definition": f"{label}: design.fe_design + solver reproduce "
                   "09_imputation S1 counterfactuals (max relative difference <= 1e-9)", "expected": "agree",
                   "obtained": f"{diff:.3g}", "abs_diff": f"{diff:.3g}", "pass": diff <= 1e-9})


def main():
    t0 = time.perf_counter()
    checks = []
    R = runs()
    agg_rows = []
    for name, (df, drop, panama) in R.items():
        design_check(df, drop, panama, name, checks)
        agg_rows += aggregate_test(name, df, drop, panama)
    agg = pd.DataFrame(agg_rows)
    cols = ["test", "row", "h", "period", "gamma", "se_cluster", "pct", "ci95_lo_pct", "ci95_hi_pct", "n_clusters",
            "n_treated_units", "n_obs", "n_terms", "rank_V", "wald_chi2", "df", "p_chi2", "F", "df1", "df2", "p_F",
            "note"]
    agg = agg[cols]
    for c in ("h", "n_clusters", "n_treated_units", "n_obs", "n_terms", "rank_V", "df", "df1", "df2"):
        agg[c] = agg[c].astype("Int64")
    agg.to_csv(TABLES / "pretrend_aggregate.csv", index=False)
    for name in R:
        j = agg[(agg["test"] == name) & (agg["row"] == "joint")].iloc[0]
        exp_terms = 11 if name == "departure" else 12
        checks.append({"check": f"pretrend_{name}_terms", "definition": f"(a) {name}: number of W_h terms; clusters "
                       f"{j['n_clusters']}; rank of V {j['rank_V']}", "expected": str(exp_terms),
                       "obtained": str(j["n_terms"]), "abs_diff": "", "pass": int(j["n_terms"]) == exp_terms})
        ok = 0 < j["p_chi2"] <= 1 and 0 < j["p_F"] <= 1
        checks.append({"check": f"pretrend_{name}_p_in_range", "definition": f"(a) {name}: Wald p-values in (0, 1]",
                       "expected": "(0, 1]", "obtained": f"{j['p_chi2']:.4g}; {j['p_F']:.4g}", "abs_diff": "",
                       "pass": bool(ok)})

    # ---- (b) per unit ------------------------------------------------------------
    unit_rows = []
    for principle in ("residence", "departure"):
        df, drop, panama = R[principle]
        u = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv")
        last_pre = m10.PRINCIPLES[principle]["last_pre"]
        for iso in sorted(u.loc[u["robust"], "iso3"]):
            unit_rows.append(unit_test(principle, df, drop, panama, iso, last_pre))
    wdf = world_table(set(m11.TRANSIT), m11.TRANSIT + m11.NON_TRANSIT)
    unit_rows.append(unit_test("system (RS-D2 main run)", wdf, (), False, "CONTAINER", m11.LAST_PRE))
    ut = pd.DataFrame(unit_rows)
    ut.to_csv(TABLES / "pretrend_units.csv", index=False)
    checks.append(exact_check_rows("pretrend_units_n", "(b) units tested (11 residence + 9 departure robust "
                                   "economies + container ships)", 21, len(ut)))
    nwin = " ".join(f"{s}:{w}:{n}" for s, w, n in ut[["set", "window", "n_window_months"]].drop_duplicates()
                    .itertuples(index=False))
    ok = set(ut.loc[ut["set"] == "departure", "n_window_months"]) == {11} and \
        set(ut.loc[ut["set"] != "departure", "n_window_months"]) == {12}
    checks.append(exact_check_rows("pretrend_units_window", f"(b) windows and months: {nwin}", "departure 11; others 12",
                                   "departure 11; others 12" if ok else nwin, ok))
    pin = bool(((ut["p_value"] > 0) & (ut["p_value"] <= 1)).all())
    checks.append({"check": "pretrend_units_p_in_range", "definition": "(b) p-values in (0, 1]", "expected": "(0, 1]",
                   "obtained": f"{ut['p_value'].min():.4g}-{ut['p_value'].max():.4g}", "abs_diff": "", "pass": pin})
    for r in ut.itertuples():
        print(f"(b) {r.set:24s} {r.unit:9s} gamma {r.pct:+7.2f}%  se {r.se_nw:.4f}  p {r.p_value:.4f}  "
              f"flag {r.pretrend_flag}")
    print(f"{rel(TABLES / 'pretrend_aggregate.csv')}, {rel(TABLES / 'pretrend_units.csv')} written")
    update_checks(checks, CHECKS_FILE, "pretrend_")
    print(f"Run time {time.perf_counter() - t0:.1f} s")


def exact_check_rows(name, definition, expected, obtained, ok=None):
    return {"check": name, "definition": definition, "expected": str(expected), "obtained": str(obtained),
            "abs_diff": "", "pass": (str(expected) == str(obtained)) if ok is None else bool(ok)}


if __name__ == "__main__":
    main()
