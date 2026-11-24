"""Run every numbered script in order to rebuild all outputs from the raw files.

Usage (from the repository root or from src/):
    python src/run_all.py                 # all steps
    python src/run_all.py --from 12       # start at 12_robustness_economies.py
    python src/run_all.py --list          # print the steps and exit

Each step runs as a separate process with the same Python interpreter as this
script, from inside src/. The run stops at the first step that exits with a
non-zero code. The run time of each step and the total are printed. After the
last step, the six main figures of the article are copied to
outputs/figures/submission/ as Fig1 to Fig6 (PDF and PNG, byte-identical copies).
"""

import argparse
import filecmp
import shutil
import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent

# Order of the steps. The numbered scripts run in numeric order, with two
# exceptions:
# - 17_xu_gsc.py runs twice: first with the default factor grid (0 to 5, the
#   main results), then with --rmax 8 (the 0 to 8 sensitivity). Both outputs
#   are read by 18_figures.py and 19_tables.py.
# - 20_false_positive.py runs before 19_tables.py, because the robust-economies
#   table and the false-positive supplementary table read its output.
# 09_imputation.py (the estimator), common.py, config.py, design.py and
# figstyle.py are modules imported by the scripts; they are not steps.
STEPS = [
    ["00_verify_raw.py"],          # checksums of the raw files -> data/MANIFEST.csv
    ["01_oecd_monthly.py"],        # monthly OECD series
    ["02_portwatch_monthly.py"],   # monthly PortWatch series
    ["03_verschuur_shares.py"],    # chokepoint trade shares
    ["04_country_groups.py"],      # country groups and coverage
    ["05_anomaly_scan.py"],        # anomalous economy-months
    ["06_panels.py"],              # analysis panels, world series by ship type
    ["07_exposure.py"],            # exposure measures and control pools
    ["08_portwatch_tables.py"],    # descriptive PortWatch tables
    ["10_rsd4_economies.py"],      # economy-level estimates and placebos
    ["11_rsd2_world.py"],          # world estimates by ship type and placebos
    ["12_robustness_economies.py"],
    ["13_robustness_world.py"],
    ["14_dose_check.py"],
    ["15_rq3_associations.py"],
    ["16_within_eea.py"],
    ["17_xu_gsc.py"],              # generalized synthetic control, factor grid 0..5
    ["17_xu_gsc.py", "--rmax", "8"],  # the same, factor grid 0..8
    ["18_figures.py"],
    ["20_false_positive.py"],      # must precede 19_tables.py
    ["19_tables.py"],
    # analyses added after the pre-submission review (RS-D29 to RS-D33)
    ["21_like_for_like.py"],       # RES_INT and TER_TOT series (RS-D29)
    ["22_pretrend.py"],            # pre-trend tests (RS-D30)
    ["23_rolling_placebo.py"],     # equal-length placebos, p-values, BH, gross (RS-D31, RS-D32); needs 21
    ["24_revision_variants.py"],   # R15/W5, R16, RQ3 leave-one-out, PPML, container path (RS-D33)
    ["25_revision_outputs.py"],    # supplementary figures and stab_rev_ tables; needs 21-24
    # supplementary analyses after the second pre-submission review (RS-D42)
    ["26_review2_checks.py"],      # gross shifts, BY, family-wise, R17, RQ3 HQ, W6; needs 10-25
]

# Figure files for submission: byte-identical copies of the six main figures of the article,
# made after the last step (outputs/figures/submission/Fig<n>.pdf and Fig<n>.png).
FIGURES = SRC.parent / "outputs" / "figures"
SUBMISSION_FIGURES = {
    "Fig1": "fig_transits",
    "Fig2": "fig_world_container",
    "Fig3": "fig_departure_bars",
    "Fig4": "fig_departure_paths",
    "Fig5": "supplementary/sfig_like_for_like",
    "Fig6": "fig_rq3_scatter",
}


def copy_submission_figures():
    """Copy the main figures to outputs/figures/submission/ and confirm the copies are identical."""
    out = FIGURES / "submission"
    out.mkdir(parents=True, exist_ok=True)
    for target, source in SUBMISSION_FIGURES.items():
        for ext in (".pdf", ".png"):
            src, dst = FIGURES / f"{source}{ext}", out / f"{target}{ext}"
            shutil.copyfile(src, dst)
            if not filecmp.cmp(src, dst, shallow=False):
                sys.exit(f"Copy differs from its source: {dst}")
    print(f"\n{len(SUBMISSION_FIGURES) * 2} submission figure files written to outputs/figures/submission/")


def label(step):
    return " ".join(step)


def start_index(name):
    """Index of the first step matching a script name, its stem or its number prefix."""
    for i, step in enumerate(STEPS):
        script = step[0]
        if name in (script, Path(script).stem, script.split("_")[0]):
            return i
    sys.exit(f"Unknown step '{name}'. Use --list to see the steps.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="start", metavar="STEP",
                        help="start at this script (file name, stem or number, e.g. 12)")
    parser.add_argument("--list", action="store_true", help="print the steps and exit")
    args = parser.parse_args()

    if args.list:
        for i, step in enumerate(STEPS, 1):
            print(f"{i:2d}  {label(step)}")
        return

    first = start_index(args.start) if args.start else 0
    steps = STEPS[first:]
    print(f"Interpreter: {sys.executable}")
    print(f"Running {len(steps)} of {len(STEPS)} steps, from {label(steps[0])}")
    times = []
    t_all = time.perf_counter()
    for step in steps:
        print(f"\n=== {label(step)} ===", flush=True)
        t0 = time.perf_counter()
        code = subprocess.call([sys.executable, *step], cwd=SRC)
        dt = time.perf_counter() - t0
        times.append((label(step), dt))
        if code != 0:
            print(f"\nStep failed: {label(step)} (exit code {code}) after {dt:.1f} s")
            sys.exit(code)
        print(f"--- {label(step)} done in {dt:.1f} s", flush=True)

    copy_submission_figures()
    total = time.perf_counter() - t_all
    print("\nRun times")
    for name, dt in times:
        print(f"  {name:<34s} {dt:8.1f} s")
    print(f"  {'Total':<34s} {total:8.1f} s ({total / 60:.1f} min)")


if __name__ == "__main__":
    main()
