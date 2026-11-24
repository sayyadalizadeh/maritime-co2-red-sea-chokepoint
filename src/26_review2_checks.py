"""Supplementary analyses after the second pre-submission review (RS-D42).

No existing output is rewritten. Every result goes to a new file.

(a) Gross shifts without influential economies (no re-estimation).
    Series TER_INT, RES_TOTAL (main estimates, rsd4_*_units.csv) and TER_TOT (like_for_like_units.csv);
    S1 and S2; exclusion sets none, EGY, SAU, MYS, EGY+SAU, EGY+SAU+MYS. An excluded economy is
    removed from the actual sums, the placebo sums and the counterfactual denominators. Placebos:
    the RS-D31 equal-window runs (rolling_placebo_runs.csv) of the same specification; TER_TOT has
    no rolling runs and is reported without a placebo comparison. Computed as RS-D32
    (23_rolling_placebo.py): gains (losses) = sum of positive (negative) unit excess over the
    non-control units, as % of their summed counterfactual. Rank of the actual value among the
    actual and placebo values, largest first (losses: largest absolute value first).
(b) Benjamini-Yekutieli at q = 0.10 on the RS-D31 unit p-values (p_u; a unit whose S1 and S2
    signs differ enters with p = 1), beside Benjamini-Hochberg; RES_TOTAL, TER_INT, RES_INT.
(c) Family-wise calibration. For each series, specification and equal-window placebo date d:
    M_d = max over the non-control units of |z0_ud|, z0_ud = placebo %_ud / sigma_u(-d), sigma_u(-d)
    the root mean square of the unit's placebo % without date d (RS-D31). Unit family-wise
    p-value p_s = (1 + #{d: M_d >= |z_u|}) / (1 + number of dates), z_u = main % / sigma_u (all
    dates); combined = max(p_S1, p_S2), set to 1 when the S1 and S2 signs differ; candidate when
    the combined p <= 0.10. The smallest attainable value is 1 / (1 + number of dates).
(d) R17: GIB, PAN, BHS and MHL removed from the control pool of each main principle where they
    are members (they become treated units; panels unchanged). RS-D15 S1 and S2 with the Panama
    term, RS-D16 placebos and robust rule; the unit table is built as in 10_rsd4_economies.py.
(e) RQ3 (residence, weighted S1 and S2, as 15_rq3_associations.py) with HQ extended by HKG, and
    by HKG and JPN; R0 sample and control pools unchanged.
(f) W6: world by ship type, RS-D2 main comparison (ten cargo types treated, eight non-cargo types
    as controls), estimation sample 2021-07..2025-10, otherwise as the main run. One placebo date
    (2022-12, data to 2023-11), S1 and S2. Aggregate pre-trend test of RS-D30 (a) for container
    ships (CONTAINER against the eight non-transit types) on the same sample. Non-inferential.
    Normalisation: with data from 2021-07 the month effects of the first twelve sample months
    (2021-07..2022-06, one per calendar month) are dropped, as the 2019 months are dropped in
    09_imputation.fit_impute; fitted values do not depend on this choice (checked against a dense
    minimum-norm least-squares solve). With first_b = 2020-01 the design equals design.fe_design.

Outputs
- outputs/tables/review2_gross_exclusions.csv, review2_multiple_testing.csv,
  review2_multiple_testing_summary.csv, review2_familywise_dates.csv, review2_r17_economies.csv,
  review2_r17_summary.csv, review2_rq3_hq.csv, review2_w6.csv
- outputs/manuscript_tables/supplementary/stab_rev2_*.csv (same cells, full precision) and
  outputs/manuscript_tables/table_notes_review2.md
- outputs/checks/review2_checks.csv
"""

import importlib
import time

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy import stats
from scipy.sparse.linalg import spsolve

import config as C
import design as D
from common import rel, write_checks

imp = importlib.import_module("09_imputation")
m10 = importlib.import_module("10_rsd4_economies")
m11 = importlib.import_module("11_rsd2_world")
m12 = importlib.import_module("12_robustness_economies")
m15 = importlib.import_module("15_rq3_associations")

TABLES = C.OUTPUTS / "tables"
MANU = C.OUTPUTS / "manuscript_tables"
SUPP = MANU / "supplementary"
MT = 1e6
Q = 0.10
Z95 = 1.959963984540054
EXCLUSION_SETS = [(), ("EGY",), ("SAU",), ("MYS",), ("EGY", "SAU"), ("EGY", "SAU", "MYS")]
HUBS = ("GIB", "PAN", "BHS", "MHL")
HQ_EXTENSIONS = {"RS-D3 (main)": (), "RS-D3 + HKG": ("HKG",), "RS-D3 + HKG + JPN": ("HKG", "JPN")}
W6_START = "2021-07"
W6_FIRST_B = "2022-07"
W6_PLACEBO, W6_PLACEBO_END = "2022-12", "2023-11"
W6_LABEL = "W6 (non-inferential)"
CHECKS = []


def chk(name, definition, expected, obtained, ok, diff=""):
    CHECKS.append({"check": name, "definition": definition, "expected": str(expected), "obtained": str(obtained),
                   "abs_diff": diff, "pass": bool(ok)})


def maxdiff(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape:
        return np.inf
    same_nan = np.array_equal(np.isnan(a), np.isnan(b))
    d = np.abs(a - b)
    return float(np.nanmax(d)) if same_nan and d.size and not np.all(np.isnan(d)) else (0.0 if same_nan else np.inf)


def reldiff(a, b):
    """max |a - b| / max(1, |b|), NaN positions required to match."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return maxdiff(a / np.maximum(1.0, np.abs(b)), b / np.maximum(1.0, np.abs(b)))


def read_runs():
    return pd.read_csv(TABLES / "rolling_placebo_runs.csv", float_precision="round_trip")


def series_units(series):
    if series == "RES_TOTAL":
        return pd.read_csv(TABLES / "rsd4_residence_units.csv")
    if series == "TER_INT":
        return pd.read_csv(TABLES / "rsd4_departure_units.csv")
    u = pd.read_csv(TABLES / "like_for_like_units.csv")
    return u[u["series"] == series].drop(columns="series").reset_index(drop=True)


# ---------------------------------------------------------------------------
# (a) gross shifts without influential economies
# ---------------------------------------------------------------------------
def gross_exclusions(runs):
    rows = []
    for series in ("TER_INT", "RES_TOTAL", "TER_TOT"):
        u = series_units(series).set_index("iso3")
        nc_all = u[~u["control"].astype(bool)]
        ur = runs[(runs["analysis"] == series) & (runs["level"] == "unit")]
        has_placebo = len(ur) > 0
        for spec in imp.SPECS:
            cfcol = "cf_total_t" if spec == "S1" else "cf_total_t_S2"
            for excl in EXCLUSION_SETS:
                nc = nc_all[~nc_all.index.isin(excl)]
                cf_act = nc[cfcol].sum()
                e = nc[f"excess_total_t_{spec}"]
                act = {"gains": 100 * e[e > 0].sum() / cf_act, "losses": 100 * e[e < 0].sum() / cf_act}
                row = {"series": series, "spec": spec, "exclusion": "+".join(excl) or "none",
                       "excluded_noncontrol": " ".join(c for c in excl if c in nc_all.index),
                       "excluded_control_or_absent": " ".join(c for c in excl if c not in nc_all.index),
                       "n_units": len(nc), "cf_Mt": cf_act / MT,
                       "gains_pct": act["gains"], "losses_pct": act["losses"],
                       "gains_Mt": e[e > 0].sum() / MT, "losses_Mt": e[e < 0].sum() / MT, "net_Mt": e.sum() / MT}
                if has_placebo:
                    s = ur[(ur["spec"] == spec) & ur["unit"].isin(nc.index)]
                    pg = []
                    for p, g in s.groupby("placebo_date"):
                        cf = g["cf_t"].sum()
                        pg.append({"gains_pct": 100 * g.loc[g["excess_t"] > 0, "excess_t"].sum() / cf,
                                   "losses_pct": 100 * g.loc[g["excess_t"] < 0, "excess_t"].sum() / cf})
                    pg = pd.DataFrame(pg)
                    n_units_pl = s.groupby("placebo_date")["unit"].nunique()
                    if not (n_units_pl == len(nc)).all():
                        raise RuntimeError(f"{series} {spec} {excl}: placebo units differ from the actual units")
                    rank_g = 1 + int((pg["gains_pct"] > act["gains"]).sum())
                    rank_l = 1 + int((pg["losses_pct"] < act["losses"]).sum())
                    row.update({"n_placebo_dates": len(pg), "max_placebo_gains_pct": pg["gains_pct"].max(),
                                "max_abs_placebo_losses_pct": pg["losses_pct"].abs().max(),
                                "rank_gains": rank_g, "rank_losses": rank_l, "n_values": len(pg) + 1,
                                "rank_gains_of_n": f"{rank_g} of {len(pg) + 1}",
                                "rank_losses_of_n": f"{rank_l} of {len(pg) + 1}", "placebo_note": ""})
                else:
                    row.update({"n_placebo_dates": 0, "max_placebo_gains_pct": np.nan,
                                "max_abs_placebo_losses_pct": np.nan, "rank_gains": pd.NA, "rank_losses": pd.NA,
                                "n_values": pd.NA, "rank_gains_of_n": "", "rank_losses_of_n": "",
                                "placebo_note": "no equal-window placebo runs exist for this series (RS-D31 covers "
                                                "RES_TOTAL, TER_INT and RES_INT); no placebo comparison"})
                rows.append(row)
    out = pd.DataFrame(rows)
    for c in ("rank_gains", "rank_losses", "n_values"):
        out[c] = out[c].astype("Int64")

    # check 1: exclusion set "none", S1, reproduces RS-D32
    ref = pd.read_csv(TABLES / "rolling_placebo_gross.csv", float_precision="round_trip")
    for series in ("RES_TOTAL", "TER_INT"):
        r = ref[(ref["series"] == series) & (ref["row"] == "actual")].iloc[0]
        o = out[(out["series"] == series) & (out["spec"] == "S1") & (out["exclusion"] == "none")].iloc[0]
        cols = ["gains_pct", "losses_pct", "gains_Mt", "losses_Mt", "cf_Mt", "max_placebo_gains_pct",
                "max_abs_placebo_losses_pct"]
        d = maxdiff([o[c] for c in cols], [r[c] for c in cols])
        same_rank = o["rank_gains_of_n"] == r["rank_gains_of_n"] and o["rank_losses_of_n"] == r["rank_losses_of_n"]
        chk(f"review2_gross_none_{series}", f"(a) {series} S1, exclusion set none: gains, losses (% and Mt), "
            "counterfactual, placebo maxima and ranks equal rolling_placebo_gross.csv (RS-D32), max |diff| = 0",
            "identical", f"max |diff| {d:.3g}; ranks {o['rank_gains_of_n']}, {o['rank_losses_of_n']}",
            d == 0.0 and same_rank, f"{d:.3g}")
    return out


# ---------------------------------------------------------------------------
# (b), (c) multiple testing
# ---------------------------------------------------------------------------
def by_adjusted(p):
    """Benjamini-Yekutieli adjusted p-values: min over k >= i of p_(k) m c(m) / k, capped at 1."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    cm = np.sum(1.0 / np.arange(1, m + 1))
    order = np.argsort(p, kind="mergesort")
    scaled = p[order] * m * cm / np.arange(1, m + 1)
    adj_sorted = np.minimum(np.minimum.accumulate(scaled[::-1])[::-1], 1.0)
    adj = np.empty(m)
    adj[order] = adj_sorted
    return adj, cm


def by_stepup(p, q):
    """Benjamini-Yekutieli step-up: the largest k with p_(k) <= k q / (m c(m))."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    cm = np.sum(1.0 / np.arange(1, m + 1))
    order = np.argsort(p, kind="stable")
    ok = p[order] <= q * np.arange(1, m + 1) / (m * cm)
    k = int(np.max(np.nonzero(ok)[0]) + 1) if ok.any() else 0
    sel = np.zeros(m, dtype=bool)
    sel[order[:k]] = True
    return sel


def multiple_testing(runs):
    m23 = importlib.import_module("23_rolling_placebo")
    units = pd.read_csv(TABLES / "rolling_placebo_units.csv", float_precision="round_trip")
    bh_ref = pd.read_csv(TABLES / "rolling_placebo_bh.csv", keep_default_na=False)
    rows, summ, date_rows = [], [], []
    all_fw = []
    for series in ("RES_TOTAL", "TER_INT", "RES_INT"):
        u = units[units["series"] == series].set_index("iso3")
        ur = runs[(runs["analysis"] == series) & (runs["level"] == "unit")]
        dates = sorted(ur["placebo_date"].unique())
        n_d = len(dates)
        fw, z_main, maxz = {}, {}, 0.0
        for spec in imp.SPECS:
            P = ur[ur["spec"] == spec].pivot(index="unit", columns="placebo_date", values="pct").reindex(u.index)[dates]
            A = P.to_numpy(dtype=float)
            sigma = np.sqrt(np.mean(A ** 2, axis=1))
            z = u[f"pct_{spec}"].to_numpy(dtype=float) / sigma
            maxz = max(maxz, maxdiff(sigma, u[f"sigma_{spec}"]), maxdiff(z, u[f"z_{spec}"]))
            sq = A ** 2
            loo = np.sqrt((sq.sum(axis=1, keepdims=True) - sq) / (n_d - 1))
            z0 = np.abs(A / loo)
            M = z0.max(axis=0)
            arg = z0.argmax(axis=0)
            for j, d in enumerate(dates):
                date_rows.append({"series": series, "spec": spec, "placebo_date": d, "M_d": M[j],
                                  "unit_at_max": u.index[arg[j]], "n_units": len(u)})
            fw[spec] = (1 + (M[None, :] >= np.abs(z)[:, None]).sum(axis=1)) / (1 + n_d)
            z_main[spec] = z
        sign_agree = u["sign_agree"].astype(bool).to_numpy()
        fw_comb = np.where(sign_agree, np.maximum(fw["S1"], fw["S2"]), 1.0)
        fw_cand = fw_comb <= Q
        p_in = u["p_bh_input"].to_numpy(dtype=float)
        # BH recomputed with the RS-D31 functions
        bh_sel = m23.bh_stepup(p_in, Q)
        _, bh_adj = m23.bh_adjusted(p_in, Q)
        by_adj, cm = by_adjusted(p_in)
        by_sel = by_adj <= Q
        by_sel2 = by_stepup(p_in, Q)
        all_fw.append(np.concatenate([fw["S1"], fw["S2"], fw_comb]))

        chk(f"review2_sigma_z_{series}", f"(c) {series}: sigma_u and z_u recomputed from rolling_placebo_runs.csv "
            "equal rolling_placebo_units.csv (max |diff| <= 1e-12)", "agree", f"{maxz:.3g}", maxz <= 1e-12, f"{maxz:.3g}")
        ref_list = bh_ref.loc[bh_ref["series"] == series, "candidates"].iloc[0]
        got_list = " ".join(sorted(u.index[bh_sel]))
        same_flags = bool((bh_sel == u["bh_candidate"].astype(bool).to_numpy()).all())
        dadj = maxdiff(bh_adj, u["bh_adjusted_p"])
        chk(f"review2_bh_{series}", f"(b) {series}: Benjamini-Hochberg (q = 0.10) recomputed from p_u reproduces the "
            "RS-D31 candidate list (rolling_placebo_bh.csv), the unit flags and the adjusted p-values", ref_list,
            got_list, got_list == ref_list and same_flags and dadj <= 1e-15, f"{dadj:.3g}")
        chk(f"review2_by_two_ways_{series}", f"(b) {series}: Benjamini-Yekutieli step-up list equals the list from "
            "BY-adjusted p-values <= 0.10", "identical", f"{int(by_sel2.sum())} vs {int(by_sel.sum())}",
            bool((by_sel == by_sel2).all()))
        by_set, bh_set = set(u.index[by_sel]), set(u.index[bh_sel])
        chk(f"review2_by_subset_{series}", f"(b) {series}: BY list is a subset of the BH list",
            "subset", f"BY {len(by_set)} of BH {len(bh_set)}", by_set <= bh_set)

        for i, iso in enumerate(u.index):
            r = u.loc[iso]
            rows.append({"series": series, "iso3": iso, "rsl": r["rsl"], "cpa": r["cpa"], "hq": r["hq"],
                         "eea": r["eea"], "pct_S1": r["pct_S1"], "pct_S2": r["pct_S2"],
                         "sign_agree": bool(sign_agree[i]), "p_S1": r["p_S1"], "p_S2": r["p_S2"], "p_u": r["p_u"],
                         "p_input": p_in[i], "bh_adjusted_p": bh_adj[i], "bh_candidate": bool(bh_sel[i]),
                         "by_adjusted_p": by_adj[i], "by_candidate": bool(by_sel[i]),
                         "z_S1": z_main["S1"][i], "z_S2": z_main["S2"][i],
                         "fw_p_S1": fw["S1"][i], "fw_p_S2": fw["S2"][i], "fw_p": fw_comb[i],
                         "fw_candidate": bool(fw_cand[i]), "n_dates": n_d, "fw_min_attainable": 1 / (1 + n_d)})
        fw_set = sorted(u.index[fw_cand])
        summ.append({"series": series, "m_noncontrol": len(u), "n_sign_disagree": int((~sign_agree).sum()),
                     "q": Q, "n_bh": len(bh_set), "bh_candidates": " ".join(sorted(bh_set)),
                     "n_by": len(by_set), "by_candidates": " ".join(sorted(by_set)), "by_c_m": cm,
                     "n_dates": n_d, "placebo_dates": f"{dates[0]}..{dates[-1]}", "fw_min_attainable": 1 / (1 + n_d),
                     "n_fw": len(fw_set), "fw_candidates": " ".join(fw_set),
                     "n_fw_at_min": int((fw_comb == 1 / (1 + n_d)).sum()),
                     "min_fw_p": float(fw_comb.min())})
        print(f"{series}: BH {len(bh_set)} [{' '.join(sorted(bh_set))}]; BY {len(by_set)} [{' '.join(sorted(by_set))}]; "
              f"family-wise <= {Q} {len(fw_set)} [{' '.join(fw_set)}]; min attainable {1 / (1 + n_d):.4f}")
    allfw = np.concatenate(all_fw)
    chk("review2_fw_in_range", "(c) family-wise p-values (S1, S2, combined; all series) lie in (0, 1]", "(0, 1]",
        f"{allfw.min():.4g}-{allfw.max():.4g}", bool((allfw > 0).all() and (allfw <= 1).all()))
    return pd.DataFrame(rows), pd.DataFrame(summ), pd.DataFrame(date_rows)


# ---------------------------------------------------------------------------
# (d) R17
# ---------------------------------------------------------------------------
def units_table(name, cfg, df, ex):
    """Main fits, RS-D16 placebos and the unit table, as in 10_rsd4_economies.run_principle."""
    main, diags, weights = {}, {}, None
    for spec in imp.SPECS:
        tr, dg, wts = imp.fit_impute(df, shock=C.SHOCK_START, drop=cfg["drop"], last=C.MAIN_END, spec=spec,
                                     panama=True)
        main[spec], diags[spec], weights = tr, dg, wts
    unit_pl, agg_pl = imp.placebo_runs(df, last_pre=cfg["last_pre"], drop=cfg["drop"], panama=True)
    econ = sorted(df["unit"].unique())
    u = pd.DataFrame({"iso3": econ})
    u = u.merge(ex[["iso3"] + m10.GROUPS], on="iso3", how="left")
    u["control"] = u["iso3"].map(df.drop_duplicates("unit").set_index("unit")["control"])
    u["weight"] = u["iso3"].map(weights)
    g1, by_year = imp.summarise_unit(main["S1"])
    g2, _ = imp.summarise_unit(main["S2"])
    u["cf_total_t"] = u["iso3"].map(g1["cf_t"])
    u["cf_total_t_S2"] = u["iso3"].map(g2["cf_t"])
    u["excess_total_t_S1"] = u["iso3"].map(g1["excess_t"])
    u["excess_total_t_S2"] = u["iso3"].map(g2["excess_t"])
    u["pct_S1"] = u["iso3"].map(g1["pct"])
    u["pct_S2"] = u["iso3"].map(g2["pct"])
    for y in ("2023", "2024", "2025"):
        u[f"excess_{y}_S1"] = u["iso3"].map(by_year[y]) if y in by_year else np.nan
    pl = unit_pl.reindex(u["iso3"])
    for c in unit_pl.columns:
        u[c] = pl[c].values
    u["max_abs_placebo"] = pl.abs().max(axis=1).values
    u["robust"] = imp.robust(u["pct_S1"], u["pct_S2"], u["max_abs_placebo"]) & ~u["control"]
    u.loc[u["control"], "robust"] = False
    return u, main, diags, agg_pl


def r17(ex, pt, R):
    e = ex.set_index("iso3")
    unit_frames, summ = [], []
    for principle, cfg in m10.PRINCIPLES.items():
        old = e[cfg["control"]].astype(bool)
        members = [c for c in HUBS if c in old.index and old[c]]
        new = old.copy()
        new[list(members)] = False
        old_set, new_set = set(old.index[old]), set(new.index[new])
        chk(f"review2_r17_{principle}_pool", f"(d) {principle}: R17 pool equals the R0 pool minus the removed members "
            f"({' '.join(members) or 'none'})", f"{len(old_set) - len(members)}",
            f"{len(new_set)}", new_set == old_set - set(members), "")
        df = m12.make_df(principle, ex, pt, R, control=new)
        u, main, diags, agg = units_table(principle, cfg, df, ex)
        ref_units = pd.read_csv(TABLES / f"rsd4_{principle}_units.csv")
        if not members:
            num = [c for c in ref_units.columns if c not in ("iso3",) and ref_units[c].dtype != object]
            d = reldiff(u[num].astype(float).to_numpy(), ref_units[num].astype(float).to_numpy())
            chk(f"review2_r17_{principle}_equals_R0", f"(d) {principle}: no hub economy is a pool member, so R17 equals "
                "R0; the unit table equals rsd4 units (max |diff| / max(1, |value|) over numeric columns <= 1e-9)", "agree", f"{d:.3g}",
                d <= 1e-9 and list(u["iso3"]) == list(ref_units["iso3"]), f"{d:.3g}")
        else:
            # code check: the same routine with the R0 pool reproduces the rsd4 unit table
            u0, _, _, _ = units_table(principle, cfg, m12.make_df(principle, ex, pt, R), ex)
            num = [c for c in ref_units.columns if c not in ("iso3",) and ref_units[c].dtype != object]
            d = reldiff(u0[num].astype(float).to_numpy(), ref_units[num].astype(float).to_numpy())
            chk(f"review2_r17_{principle}_R0_reproduced", f"(d) {principle}: the R17 routine with the R0 pool "
                "reproduces rsd4 units (max |diff| / max(1, |value|) over numeric columns <= 1e-9)", "agree", f"{d:.3g}", d <= 1e-9,
                f"{d:.3g}")
        u.insert(0, "principle", principle)
        unit_frames.append(u)

        r0 = set(ref_units.loc[ref_units["robust"].astype(bool), "iso3"])
        rob = set(u.loc[u["robust"].astype(bool), "iso3"])
        nc = u[~u["control"].astype(bool)]
        e1 = nc["excess_total_t_S1"]
        r0s = pd.read_csv(TABLES / "rsd4_summary.csv").set_index(["principle", "spec"])
        chk(f"review2_r17_{principle}_placebo_runs", f"(d) {principle}: placebo runs (5 dates x S1, S2)", 10, len(agg),
            len(agg) == 10)
        for spec in imp.SPECS:
            tr = main[spec]
            tot, cf = tr["excess_t"].sum(), tr["cf_t"].sum()
            lo, hi = agg["pct"].min(), agg["pct"].max()
            summ.append({
                "variant": "R17", "principle": principle, "spec": spec,
                "hubs_considered": " ".join(HUBS), "removed_pool_members": " ".join(members),
                "hubs_not_in_pool": " ".join(c for c in HUBS if c not in members),
                "pool_size_R0": len(old_set), "pool_size": len(new_set), "pool": " ".join(sorted(new_set)),
                "n_economies": diags[spec]["n_units"], "n_control": diags[spec]["n_control_units"],
                "excess_Mt": tot / MT, "cf_Mt": cf / MT, "pct": 100 * tot / cf,
                "placebo_band_pct_min": lo, "placebo_band_pct_max": hi,
                "placebo_band_Mt_min": lo * cf / 100 / MT, "placebo_band_Mt_max": hi * cf / 100 / MT,
                "gross_gains_S1_Mt": e1[e1 > 0].sum() / MT, "gross_losses_S1_Mt": e1[e1 < 0].sum() / MT,
                "gross_gains_S1_pct": 100 * e1[e1 > 0].sum() / nc["cf_total_t"].sum(),
                "gross_losses_S1_pct": 100 * e1[e1 < 0].sum() / nc["cf_total_t"].sum(),
                "n_robust": len(rob), "robust_list": " ".join(sorted(rob)),
                "robust_list_R0": " ".join(sorted(r0)), "gained_vs_R0": " ".join(sorted(rob - r0)),
                "lost_vs_R0": " ".join(sorted(r0 - rob)),
                "excess_Mt_R0": r0s.loc[(principle, spec), "excess_Mt"], "pct_R0": r0s.loc[(principle, spec), "pct"],
                "placebo_band_pct_min_R0": r0s.loc[(principle, spec), "placebo_band_pct_min"],
                "placebo_band_pct_max_R0": r0s.loc[(principle, spec), "placebo_band_pct_max"],
                "gross_gains_S1_Mt_R0": r0s.loc[(principle, "S1"), "gross_gains_all_Mt"],
                "gross_losses_S1_Mt_R0": r0s.loc[(principle, "S1"), "gross_losses_all_Mt"]})
        print(f"R17 {principle}: removed {' '.join(members) or 'none'}; pool {len(new_set)} (R0 {len(old_set)}); "
              f"S1 {summ[-2]['excess_Mt']:+.2f} Mt, S2 {summ[-1]['excess_Mt']:+.2f} Mt; robust {len(rob)} "
              f"(gained {' '.join(sorted(rob - r0)) or '-'}; lost {' '.join(sorted(r0 - rob)) or '-'})")
    return pd.concat(unit_frames, ignore_index=True), pd.DataFrame(summ)


# ---------------------------------------------------------------------------
# (e) RQ3 with HQ extended
# ---------------------------------------------------------------------------
def rq3_hq(ex):
    e = ex.set_index("iso3")
    principle = "residence"
    u = pd.read_csv(TABLES / "rsd4_residence_units.csv")
    controls = set(u.loc[u["control"].astype(bool), "iso3"])
    u = u[~u["control"]].copy()
    u["e_res"] = u["iso3"].map(e["e_res"])
    regs = m15.REGRESSORS[principle]
    rows = []
    for version, extra in HQ_EXTENSIONS.items():
        d = u.copy()
        d["hq"] = d["hq"].astype(bool) | d["iso3"].isin(extra)
        in_ctrl = [c for c in extra if c in controls]
        for spec in imp.SPECS:
            cfcol = "cf_total_t" if spec == "S1" else "cf_total_t_S2"
            X = np.column_stack([np.ones(len(d))] + [d[r].astype(float).to_numpy() for r in regs])
            b, se, r2, _ = m15.wls_hc3(d[f"pct_{spec}"].to_numpy(), X, d[cfcol].to_numpy() / MT)
            for term, bb, ss in zip(["const"] + regs, b, se):
                rows.append({"principle": principle, "spec": spec, "hq_version": version,
                             "hq_added": " ".join(extra), "term": term, "coef": bb, "se_hc3": ss,
                             "ci95_lo": bb - 1.96 * ss, "ci95_hi": bb + 1.96 * ss, "r2": r2, "n": len(d),
                             "n_hq": int(d["hq"].sum()), "hq_members_in_sample": " ".join(sorted(d.loc[d["hq"], "iso3"])),
                             "added_in_control_pool": " ".join(in_ctrl)})
    out = pd.DataFrame(rows)
    chk("review2_rq3_added_not_controls", "(e) HKG and JPN are non-control residence economies (both enter the "
        "regression)", "none in pool", " ".join(c for c in ("HKG", "JPN") if c in controls) or "none in pool",
        not ({"HKG", "JPN"} & controls))

    # check 6: main rows reproduce Table 4 (tab_rq3.csv) and rq3_coefficients.csv
    tab = pd.read_csv(MANU / "tab_rq3.csv", keep_default_na=False, dtype=str).set_index("term")
    ref = pd.read_csv(TABLES / "rq3_coefficients.csv")
    ref = ref[(ref["principle"] == principle) & (ref["variant"] == "weighted")]
    for spec in imp.SPECS:
        m = out[(out["hq_version"] == "RS-D3 (main)") & (out["spec"] == spec)].set_index("term")
        cells = {t: f"{m.loc[t, 'coef']:.3f} ({m.loc[t, 'se_hc3']:.3f})" for t in m.index}
        cells["n"] = f"{m['n'].iloc[0]:.0f}"
        cells["r2"] = f"{m['r2'].iloc[0]:.3f}"
        want = {t: tab.loc[t, f"residence_{spec}"] for t in cells}
        bad = [t for t in cells if cells[t] != want[t]]
        rr = ref[ref["spec"] == spec].set_index("term").loc[m.index]
        d = maxdiff(np.r_[m["coef"], m["se_hc3"]], np.r_[rr["coef"], rr["se_hc3"]])
        chk(f"review2_rq3_table4_{spec}", f"(e) residence {spec}: main-HQ rows reproduce Table 4 (tab_rq3.csv cells: "
            "coefficient (SE), n, R2) and rq3_coefficients.csv (max |diff| <= 1e-9)", "identical",
            f"cells differing: {' '.join(bad) or 'none'}; max |diff| {d:.3g}", not bad and d <= 1e-9, f"{d:.3g}")
    return out


# ---------------------------------------------------------------------------
# (f) W6
# ---------------------------------------------------------------------------
def fe_design_gen(d, untreated, spec="S1", panama=False, first_b="2020-01"):
    """design.fe_design with month effects from first_b on (the months before first_b are dropped)."""
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
    m_periods = sorted(p for p in set(per) if p >= first_b)
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


def fit_gen(df, shock, last, spec, first_b, dense_check=False):
    """RS-D15 imputation (as 09_imputation.fit_impute, no Panama term) with the generalised design."""
    d, untreated, treated = D.prepare(df, shock, (), last)
    keep = untreated | treated
    d, untreated, treated = d[keep].reset_index(drop=True), untreated[keep], treated[keep]
    weights = D.unit_weights(d)
    w = d["unit"].map(weights).to_numpy()
    y = np.log(d["per_day"].to_numpy())
    X, _ = fe_design_gen(d, untreated, spec, False, first_b)
    Xu, yu, wu = X[untreated], y[untreated], w[untreated]
    A = (Xu.T @ sp.diags(wu) @ Xu).tocsc()
    beta = spsolve(A, Xu.T @ (wu * yu))
    fitted = X @ beta
    resid = yu - fitted[untreated]
    s_u = pd.Series(np.exp(resid)).groupby(d.loc[untreated, "unit"].to_numpy()).mean()
    diag = {"n_params": X.shape[1], "rel_resid": float(np.linalg.norm(A @ beta - Xu.T @ (wu * yu))
                                                       / np.linalg.norm(Xu.T @ (wu * yu)))}
    if dense_check:
        sw = np.sqrt(wu)
        bd, *_ = np.linalg.lstsq(Xu.toarray() * sw[:, None], yu * sw, rcond=None)
        diag["dense_max_abs_fitted_diff"] = float(np.max(np.abs(X.toarray() @ bd - fitted)))
        diag["dense_rank"] = int(np.linalg.matrix_rank(Xu.toarray() * sw[:, None]))
    tr = d.loc[treated, ["unit", "period", "days", "value_t", "per_day"]].copy()
    tr["cf_per_day"] = np.exp(fitted[treated]) * tr["unit"].map(s_u).to_numpy()
    tr["cf_t"] = tr["cf_per_day"] * tr["days"]
    tr["excess_t"] = (tr["per_day"] - tr["cf_per_day"]) * tr["days"]
    return tr.reset_index(drop=True), diag


def pretrend_gen(df, first_b):
    """RS-D30 (a) aggregate test (as 22_pretrend.aggregate_test, no Panama term) with the generalised design."""
    d, untreated, _ = D.prepare(df, C.SHOCK_START, (), C.MAIN_END)
    du = d[untreated].reset_index(drop=True)
    wts = D.unit_weights(du)
    Z, _ = fe_design_gen(du, np.ones(len(du), dtype=bool), "S1", False, first_b)
    w = du["unit"].map(wts).to_numpy()
    y = np.log(du["per_day"].to_numpy())
    per = [imp.add_months(C.SHOCK_START, -h) for h in range(1, 13)]
    treated_unit = ~du["control"].astype(bool).to_numpy()
    W = np.column_stack([(treated_unit & (du["period"].to_numpy() == p)).astype(float) for p in per])
    gamma, W_t, e, _ = D.wls_fwl(Z, W, y, w)
    units = du["unit"].to_numpy()
    G = len(np.unique(units))
    scores = pd.DataFrame(W_t * (w * e)[:, None]).groupby(units).sum().to_numpy()
    bread = np.linalg.inv(W_t.T @ (w[:, None] * W_t))
    V = G / (G - 1) * bread @ (scores.T @ scores) @ bread
    rank = int(np.linalg.matrix_rank(V))
    Vinv = np.linalg.inv(V) if rank == len(per) else np.linalg.pinv(V)
    wald = float(gamma @ Vinv @ gamma)
    se = np.sqrt(np.diag(V))
    F = wald / rank
    joint = {"n_clusters": G, "n_obs": len(du), "n_terms": len(per), "rank_V": rank, "wald_chi2": wald, "df": rank,
             "p_chi2": float(stats.chi2.sf(wald, rank)), "F": F, "df1": rank, "df2": G - 1,
             "p_F": float(stats.f.sf(F, rank, G - 1))}
    hrows = [{"h": h, "period": p, "gamma": g, "se_cluster": s, "pct": 100 * np.expm1(g),
              "ci95_lo_pct": 100 * np.expm1(g - Z95 * s), "ci95_hi_pct": 100 * np.expm1(g + Z95 * s)}
             for h, p, g, s in zip(range(1, 13), per, gamma, se)]
    return hrows, joint


def world_df(start, vessels, treated):
    w = pd.read_csv(C.INTERIM / "world_by_vessel.csv.gz")
    w = w[(w["period"] >= start) & (w["period"] <= C.MAIN_END) & w["vessel"].isin(vessels)]
    df = w.rename(columns={"vessel": "unit"})[["unit", "period", "days", "value_t", "per_day"]].copy()
    df["control"] = ~df["unit"].isin(treated)
    return df.reset_index(drop=True)


def w6():
    rows = []
    full = world_df(C.PRE_START, m11.TRANSIT + m11.NON_TRANSIT, set(m11.TRANSIT))
    # design and estimator checks on the main sample
    d0, un0, _ = D.prepare(full, C.SHOCK_START, (), C.MAIN_END)
    for spec in imp.SPECS:
        Xa, na = fe_design_gen(d0, un0, spec, False, "2020-01")
        Xb, nb = D.fe_design(d0, un0, spec, False)
        same = na == nb and Xa.shape == Xb.shape and (abs(Xa - Xb)).max() == 0
        chk(f"review2_w6_design_{spec}", f"(f) generalised design with first_b = 2020-01 equals design.fe_design on the "
            f"RS-D2 main sample ({spec})", "identical", "identical" if same else "differs", same)
    types = pd.read_csv(TABLES / "rsd2_types.csv").set_index("vessel")
    summ = pd.read_csv(TABLES / "rsd2_summary.csv").set_index(["run", "spec"])
    for spec in imp.SPECS:
        tr, _ = fit_gen(full, C.SHOCK_START, C.MAIN_END, spec, "2020-01")
        c = tr[tr["unit"] == "CONTAINER"]["excess_t"].sum() / MT
        t = tr["excess_t"].sum() / MT
        d = max(abs(c - types.loc["CONTAINER", f"excess_total_t_{spec}"] / MT), abs(t - summ.loc[("main", spec), "excess_Mt"]))
        chk(f"review2_w6_estimator_{spec}", f"(f) generalised estimator on the RS-D2 main sample reproduces rsd2 "
            f"container and total excess ({spec}, Mt, |diff| <= 1e-6)", "agree", f"{d:.3g}", d <= 1e-6, f"{d:.3g}")
    # pre-trend reproduction on the main sample
    pa = pd.read_csv(TABLES / "pretrend_aggregate.csv")
    pa = pa[pa["test"] == "container"]
    cont_full = world_df(C.PRE_START, ["CONTAINER"] + m11.NON_TRANSIT, {"CONTAINER"})
    hr, jt = pretrend_gen(cont_full, "2020-01")
    ref_h = pa[pa["row"] == "h"].sort_values("h")
    ref_j = pa[pa["row"] == "joint"].iloc[0]
    d = max(maxdiff([r["gamma"] for r in hr], ref_h["gamma"]), maxdiff([r["se_cluster"] for r in hr], ref_h["se_cluster"]),
            abs(jt["wald_chi2"] - ref_j["wald_chi2"]) / ref_j["wald_chi2"])
    chk("review2_w6_pretrend_reproduced", "(f) generalised pre-trend test on the main sample reproduces "
        "pretrend_aggregate.csv (container: gamma_h, se, Wald; max |diff| <= 1e-9)", "agree", f"{d:.3g}", d <= 1e-9,
        f"{d:.3g}")

    # W6 estimates
    df = world_df(W6_START, m11.TRANSIT + m11.NON_TRANSIT, set(m11.TRANSIT))
    est = {}
    for spec in imp.SPECS:
        tr, dg = fit_gen(df, C.SHOCK_START, C.MAIN_END, spec, W6_FIRST_B, dense_check=True)
        est[spec] = tr
        chk(f"review2_w6_dense_{spec}", f"(f) W6 {spec}: sparse fit equals a dense minimum-norm least-squares fit "
            f"(max |fitted diff| <= 1e-8; dense rank {dg['dense_rank']} = parameters {dg['n_params']})", "agree",
            f"{dg['dense_max_abs_fitted_diff']:.3g}",
            dg["dense_max_abs_fitted_diff"] <= 1e-8 and dg["dense_rank"] == dg["n_params"],
            f"{dg['dense_max_abs_fitted_diff']:.3g}")
        for unit, part in (("CONTAINER", tr[tr["unit"] == "CONTAINER"]), ("TOTAL (ten cargo types)", tr)):
            e, cf = part["excess_t"].sum(), part["cf_t"].sum()
            ref = (types.loc["CONTAINER", f"excess_total_t_{spec}"] / MT, types.loc["CONTAINER", f"pct_{spec}"]) \
                if unit == "CONTAINER" else (summ.loc[("main", spec), "excess_Mt"], summ.loc[("main", spec), "pct"])
            rows.append({"label": W6_LABEL, "block": "estimate", "unit": unit, "spec": spec, "sample_start": W6_START,
                         "shock": C.SHOCK_START, "last_period": C.MAIN_END, "n_treated_months": part["period"].nunique(),
                         "excess_Mt": e / MT, "cf_Mt": cf / MT, "pct": 100 * e / cf,
                         "excess_Mt_W0": ref[0], "pct_W0": ref[1]})
    # placebo 2022-12
    for spec in imp.SPECS:
        tr, _ = fit_gen(df, W6_PLACEBO, W6_PLACEBO_END, spec, W6_FIRST_B)
        for unit, part in (("CONTAINER", tr[tr["unit"] == "CONTAINER"]), ("TOTAL (ten cargo types)", tr)):
            e, cf = part["excess_t"].sum(), part["cf_t"].sum()
            rows.append({"label": W6_LABEL, "block": "placebo", "unit": unit, "spec": spec, "sample_start": W6_START,
                         "shock": W6_PLACEBO, "last_period": W6_PLACEBO_END, "n_treated_months": part["period"].nunique(),
                         "excess_Mt": e / MT, "cf_Mt": cf / MT, "pct": 100 * e / cf})
    # pre-trend
    cont = world_df(W6_START, ["CONTAINER"] + m11.NON_TRANSIT, {"CONTAINER"})
    hr, jt = pretrend_gen(cont, W6_FIRST_B)
    for r in hr:
        rows.append({"label": W6_LABEL, "block": "pretrend_h", "unit": "CONTAINER", "spec": "S1",
                     "sample_start": W6_START, **r})
    rows.append({"label": W6_LABEL, "block": "pretrend_joint", "unit": "CONTAINER", "spec": "S1",
                 "sample_start": W6_START, **jt,
                 "note": "CONTAINER against the eight non-transit types; cluster-robust by ship type" +
                         ("; rank of the covariance below the number of terms, Moore-Penrose inverse, df = rank"
                          if jt["rank_V"] < jt["n_terms"] else "")})
    ref_j = pa[pa["row"] == "joint"].iloc[0]
    rows.append({"label": "reference: RS-D30 (a) on the main sample", "block": "pretrend_joint", "unit": "CONTAINER",
                 "spec": "S1", "sample_start": C.PRE_START,
                 **{k: ref_j[k] for k in ("n_clusters", "n_obs", "n_terms", "rank_V", "wald_chi2", "df", "p_chi2", "F",
                                          "df1", "df2", "p_F")}, "note": "from outputs/tables/pretrend_aggregate.csv"})
    out = pd.DataFrame(rows)
    cols = ["label", "block", "unit", "spec", "sample_start", "shock", "last_period", "n_treated_months", "excess_Mt",
            "cf_Mt", "pct", "excess_Mt_W0", "pct_W0", "h", "period", "gamma", "se_cluster", "ci95_lo_pct",
            "ci95_hi_pct", "n_clusters", "n_obs", "n_terms", "rank_V", "wald_chi2", "df", "p_chi2", "F", "df1", "df2",
            "p_F", "note"]
    out = out[cols]
    for c in ("n_treated_months", "h", "n_clusters", "n_obs", "n_terms", "rank_V", "df", "df1", "df2"):
        out[c] = out[c].astype("Int64")
    n_est = (out["block"] == "estimate").sum()
    chk("review2_w6_rows", "(f) W6 rows: 4 estimates (container, total x S1, S2), 4 placebo rows, 12 pre-trend terms, "
        "1 joint test (+1 reference row)", "4; 4; 12; 2",
        f"{n_est}; {(out['block'] == 'placebo').sum()}; {(out['block'] == 'pretrend_h').sum()}; "
        f"{(out['block'] == 'pretrend_joint').sum()}",
        n_est == 4 and (out["block"] == "placebo").sum() == 4 and (out["block"] == "pretrend_h").sum() == 12)
    c = out[(out["block"] == "estimate") & (out["unit"] == "CONTAINER")]
    p = out[(out["block"] == "placebo") & (out["unit"] == "CONTAINER")]
    print(f"W6: container S1 {c['excess_Mt'].iloc[0]:+.2f} Mt ({c['pct'].iloc[0]:+.2f}%), S2 {c['excess_Mt'].iloc[1]:+.2f} "
          f"Mt ({c['pct'].iloc[1]:+.2f}%); placebo 2022-12 S1 {p['pct'].iloc[0]:+.2f}%, S2 {p['pct'].iloc[1]:+.2f}%; "
          f"pre-trend Wald {jt['wald_chi2']:.3f}, p {jt['p_chi2']:.4f}")
    return out


# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------
OUT_NOTES = {
    "review2_gross_exclusions": "RS-D42(a): gross gains and losses (% of the summed counterfactual and Mt) of TER_INT, "
    "RES_TOTAL and TER_TOT, S1 and S2, with EGY, SAU, MYS left out singly and jointly; maxima of the RS-D31 "
    "equal-window placebo gains and losses and the rank of the actual value (largest first). TER_TOT has no "
    "equal-window placebo runs.",
    "review2_multiple_testing": "RS-D42(b, c): per non-control unit of RES_TOTAL, TER_INT and RES_INT: RS-D31 p_u, "
    "Benjamini-Hochberg and Benjamini-Yekutieli adjusted p-values and candidates (q = 0.10), family-wise p-values "
    "(S1, S2, combined) and candidates (<= 0.10), smallest attainable family-wise p-value.",
    "review2_multiple_testing_summary": "RS-D42(b, c): per series, the BH, BY and family-wise candidate lists and the "
    "smallest attainable family-wise p-value.",
    "review2_familywise_dates": "RS-D42(c): M_d, the maximum |standardized placebo statistic| over the non-control "
    "units at each equal-window placebo date, per series and specification, and the unit attaining it.",
    "review2_r17_economies": "RS-D42(d) R17: per economy, the results with GIB, PAN, BHS and MHL removed from the "
    "control pools (columns as the main units files, plus principle).",
    "review2_r17_summary": "RS-D42(d) R17: removed pool members, pool sizes, totals with the placebo band, gross gains "
    "and losses (S1), robust list and changes against R0, with the R0 values beside.",
    "review2_rq3_hq": "RS-D42(e): RQ3 residence regressions (weighted, S1 and S2) with HQ as in RS-D3, HQ + HKG, and "
    "HQ + HKG + JPN: coefficients, HC3 standard errors, 95% intervals, R2 and n. Descriptive.",
    "review2_w6": "RS-D42(f) W6 (non-inferential): container ships and the ten cargo types, estimation sample "
    "2021-07..2025-10; S1 and S2 excess with the W0 values beside; placebo 2022-12 (data to 2023-11); aggregate "
    "pre-trend test for container ships on the same sample, with the main-sample test as reference.",
}


def main():
    t0 = time.perf_counter()
    ex = pd.read_csv(C.INTERIM / "exposure.csv")
    pt = pd.read_csv(C.INTERIM / "panama_term.csv").set_index("iso3")
    R = pd.read_csv(C.INTERIM / "panama_restriction.csv").set_index("period")["R"]
    runs = read_runs()

    out = {}
    out["review2_gross_exclusions"] = gross_exclusions(runs)
    mt, mts, mtd = multiple_testing(runs)
    out["review2_multiple_testing"] = mt
    out["review2_multiple_testing_summary"] = mts
    out["review2_familywise_dates"] = mtd
    out["review2_r17_economies"], out["review2_r17_summary"] = r17(ex, pt, R)
    out["review2_rq3_hq"] = rq3_hq(ex)
    out["review2_w6"] = w6()

    SUPP.mkdir(parents=True, exist_ok=True)
    notes = []
    for name, df in out.items():
        path = TABLES / f"{name}.csv"
        df.to_csv(path, index=False)
        src = pd.read_csv(path, keep_default_na=False, dtype=str)
        stab = SUPP / f"stab_rev2_{name.removeprefix('review2_')}.csv"
        src.to_csv(stab, index=False)
        same = pd.read_csv(stab, keep_default_na=False, dtype=str).equals(src)
        chk(f"review2_stab_{name.removeprefix('review2_')}", f"{stab.name}: same cells as {rel(path)}", "identical",
            f"{len(src)} rows", same)
        notes.append(f"- `{stab.name}` ({len(src)} rows): {OUT_NOTES[name]} Source: `{rel(path)}` "
                     "(src/26_review2_checks.py).")
        print(f"{rel(path)}, {rel(stab)}: {len(src)} rows")
    lines = ["# Table notes: supplementary analyses after the second pre-submission review (RS-D42)", "",
             "Supplementary tables prefixed `stab_rev2_`; final numbers are assigned when the text is written. Values at "
             "full precision. Excess is in Mt CO2 over 2023-12..2025-10 unless stated.", ""] + notes + [""]
    (MANU / "table_notes_review2.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{rel(MANU / 'table_notes_review2.md')} written")
    write_checks(CHECKS, C.CHECKS / "review2_checks.csv")
    print(f"Run time {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
