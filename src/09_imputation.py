"""Imputation estimator (RS-D15) with placebo runs and robust classification (RS-D16).

This module is imported by 10_rsd4_economies.py and 11_rsd2_world.py.

Input: a long table with columns unit, period (YYYY-MM), days, value_t,
per_day, control (bool) and, when the Panama term is used, P and R.

Model on untreated observations (weighted least squares), outcome log(per_day):
- S1: unit x calendar-month effects + month effects (+ gamma * P * R);
- S2: S1 + a unit-specific linear trend (year - 2019) + (month - 1) / 12.

Normalisation. Unit x calendar-month effects and month effects are collinear:
for each calendar month, the sum of the unit dummies equals the sum of the
month dummies of that calendar month. The month dummies of 2019-01..2019-12
are therefore dropped (one per calendar month). In S2 the unit trends add one
more dependency (their sum is a combination of the other columns), so the
trend of the first unit is dropped. Fitted values, and hence counterfactuals,
do not depend on this choice. The fit is solved exactly from the sparse
normal equations (scipy.sparse.linalg.spsolve, SuperLU); `dense_check`
compares the fitted values with a dense minimum-norm least-squares solve.

Weights: the unit's mean per_day over the periods <= 2023-11 present in the
run's data. Counterfactual: exp(fitted) * S_u, with S_u the unweighted mean of
exp(residual) over the unit's untreated observations. Excess:
(per_day - counterfactual) * days, for treated observations.
"""

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

PLACEBO_DATES = ("2020-12", "2021-06", "2021-12", "2022-06", "2022-12")
SPECS = ("S1", "S2")
WEIGHT_END = "2023-11"
SOLVER = "scipy.sparse.linalg.spsolve (SuperLU) on the weighted normal equations"


def add_months(period, k):
    return (pd.Period(period, freq="M") + k).strftime("%Y-%m")


def fit_impute(df, shock, drop=(), last=None, spec="S1", panama=False, dense_check=False,
               return_untreated=False):
    """Fit RS-D15 on untreated observations and impute treated ones.

    Returns (treated, diagnostics, weights):
    - treated: DataFrame of treated rows with cf_per_day, cf_t and excess_t;
    - diagnostics: dict with fit statistics;
    - weights: Series of unit weights.
    With return_untreated=True a fourth element is returned: the untreated rows
    with fitted_per_day = exp(fitted) * S_u (used for figures only; the
    estimates are the same either way).
    """
    d = df[~df["period"].isin(list(drop))]
    if last is not None:
        d = d[d["period"] <= last]
    d = d.sort_values(["unit", "period"]).reset_index(drop=True)

    post = d["period"] >= shock
    control = d["control"].astype(bool)
    untreated = (~post | control).to_numpy()
    treated = (post & ~control).to_numpy()
    d = d[untreated | treated].reset_index(drop=True)
    untreated, treated = untreated[untreated | treated], treated[untreated | treated]

    weights = d[d["period"] <= WEIGHT_END].groupby("unit")["per_day"].mean()
    w = d["unit"].map(weights).to_numpy()
    y = np.log(d["per_day"].to_numpy())

    units = sorted(d["unit"].unique())
    u_idx = d["unit"].map({u: i for i, u in enumerate(units)}).to_numpy()
    year = d["period"].str[:4].astype(int).to_numpy()
    month = d["period"].str[5:7].astype(int).to_numpy()
    n = len(d)

    rows, cols, vals = [], [], []
    names = []
    # unit x calendar-month effects
    uc = u_idx * 12 + (month - 1)
    uc_codes = {c: i for i, c in enumerate(sorted(set(uc)))}
    rows.append(np.arange(n)); cols.append(np.array([uc_codes[c] for c in uc])); vals.append(np.ones(n))
    names += [f"a[{units[c // 12]},{c % 12 + 1}]" for c in sorted(uc_codes)]
    k = len(uc_codes)
    # month effects, 2019 months dropped
    per = d["period"].to_numpy()
    m_periods = sorted(p for p in set(per) if p >= "2020-01")
    m_codes = {p: k + i for i, p in enumerate(m_periods)}
    has_m = np.array([p in m_codes for p in per])
    rows.append(np.arange(n)[has_m]); cols.append(np.array([m_codes[p] for p in per[has_m]], dtype=int))
    vals.append(np.ones(has_m.sum()))
    names += [f"b[{p}]" for p in m_periods]
    k += len(m_periods)
    # Panama term
    panama_used = False
    if panama:
        pr = (d["P"] * d["R"]).to_numpy(dtype=float)
        if np.any(pr[untreated] != 0):
            nz = pr != 0
            rows.append(np.arange(n)[nz]); cols.append(np.full(nz.sum(), k)); vals.append(pr[nz])
            names.append("gamma[P*R]")
            k += 1
            panama_used = True
    # unit trends (S2), first unit dropped
    if spec == "S2":
        t = (year - 2019) + (month - 1) / 12
        keep = u_idx > 0
        rows.append(np.arange(n)[keep]); cols.append(k + u_idx[keep] - 1); vals.append(t[keep])
        names += [f"c[{u}]" for u in units[1:]]
        k += len(units) - 1

    X = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, k))
    Xu, yu, wu = X[untreated], y[untreated], w[untreated]
    A = (Xu.T @ sp.diags(wu) @ Xu).tocsc()
    b = Xu.T @ (wu * yu)
    beta = spsolve(A, b)
    rel_resid = float(np.linalg.norm(A @ beta - b) / np.linalg.norm(b))

    fitted = X @ beta
    resid = yu - fitted[untreated]
    s_u = pd.Series(np.exp(resid)).groupby(d.loc[untreated, "unit"].to_numpy()).mean()

    ybar = np.sum(wu * yu) / np.sum(wu)
    diag = {
        "spec": spec, "shock": shock, "last": d["period"].max(),
        "n_units": len(units), "n_control_units": int(d.loc[d["control"].astype(bool), "unit"].nunique()),
        "n_untreated": int(untreated.sum()), "n_treated": int(treated.sum()), "n_params": k,
        "panama_term": panama_used,
        "gamma": float(beta[names.index("gamma[P*R]")]) if panama_used else np.nan,
        "weighted_r2": float(1 - np.sum(wu * resid ** 2) / np.sum(wu * (yu - ybar) ** 2)),
        "rmse_log": float(np.sqrt(np.mean(resid ** 2))),
        "solver_rel_residual": rel_resid,
    }
    if dense_check:
        sw = np.sqrt(wu)
        beta_d, *_ = np.linalg.lstsq(Xu.toarray() * sw[:, None], yu * sw, rcond=None)
        diag["dense_max_abs_fitted_diff"] = float(np.max(np.abs(X.toarray() @ beta_d - fitted)))
        diag["dense_rank"] = int(np.linalg.matrix_rank(Xu.toarray() * sw[:, None]))

    tr = d.loc[treated, ["unit", "period", "days", "value_t", "per_day"]].copy()
    tr["cf_per_day"] = np.exp(fitted[treated]) * tr["unit"].map(s_u).to_numpy()
    tr["cf_t"] = tr["cf_per_day"] * tr["days"]
    tr["excess_t"] = (tr["per_day"] - tr["cf_per_day"]) * tr["days"]
    if return_untreated:
        un = d.loc[untreated, ["unit", "period", "days", "value_t", "per_day"]].copy()
        un["fitted_per_day"] = np.exp(fitted[untreated]) * un["unit"].map(s_u).to_numpy()
        return tr.reset_index(drop=True), diag, weights, un.reset_index(drop=True)
    return tr.reset_index(drop=True), diag, weights


def pct(excess, cf):
    return 100 * excess / cf if cf else np.nan


def placebo_runs(df, last_pre, drop=(), panama=False):
    """Run the five placebo dates with S1 and S2 (RS-D16).

    Returns (unit_pct, aggregate): unit_pct is units x 10 runs of placebo %;
    aggregate is a DataFrame with spec, date, pct, excess_t, cf_t.
    """
    unit_cols, agg = {}, []
    for p in PLACEBO_DATES:
        end = min(add_months(p, 11), last_pre)
        for spec in SPECS:
            tr, _, _ = fit_impute(df, shock=p, drop=drop, last=end, spec=spec, panama=panama)
            g = tr.groupby("unit")[["excess_t", "cf_t"]].sum()
            unit_cols[f"placebo_{p}_{spec}"] = 100 * g["excess_t"] / g["cf_t"]
            agg.append({"spec": spec, "placebo_date": p, "last_period": end,
                        "pct": pct(tr["excess_t"].sum(), tr["cf_t"].sum()),
                        "excess_t": tr["excess_t"].sum(), "cf_t": tr["cf_t"].sum()})
    return pd.DataFrame(unit_cols), pd.DataFrame(agg)


def robust(pct_s1, pct_s2, max_abs_placebo):
    """RS-D16: same sign in S1 and S2, and min(|S1 %|, |S2 %|) > max |placebo %|."""
    same_sign = np.sign(pct_s1) == np.sign(pct_s2)
    return same_sign & (np.minimum(np.abs(pct_s1), np.abs(pct_s2)) > max_abs_placebo)


def summarise_unit(tr):
    """Per-unit totals of a treated table: excess, counterfactual, %, by year."""
    g = tr.groupby("unit")[["excess_t", "cf_t"]].sum()
    g["pct"] = 100 * g["excess_t"] / g["cf_t"]
    by_year = tr.assign(year=tr["period"].str[:4]).pivot_table(
        index="unit", columns="year", values="excess_t", aggfunc="sum")
    return g, by_year
