"""Small helpers shared by the numbered scripts."""

import sys
from pathlib import Path

import pandas as pd

import config as C

CHECK_COLUMNS = ["check", "definition", "expected", "obtained", "abs_diff", "pass"]


def rel(path: Path) -> str:
    """Path relative to the repository root, with forward slashes."""
    return Path(path).relative_to(C.ROOT).as_posix()


def require_verified(*paths: Path) -> None:
    """Stop the script unless every raw file passed the checksum test.

    The test result is read from data/MANIFEST.csv, written by 00_verify_raw.py.
    """
    if not C.MANIFEST.exists():
        sys.exit(f"STOP: {rel(C.MANIFEST)} not found. Run 00_verify_raw.py first.")
    manifest = pd.read_csv(C.MANIFEST, dtype=str)
    status = dict(zip(manifest["path"].str.lower(), manifest["checksum_match"]))
    failed = []
    for p in paths:
        key = C.RAW.relative_to(C.ROOT).as_posix() + "/" + Path(p).relative_to(C.RAW).as_posix()
        if status.get(key.lower()) != "true":
            failed.append(f"{key} (checksum_match = {status.get(key.lower(), 'missing')})")
    if failed:
        sys.exit("STOP: raw file(s) not verified:\n  " + "\n  ".join(failed))


def is_verified(path: Path) -> bool:
    """True if the raw file passed the checksum test in data/MANIFEST.csv."""
    if not C.MANIFEST.exists():
        return False
    manifest = pd.read_csv(C.MANIFEST, dtype=str)
    key = C.RAW.relative_to(C.ROOT).as_posix() + "/" + Path(path).relative_to(C.RAW).as_posix()
    status = dict(zip(manifest["path"].str.lower(), manifest["checksum_match"]))
    return status.get(key.lower()) == "true"


def decimals_of(expected: str) -> int:
    """Number of decimals in a numeric string such as '0.179' or '-54'."""
    s = str(expected).strip()
    return len(s.split(".")[1]) if "." in s else 0


def numeric_check(name, definition, expected, obtained, decimals, tol=None):
    """Build one check row for a numeric value.

    `obtained` is rounded to `decimals`. The check passes when the absolute
    difference between the rounded value and `expected` is at most `tol`
    (default: half a unit of the last decimal of `expected`, i.e. equality at
    the precision of the expected value).
    """
    exp_dec = decimals_of(expected)
    exp = float(expected)
    if obtained is None or pd.isna(obtained):
        return dict(check=name, definition=definition, expected=expected,
                    obtained="NA", abs_diff="NA", **{"pass": False})
    got = round(float(obtained), decimals)
    diff = abs(got - exp)
    if tol is None:
        tol = 0.5 * 10 ** (-exp_dec) + 1e-12
    return dict(check=name, definition=definition, expected=expected,
                obtained=f"{got:.{decimals}f}", abs_diff=f"{diff:.{decimals}f}",
                **{"pass": bool(diff <= tol + 1e-12)})


def exact_check(name, definition, expected, obtained):
    """Build one check row for a count, date or label (exact match)."""
    ok = str(expected) == str(obtained)
    diff = ""
    try:
        diff = str(abs(int(str(obtained)) - int(str(expected))))
    except ValueError:
        diff = "0" if ok else "n/a"
    return dict(check=name, definition=definition, expected=str(expected),
                obtained=str(obtained), abs_diff=diff, **{"pass": ok})


def range_check(name, definition, lo, hi, values, decimals, tol=0.0):
    """Pass when every value, rounded to `decimals`, lies within [lo - tol, hi + tol]."""
    vals = [round(float(v), decimals) for v in values if pd.notna(v)]
    if not vals:
        return dict(check=name, definition=definition, expected=f"{lo}-{hi}",
                    obtained="NA", abs_diff="NA", **{"pass": False})
    vmin, vmax = min(vals), max(vals)
    out = max(0.0, float(lo) - vmin, vmax - float(hi))
    return dict(check=name, definition=definition, expected=f"{lo}-{hi}",
                obtained=f"{vmin:.{decimals}f}-{vmax:.{decimals}f}",
                abs_diff=f"{out:.{decimals}f}", **{"pass": bool(out <= tol + 1e-12)})


def months(start: str, end: str) -> list:
    """List of YYYY-MM strings from start to end inclusive."""
    return pd.period_range(start, end, freq="M").strftime("%Y-%m").tolist()


def days_in(periods) -> pd.Series:
    """Days in month for a sequence of YYYY-MM strings."""
    return pd.Series(pd.PeriodIndex(list(periods), freq="M").days_in_month, index=getattr(periods, "index", None))


def load_oecd_monthly(vessel="ALL_VESSELS") -> pd.DataFrame:
    """Monthly OECD extract for one vessel aggregate (requires the verified raw file)."""
    require_verified(C.OECD_FILE)
    m = pd.read_csv(C.OECD_MONTHLY)
    return m[m["vessel"] == vessel] if vessel is not None else m


def complete_economies(m: pd.DataFrame, source: str, start: str, end: str) -> list:
    """Economies (W, OECD, W_O excluded) with a value in every month of start..end."""
    win = months(start, end)
    s = m[(m["source"] == source) & m["period"].isin(win) & ~m["area"].isin(C.NON_ECONOMY_AREAS)]
    n = s.groupby("area")["period"].nunique()
    return sorted(n[n == len(win)].index)


def group_flags(iso3: pd.Series) -> pd.DataFrame:
    """Boolean membership columns rsl, cpa, hq, eea, rus for a series of iso3 codes."""
    return pd.DataFrame({g.lower(): iso3.isin(members).values
                         for g, (members, _) in C.COUNTRY_GROUP_DEFS.items()}, index=iso3.index)


def imputable(df, shock, drop=(), last=None):
    """Remove treated cells that cannot be imputed.

    A treated observation needs its unit x calendar-month effect, which is
    estimated only from that unit's untreated observations of the same calendar
    month. When economy-months are removed from the panel (variant R7), a short
    placebo window can leave a unit with no untreated observation of a calendar
    month; its treated observations of that calendar month are then removed
    before fitting. Returns (table, number of treated rows removed). In a
    balanced panel nothing is removed.
    """
    d = df[~df["period"].isin(list(drop))]
    if last is not None:
        d = d[d["period"] <= last]
    cal = d["period"].str[5:7]
    untreated = (d["period"] < shock) | d["control"].astype(bool)
    support = set(zip(d.loc[untreated, "unit"], cal[untreated]))
    ok = untreated | pd.Series([(u, c) in support for u, c in zip(d["unit"], cal)], index=d.index)
    return d[ok], int((~ok).sum())


def run_variant(df, drop=(), last=None, last_pre=C.PRE_END, panama=False, placebo_dates=None,
                placebos=True):
    """Main S1/S2 fits, placebo runs and RS-D16 robust classification with 09_imputation.

    placebo_dates defaults to the RS-D16 dates; each placebo run keeps data up to
    min(date + 11 months, last_pre), with the same drop list as the main run,
    as in 09_imputation.placebo_runs.

    Returns a dict with:
    - main: {spec: treated table}, diags: {spec: fit diagnostics}, weights;
    - units: per-unit DataFrame (excess and % per spec, placebo %, robust);
    - placebo: aggregate placebo table (spec, placebo_date, pct, excess_t, cf_t), or None.
    """
    import importlib
    import numpy as np
    imp = importlib.import_module("09_imputation")
    dates = imp.PLACEBO_DATES if placebo_dates is None else tuple(placebo_dates)
    last = last if last is not None else C.MAIN_END

    main, diags, weights = {}, {}, None
    removed = {}
    d_main, removed["main"] = imputable(df, C.SHOCK_START, drop, last)
    for spec in imp.SPECS:
        tr, dg, weights = imp.fit_impute(d_main, shock=C.SHOCK_START, drop=drop, last=last,
                                         spec=spec, panama=panama)
        main[spec], diags[spec] = tr, dg
    g = {s: imp.summarise_unit(main[s])[0] for s in imp.SPECS}
    units = pd.DataFrame({"excess_t_S1": g["S1"]["excess_t"], "excess_t_S2": g["S2"]["excess_t"],
                          "cf_t_S1": g["S1"]["cf_t"], "cf_t_S2": g["S2"]["cf_t"],
                          "pct_S1": g["S1"]["pct"], "pct_S2": g["S2"]["pct"]})
    agg = None
    if placebos:
        cols, rows = {}, []
        for p in dates:
            end = min(imp.add_months(p, 11), last_pre)
            d_p, removed[p] = imputable(df, p, drop, end)
            for spec in imp.SPECS:
                tr, _, _ = imp.fit_impute(d_p, shock=p, drop=drop, last=end, spec=spec, panama=panama)
                if not np.isfinite(tr["excess_t"]).all():
                    raise RuntimeError(f"non-finite excess in placebo run {p} {spec}")
                gg = tr.groupby("unit")[["excess_t", "cf_t"]].sum()
                cols[f"placebo_{p}_{spec}"] = 100 * gg["excess_t"] / gg["cf_t"]
                rows.append({"spec": spec, "placebo_date": p, "last_period": end,
                             "pct": imp.pct(tr["excess_t"].sum(), tr["cf_t"].sum()),
                             "excess_t": tr["excess_t"].sum(), "cf_t": tr["cf_t"].sum()})
        pl = pd.DataFrame(cols).reindex(units.index)
        units = units.join(pl)
        units["max_abs_placebo"] = pl.abs().max(axis=1)
        units["robust"] = imp.robust(units["pct_S1"], units["pct_S2"], units["max_abs_placebo"])
        agg = pd.DataFrame(rows)
    for spec, tr in main.items():
        if not np.isfinite(tr["excess_t"]).all():
            raise RuntimeError(f"non-finite excess in the main {spec} fit")
    return {"main": main, "diags": diags, "weights": weights, "units": units, "placebo": agg,
            "removed": removed}


def update_checks(rows, path: Path, prefix: str) -> pd.DataFrame:
    """Replace the rows whose check name starts with `prefix` in a shared check file.

    Rows are written in a fixed order, so that the file does not depend on the
    order in which the contributing scripts are run: grouped by the check-name
    prefix (the text before the first underscore, e.g. `rsd2`, `rsd4`), prefixes
    in alphabetical order; within a prefix, rows keep the order in which the
    script that writes them lists them (stable sort).
    """
    new = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    new["pass"] = new["pass"].map(lambda b: "true" if b else "false")
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False)
        old = old[~old["check"].str.startswith(prefix)]
        new = pd.concat([old, new], ignore_index=True)
    key = new["check"].str.split("_", n=1).str[0]
    new = new.iloc[key.argsort(kind="stable")].reset_index(drop=True)
    new.to_csv(path, index=False)
    part = new[new["check"].str.startswith(prefix)]
    print(f"{rel(path)}: {(part['pass'] == 'true').sum()} of {len(part)} '{prefix}' checks passed")
    return new


def write_checks(rows, path: Path) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    df["pass"] = df["pass"].map(lambda b: "true" if b else "false")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    n_pass = (df["pass"] == "true").sum()
    print(f"{rel(path)}: {n_pass} of {len(df)} checks passed")
    return df
