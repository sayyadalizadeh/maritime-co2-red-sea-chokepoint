"""RQ3: associations of economy-level excess with exposure and group membership (RS-D18).

Sample: non-control economies of each principle's main panel (R0).
Outcome: window excess as % of the counterfactual, S1 and S2.
Regressors: departure x_v, RSL, CPA; residence e_res, HQ, RSL, CPA; plus an intercept.
Estimation: weighted least squares, weights = the window counterfactual of the same
specification; HC3 standard errors computed with numpy:
    V = (X'WX)^-1 X'W diag(e_i^2 / (1 - h_i)^2) W X (X'WX)^-1,
    h_i = w_i x_i' (X'WX)^-1 x_i.
Variants: weighted (main); unweighted; weighted without economies whose window
counterfactual is below 1 Mt. The results are associations, not causal effects.

Outputs
- outputs/tables/rq3_coefficients.csv
- outputs/tables/rq3_decomposition.csv
- outputs/checks/rq3_checks.csv
"""

import time

import numpy as np
import pandas as pd

import config as C
from common import exact_check, numeric_check, rel, write_checks

TABLES = C.OUTPUTS / "tables"
MT = 1e6
REGRESSORS = {"departure": ["x_v", "rsl", "cpa"], "residence": ["e_res", "hq", "rsl", "cpa"]}
EXPOSURE = {"departure": "x_v", "residence": "e_res"}
GROUPS = ["rsl", "cpa", "hq", "eea"]

REF = {  # principle, spec: (n, R2, {term: (coef, se)})
    ("departure", "S1"): (88, "0.370", {"const": ("3.490", "6.832"), "x_v": ("24.954", "28.320"),
                                        "rsl": ("-54.876", "25.074"), "cpa": ("-4.031", "10.231")}),
    ("departure", "S2"): (None, "0.375", {"x_v": ("38.472", "39.907"), "rsl": ("-56.923", "29.508"),
                                          "cpa": ("11.685", "7.928")}),
    ("residence", "S1"): (96, "0.090", {"e_res": ("-46.626", "83.762"), "hq": ("1.131", "4.503"),
                                        "rsl": ("-2.582", "5.593"), "cpa": ("49.735", "44.853")}),
    ("residence", "S2"): (None, "0.210", {"e_res": ("114.685", "60.317"), "hq": ("3.251", "3.743")}),
}


def wls_hc3(y, X, w):
    """WLS coefficients, HC3 standard errors and weighted R-squared."""
    XtW = X.T * w
    A_inv = np.linalg.inv(XtW @ X)
    beta = A_inv @ (XtW @ y)
    e = y - X @ beta
    h = w * np.einsum("ij,jk,ik->i", X, A_inv, X)
    with np.errstate(divide="ignore", invalid="ignore"):
        omega = e ** 2 / (1 - h) ** 2
    meat = (X.T * (w ** 2 * omega)) @ X
    V = A_inv @ meat @ A_inv
    ybar = np.sum(w * y) / np.sum(w)
    r2 = 1 - np.sum(w * e ** 2) / np.sum(w * (y - ybar) ** 2)
    return beta, np.sqrt(np.diag(V)), r2, h


def main():
    t0 = time.perf_counter()
    ex = pd.read_csv(C.INTERIM / "exposure.csv").set_index("iso3")
    coef_rows, dec_rows, checks = [], [], []

    for principle in ("departure", "residence"):
        u = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv")
        u = u[~u["control"]].copy()
        u[EXPOSURE[principle]] = u["iso3"].map(ex[EXPOSURE[principle]])
        u["cf_S1"], u["cf_S2"] = u["cf_total_t"], u["cf_total_t_S2"]
        checks.append(exact_check(f"{principle}_n", f"{principle}: non-control economies",
                                  REF[(principle, "S1")][0], len(u)))
        regs = REGRESSORS[principle]

        # ---- regressions ---------------------------------------------------
        for spec in ("S1", "S2"):
            for variant in ("weighted", "unweighted", "weighted_cf_ge_1Mt"):
                d = u if variant != "weighted_cf_ge_1Mt" else u[u[f"cf_{spec}"] >= MT]
                X = np.column_stack([np.ones(len(d))] + [d[r].astype(float).to_numpy() for r in regs])
                y = d[f"pct_{spec}"].to_numpy()
                w = np.ones(len(d)) if variant == "unweighted" else d[f"cf_{spec}"].to_numpy() / MT
                beta, se, r2, h = wls_hc3(y, X, w)
                for term, b, s in zip(["const"] + regs, beta, se):
                    coef_rows.append({"principle": principle, "spec": spec, "variant": variant, "term": term,
                                      "coef": b, "se_hc3": s, "ci95_lo": b - 1.96 * s, "ci95_hi": b + 1.96 * s,
                                      "r2": r2, "n": len(d), "max_leverage": float(h.max()),
                                      "n_group_members": int(d[term].sum()) if term in GROUPS else np.nan})
                if variant == "weighted":
                    n_ref, r2_ref, terms = REF[(principle, spec)]
                    d_ = f"RQ3 {principle} {spec} weighted"
                    checks.append(numeric_check(f"{principle}_{spec}_r2", f"{d_}: R2", r2_ref, r2, 3, tol=0.002))
                    for term, (cb, cs) in terms.items():
                        i = (["const"] + regs).index(term)
                        checks.append(numeric_check(f"{principle}_{spec}_{term}_coef", f"{d_}: {term} coefficient",
                                                    cb, beta[i], 3, tol=0.01))
                        checks.append(numeric_check(f"{principle}_{spec}_{term}_se", f"{d_}: {term} HC3 SE",
                                                    cs, se[i], 3, tol=0.01))

        # ---- decomposition ---------------------------------------------------
        u["other"] = ~u[GROUPS].any(axis=1)
        for g in GROUPS + ["other"]:
            s = u[u[g]]
            dec_rows.append({"principle": principle, "block": "group", "category": g.upper() if g != "other" else "other",
                             "n": len(s), "excess_S1_Mt": s["excess_total_t_S1"].sum() / MT,
                             "excess_S2_Mt": s["excess_total_t_S2"].sum() / MT, "members": " ".join(sorted(s["iso3"])),
                             "note": "economies in several groups are counted in each" if g != "other" else
                             "economies in none of RSL, CPA, HQ, EEA"})
        col = EXPOSURE[principle]
        q1, q2 = u[col].quantile(1 / 3), u[col].quantile(2 / 3)
        tercile = np.where(u[col] <= q1, "T1 (lowest)", np.where(u[col] <= q2, "T2", "T3 (highest)"))
        for t in ("T1 (lowest)", "T2", "T3 (highest)"):
            s = u[tercile == t]
            dec_rows.append({"principle": principle, "block": f"tercile of {col}", "category": t, "n": len(s),
                             "excess_S1_Mt": s["excess_total_t_S1"].sum() / MT,
                             "excess_S2_Mt": s["excess_total_t_S2"].sum() / MT,
                             "members": " ".join(sorted(s["iso3"])),
                             "note": f"cut-offs over non-control economies: {q1:.4f}, {q2:.4f}"})
        dec_rows.append({"principle": principle, "block": "all", "category": "all non-control", "n": len(u),
                         "excess_S1_Mt": u["excess_total_t_S1"].sum() / MT,
                         "excess_S2_Mt": u["excess_total_t_S2"].sum() / MT})
        for spec in ("S1", "S2"):
            e = u[f"excess_total_t_{spec}"]
            rob = u["robust"]
            for sign, name in ((1, "gains"), (-1, "losses")):
                part = e[(np.sign(e) == sign)]
                part_rob = e[(np.sign(e) == sign) & rob]
                dec_rows.append({"principle": principle, "block": f"robust share of gross {name}", "category": spec,
                                 "n": int(((np.sign(e) == sign) & rob).sum()),
                                 f"excess_{spec}_Mt": part_rob.sum() / MT,
                                 "gross_Mt": part.sum() / MT, "share_robust": part_rob.sum() / part.sum(),
                                 "note": f"n = robust economies with {name} in {spec}"})

    pd.DataFrame(coef_rows).to_csv(TABLES / "rq3_coefficients.csv", index=False)
    pd.DataFrame(dec_rows).to_csv(TABLES / "rq3_decomposition.csv", index=False)
    print(f"{rel(TABLES / 'rq3_coefficients.csv')}: {len(coef_rows)} rows")
    print(f"{rel(TABLES / 'rq3_decomposition.csv')}: {len(dec_rows)} rows")
    write_checks(checks, C.CHECKS / "rq3_checks.csv")
    print(f"Run time {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
