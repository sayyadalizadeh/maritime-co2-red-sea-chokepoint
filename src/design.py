"""Design matrix of the RS-D15 model and estimators built on it.

Imported by 22_pretrend.py and 24_revision_variants.py. The columns are those of
09_imputation.fit_impute, in the same order and with the same normalisation:
- unit x calendar-month effects;
- month effects, months of 2019 dropped (one per calendar month);
- the Panama term P * R, when requested and non-zero on untreated observations;
- S2 only: unit-specific linear trends (year - 2019) + (month - 1) / 12, first unit dropped.

Functions
- fe_design: the sparse design for a prepared table;
- wls_fwl: weighted least squares of y on [Z, W] by partialling out Z (Frisch-Waugh-Lovell),
  returning the coefficients on W, the partialled-out W and the residuals;
- ppml: Poisson pseudo-maximum likelihood by iteratively reweighted least squares.
"""

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu

WEIGHT_END = "2023-11"


def prepare(df, shock, drop=(), last=None):
    """Rows kept by fit_impute, sorted by unit and period, with boolean untreated / treated arrays."""
    d = df[~df["period"].isin(list(drop))]
    if last is not None:
        d = d[d["period"] <= last]
    d = d.sort_values(["unit", "period"]).reset_index(drop=True)
    post = d["period"] >= shock
    control = d["control"].astype(bool)
    untreated = (~post | control).to_numpy()
    treated = (post & ~control).to_numpy()
    return d, untreated, treated


def unit_weights(d):
    """RS-D15 weights: the unit's mean per-day value over the periods <= 2023-11 in the data."""
    return d[d["period"] <= WEIGHT_END].groupby("unit")["per_day"].mean()


def fe_design(d, untreated, spec="S1", panama=False):
    """Sparse design (n x k) and column names, as in 09_imputation.fit_impute."""
    units = sorted(d["unit"].unique())
    u_idx = d["unit"].map({u: i for i, u in enumerate(units)}).to_numpy()
    year = d["period"].str[:4].astype(int).to_numpy()
    month = d["period"].str[5:7].astype(int).to_numpy()
    n = len(d)
    rows, cols, vals, names = [], [], [], []
    uc = u_idx * 12 + (month - 1)
    uc_codes = {c: i for i, c in enumerate(sorted(set(uc)))}
    rows.append(np.arange(n)); cols.append(np.array([uc_codes[c] for c in uc])); vals.append(np.ones(n))
    names += [f"a[{units[c // 12]},{c % 12 + 1}]" for c in sorted(uc_codes)]
    k = len(uc_codes)
    per = d["period"].to_numpy()
    m_periods = sorted(p for p in set(per) if p >= "2020-01")
    m_codes = {p: k + i for i, p in enumerate(m_periods)}
    has_m = np.array([p in m_codes for p in per])
    rows.append(np.arange(n)[has_m]); cols.append(np.array([m_codes[p] for p in per[has_m]], dtype=int))
    vals.append(np.ones(has_m.sum()))
    names += [f"b[{p}]" for p in m_periods]
    k += len(m_periods)
    if panama:
        pr = (d["P"] * d["R"]).to_numpy(dtype=float)
        if np.any(pr[untreated] != 0):
            nz = pr != 0
            rows.append(np.arange(n)[nz]); cols.append(np.full(nz.sum(), k)); vals.append(pr[nz])
            names.append("gamma[P*R]")
            k += 1
    if spec == "S2":
        t = (year - 2019) + (month - 1) / 12
        keep = u_idx > 0
        rows.append(np.arange(n)[keep]); cols.append(k + u_idx[keep] - 1); vals.append(t[keep])
        names += [f"c[{u}]" for u in units[1:]]
        k += len(units) - 1
    X = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, k))
    return X, names


def wls_fwl(Z, W, y, w):
    """WLS of y on [Z, W] with weights w; Z (sparse) partialled out.

    Returns (gamma, W_tilde, resid, fitted_Z_part):
    gamma: coefficients on the columns of W; W_tilde: W minus its weighted projection on Z;
    resid: residuals of the full regression; beta_Z: coefficients on Z.
    """
    A = (Z.T @ sp.diags(w) @ Z).tocsc()
    lu = splu(A)
    W = np.asarray(W, dtype=float)
    if W.ndim == 1:
        W = W[:, None]
    def proj(v):
        wv = w[:, None] * v if v.ndim == 2 else w * v
        return Z @ lu.solve(np.asarray(Z.T @ wv))

    W_t = W - proj(W)
    y_t = y - proj(y)
    WtW = W_t.T @ (w[:, None] * W_t)
    gamma = np.linalg.solve(WtW, W_t.T @ (w * y_t))
    resid = y_t - W_t @ gamma
    beta_z = lu.solve(Z.T @ (w * (y - W @ gamma)))
    return gamma, W_t, resid, beta_z


def ppml(X, y, tol=1e-12, max_iter=200):
    """Poisson pseudo-maximum likelihood of y (> 0) on X by iteratively reweighted least squares.

    Start: mu = y. Iteration: z = eta + (y - mu) / mu, weights mu, WLS of z on X (sparse normal
    equations). Stops when the relative change of the Poisson deviance is below tol.
    Returns (beta, n_iter, deviance, max |score| relative to sum(y)).
    """
    y = np.asarray(y, dtype=float)
    mu = y.copy()
    eta = np.log(mu)
    dev_old = np.inf
    for it in range(1, max_iter + 1):
        z = eta + (y - mu) / mu
        A = (X.T @ sp.diags(mu) @ X).tocsc()
        beta = splu(A).solve(X.T @ (mu * z))
        eta = X @ beta
        mu = np.exp(eta)
        dev = 2 * np.sum(y * np.log(y / mu) - (y - mu))
        if np.isfinite(dev_old) and abs(dev_old - dev) <= tol * max(abs(dev), 1e-300):
            break
        dev_old = dev
    score = X.T @ (y - mu)
    return beta, it, dev, float(np.max(np.abs(score)) / np.sum(y))
