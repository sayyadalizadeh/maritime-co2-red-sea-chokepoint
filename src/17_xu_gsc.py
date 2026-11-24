"""Generalized synthetic control (Xu, 2017) for the R0 robust economies (RS-D20), numpy only.

Units: treated = the R0 robust economies of a principle; controls = that principle's
R0 control pool. Window 2019-01..2025-10; departure drops 2023-11 everywhere.

Algorithm (one principle; "pre-crisis months" = window months before 2023-12):
 1. Outcome. y_ut = log(per-day value). Z_ut = y_ut minus the unit's mean of y over
    its pre-crisis months of the same calendar month (unit x calendar-month mean).
 2. Time effects. delta_t = weighted mean of Z_ut over the control units in month t,
    weights = the unit's mean per-day value over the months up to 2023-11 present
    in the data (as in RS-D15).
 3. Control residuals. U = Z_controls - delta (months x controls, all window months).
    Scale column u by sqrt(weight_u) and take the SVD: U_s = P S Q'. The factors
    F_r (months x r) are the first r columns of P multiplied by their singular
    values. r = 0, 1, ..., 5 (r = 0 means no factors).
 4. Choice of r. Leave-one-period-out cross-validation over the treated units'
    pre-crisis months: for each r, each treated unit and each pre-crisis month s,
    estimate the unit's loadings by OLS (no intercept) of Z - delta on F_r over the
    other pre-crisis months and predict month s. The pooled mean squared
    prediction error over units and months is computed for every r; the smallest
    wins, ties going to the smaller r.
 5. Loadings. For each treated unit, OLS (no intercept) of Z - delta on F_r over
    all its pre-crisis months: lambda_u.
 6. Counterfactual. Z0_ut = delta_t + F_r,t lambda_u; log per-day counterfactual =
    Z0_ut + the unit's calendar-month mean; cf_per_day = exp(.) x S_u, with S_u the
    mean of exp(pre-crisis residual Z - Z0) over the unit's pre-crisis months.
    Excess = (per_day - cf_per_day) x days over 2023-12..2025-10; % = sum excess /
    sum (cf_per_day x days). Pre-crisis RMSE = root mean squared pre-crisis residual.
 7. Placebos. For each RS-D16 date p, data are truncated at min(p + 11 months, last
    pre-crisis month: 2023-11, or 2023-10 for departure). Steps 1-6 are repeated on
    the truncated data with r fixed at the main choice; the months before p are the
    pre-crisis months, and p..truncation are the treated months. Each unit's
    placebo % is recorded; max |placebo %| is taken over the 5 dates.

Validation (run once, seed 20261121): a simulated panel of 30 control and 5 treated
units over the 82 window months, log outcome = unit x calendar-month effects + a
common month effect + 2 factors with random loadings + Gaussian noise (SD 0.02),
equal weights. (a) No effect: cross-validation should choose r = 2 and each
treated unit's window % should be within +-1. (b) +10% (log 0.0953) added to the
treated units from 2023-12: each estimated % should be within 10 +- 1.

Outputs
- outputs/tables/xu_gsc.csv
- outputs/checks/xu_gsc_cv.csv
- outputs/checks/xu_gsc_validation.csv
"""

import importlib
import time

import numpy as np
import pandas as pd

import config as C
from common import days_in, months, rel

m10 = importlib.import_module("10_rsd4_economies")
imp = importlib.import_module("09_imputation")

TABLES = C.OUTPUTS / "tables"
MT = 1e6
R_GRID = range(6)
SEED = 20261121


def ols(X, Y):
    """OLS without intercept; returns zeros when X has no columns."""
    if X.shape[1] == 0:
        return np.zeros((0,) + Y.shape[1:])
    return np.linalg.lstsq(X, Y, rcond=None)[0]


def gsc(y, per_day, days, treated, controls, weights, pre, post, r=None, r_grid=R_GRID):
    """Steps 1-6 for one panel.

    y, per_day, days: DataFrames (periods x units), periods sorted, no missing values.
    weights: Series of unit weights. pre, post: boolean arrays over periods.
    Returns dict with r, cv (Series of MSPE by r, or None), and a per-unit table.
    """
    periods = y.index.to_numpy()
    cal = np.array([p[5:7] for p in periods])
    mu = pd.DataFrame(index=periods, columns=y.columns, dtype=float)
    for c in np.unique(cal):
        rows = cal == c
        mu.loc[rows] = np.repeat(y[rows & pre].mean().to_numpy()[None, :], rows.sum(), axis=0)
    Z = y - mu

    wc = weights[controls].to_numpy()
    delta = (Z[controls].to_numpy() * wc).sum(axis=1) / wc.sum()
    U = Z[controls].to_numpy() - delta[:, None]
    P, s, _ = np.linalg.svd(U * np.sqrt(wc)[None, :], full_matrices=False)
    F_all = P * s
    Rt = Z[treated].to_numpy() - delta[:, None]
    pre_idx = np.where(pre)[0]

    cv = None
    if r is None:
        mspe = {}
        for rr in r_grid:
            F = F_all[pre_idx, :rr]
            errs = []
            for j in range(len(treated)):
                yj = Rt[pre_idx, j]
                for k in range(len(pre_idx)):
                    keep = np.arange(len(pre_idx)) != k
                    pred = F[k] @ ols(F[keep], yj[keep]) if rr else 0.0
                    errs.append((yj[k] - pred) ** 2)
            mspe[rr] = float(np.mean(errs))
        cv = pd.Series(mspe)
        r = min(r_grid, key=lambda rr: (mspe[rr], rr))  # smallest MSPE; ties to the smaller r

    F = F_all[:, :r]
    lam = ols(F[pre_idx], Rt[pre_idx])
    fit = F @ lam if r else np.zeros_like(Rt)
    resid_pre = Rt[pre_idx] - fit[pre_idx]
    S = np.exp(resid_pre).mean(axis=0)
    log_cf = delta[:, None] + fit + mu[treated].to_numpy()
    cf_pd = np.exp(log_cf) * S[None, :]
    d = days[treated].to_numpy()
    exc = ((per_day[treated].to_numpy() - cf_pd) * d)[post]
    cft = (cf_pd * d)[post]
    out = pd.DataFrame({"unit": treated, "pre_rmse_log": np.sqrt((resid_pre ** 2).mean(axis=0)),
                        "excess_t": exc.sum(axis=0), "cf_t": cft.sum(axis=0)}).set_index("unit")
    out["pct"] = 100 * out["excess_t"] / out["cf_t"]
    return {"r": r, "cv": cv, "units": out}


def wide(df, col, periods):
    return df.pivot(index="period", columns="unit", values=col).reindex(periods)


def run_panel(df, treated, controls, shock, last_pre, drop=(), r=None, r_grid=R_GRID):
    """Main run and placebo runs for one principle (long input: unit, period, days, per_day)."""
    df = df[~df["period"].isin(list(drop)) & df["unit"].isin(treated + controls)]

    def one(data, shock_p, r_fixed):
        periods = sorted(data["period"].unique())
        weights = data[data["period"] <= C.PRE_END].groupby("unit")["per_day"].mean()
        pdw = wide(data, "per_day", periods)
        res = gsc(np.log(pdw), pdw, wide(data, "days", periods), treated, controls, weights,
                  pre=np.array([p < shock_p for p in periods]), post=np.array([p >= shock_p for p in periods]),
                  r=r_fixed, r_grid=r_grid)
        return res

    main = one(df, shock, r)
    placebo = {}
    for p in imp.PLACEBO_DATES:
        end = min(imp.add_months(p, 11), last_pre)
        placebo[p] = one(df[df["period"] <= end], p, main["r"])["units"]["pct"]
    pl = pd.DataFrame(placebo)
    return main, pl


def simulate(effect):
    """Simulated long panel (30 controls, 5 treated), log outcome as in the docstring."""
    rng = np.random.default_rng(SEED)
    periods = months(C.PRE_START, C.MAIN_END)
    n_c, n_t = 30, 5
    units = [f"C{i:02d}" for i in range(n_c)] + [f"T{i}" for i in range(n_t)]
    cal = np.array([int(p[5:7]) for p in periods])
    a = rng.normal(8.0, 1.0, size=(len(units), 1)) + rng.normal(0.0, 0.1, size=(len(units), 12))
    b = rng.normal(0.0, 0.05, size=len(periods))
    f = rng.normal(0.0, 0.1, size=(len(periods), 2))
    lam = rng.normal(0.0, 1.0, size=(len(units), 2))
    eps = rng.normal(0.0, 0.02, size=(len(periods), len(units)))
    y = a[:, cal - 1].T + b[:, None] + f @ lam.T + eps
    post = np.array([p >= C.SHOCK_START for p in periods])
    y[np.ix_(post, np.arange(n_c, n_c + n_t))] += effect
    d = days_in(pd.Series(periods)).to_numpy()
    long = pd.DataFrame({"unit": np.repeat(units, len(periods)), "period": np.tile(periods, len(units)),
                         "days": np.tile(d, len(units)), "per_day": np.exp(y.T).ravel()})
    return long, units[n_c:], units[:n_c]


def main(r_max=5):
    """r_max = 5: main results (RS-D20) and the simulation validation.
    r_max = 8: supplementary sensitivity, written to xu_gsc_r8.csv and xu_gsc_cv_r8.csv."""
    t_all = time.perf_counter()
    r_grid = range(r_max + 1)
    main_grid = r_max == 5
    suffix = "" if main_grid else f"_r{r_max}"
    rows, cv_rows, val_rows = [], [], []

    # ---- validation by simulation (main grid only) -----------------------------
    for case, effect, target in ((("a_no_effect", 0.0, 0.0), ("b_plus_10pct", np.log(1.10), 10.0))
                                 if main_grid else ()):
        long, tr, co = simulate(effect)
        long["per_day"] = long["per_day"].astype(float)
        periods = months(C.PRE_START, C.MAIN_END)
        res = gsc(np.log(wide(long, "per_day", periods)), wide(long, "per_day", periods),
                  wide(long, "days", periods), tr, co, pd.Series(1.0, index=tr + co),
                  pre=np.array([p < C.SHOCK_START for p in periods]),
                  post=np.array([p >= C.SHOCK_START for p in periods]))
        u = res["units"]
        agg = 100 * u["excess_t"].sum() / u["cf_t"].sum()
        for rr, v in res["cv"].items():
            cv_rows.append({"principle": f"simulation {case}", "r": rr, "mspe": v, "chosen": rr == res["r"]})
        ok_units = bool(((u["pct"] - target).abs() <= 1).all())
        val_rows.append({"case": case, "true_pct": target, "r_chosen": res["r"], "r_expected": 2,
                         "unit_pct": " ".join(f"{k}:{v:.3f}" for k, v in u["pct"].items()),
                         "min_unit_pct": u["pct"].min(), "max_unit_pct": u["pct"].max(), "aggregate_pct": agg,
                         "pass_r": res["r"] == 2, "pass_pct_within_1": ok_units})
        print(f"simulation {case}: r = {res['r']}, unit % {u['pct'].min():.3f}..{u['pct'].max():.3f}, "
              f"aggregate {agg:.3f}")

    # ---- the two principles --------------------------------------------------
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    for principle, cfg in m10.PRINCIPLES.items():
        t0 = time.perf_counter()
        u0 = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv").set_index("iso3")
        treated = sorted(u0.index[u0["robust"]])
        controls = sorted(u0.index[u0["control"]])
        p = pd.read_csv(C.INTERIM / cfg["panel"])
        p = p[p["in_main_window"] & p["iso3"].isin(treated + controls)]
        long = pd.DataFrame({"unit": p["iso3"], "period": p["period"], "days": p["days"], "per_day": p["per_day"]})
        main_res, pl = run_panel(long, treated, controls, C.SHOCK_START, cfg["last_pre"], drop=cfg["drop"],
                                 r_grid=r_grid)
        for rr, v in main_res["cv"].items():
            cv_rows.append({"principle": principle, "r": rr, "mspe": v, "chosen": rr == main_res["r"]})
        u = main_res["units"]
        for iso in treated:
            max_pl = pl.loc[iso].abs().max()
            row = {"principle": principle, "iso3": iso, "r": main_res["r"], "n_controls": len(controls),
                   "pre_rmse_log": u.loc[iso, "pre_rmse_log"], "excess_Mt": u.loc[iso, "excess_t"] / MT,
                   "cf_Mt": u.loc[iso, "cf_t"] / MT, "pct": u.loc[iso, "pct"]}
            row.update({f"placebo_{d}": pl.loc[iso, d] for d in pl.columns})
            row.update({"max_abs_placebo": max_pl, "exceeds_placebo": bool(abs(u.loc[iso, "pct"]) > max_pl),
                        "R0_excess_S1_Mt": u0.loc[iso, "excess_total_t_S1"] / MT, "R0_pct_S1": u0.loc[iso, "pct_S1"],
                        "R0_excess_S2_Mt": u0.loc[iso, "excess_total_t_S2"] / MT, "R0_pct_S2": u0.loc[iso, "pct_S2"],
                        "sign_agrees_S1": bool(np.sign(u.loc[iso, "pct"]) == np.sign(u0.loc[iso, "pct_S1"])),
                        "sign_agrees_S2": bool(np.sign(u.loc[iso, "pct"]) == np.sign(u0.loc[iso, "pct_S2"]))})
            rows.append(row)
        print(f"{principle}: r = {main_res['r']}, {len(treated)} treated, {len(controls)} controls "
              f"({time.perf_counter() - t0:.1f} s)")

    files = [TABLES / f"xu_gsc{suffix}.csv", C.CHECKS / f"xu_gsc_cv{suffix}.csv"]
    pd.DataFrame(rows).to_csv(files[0], index=False)
    pd.DataFrame(cv_rows).to_csv(files[1], index=False)
    if main_grid:
        files.append(C.CHECKS / "xu_gsc_validation.csv")
        pd.DataFrame(val_rows).to_csv(files[2], index=False)
    for f in files:
        print(f"{rel(f)} written")
    print(f"Run time {time.perf_counter() - t_all:.1f} s")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rmax", type=int, default=5,
                    help="largest number of factors in the grid (5: main results; 8: sensitivity)")
    main(ap.parse_args().rmax)
