# maritime-co2-red-sea-chokepoint

Code and outputs for the article *How two accounting principles record shipping emissions from the Red Sea crisis*.

## Purpose

From December 2023, ships were rerouted from the Suez Canal and Bab el-Mandeb to the Cape of Good Hope during the Red Sea crisis. This repository estimates the monthly excess CO2 emissions of shipping during the crisis, for the world fleet by ship type and for individual economies. Economy results are given under two accounting principles: the residence of the vessel operator and the economy of voyage departure.

## Repository structure

```
README.md            this file
DECISIONS.md         dated record of the analysis decisions and their corrections
LICENSE              MIT licence for the code
CITATION.cff         citation metadata
requirements.txt     Python packages and versions
data/
  MANIFEST.csv       source, version, size and checksums of every raw file (written by 00_verify_raw.py)
  reference/         country-group table (written by 04_country_groups.py from the groups fixed in config.py)
  raw/               raw input files (not included; see Data sources)
  interim/           intermediate files written by the scripts (not included; regenerated)
src/
  run_all.py         runs every step in order and copies the submission figures
  00_*.py ... 26_*.py  numbered scripts, one step each
  09_imputation.py   estimator module used by later scripts (not a step)
  config.py          paths and fixed constants (dates, country groups)
  common.py          shared helpers (checksum guard, check builders, estimation runs)
  design.py          design matrix and estimators shared by the later scripts
  figstyle.py        shared figure settings
outputs/
  checks/            verification outputs of every step (expected against obtained values)
  tables/            estimates
  figures/           figures (PDF, 300-dpi PNG and a data file per figure), supplementary/ and figure notes
  figures/submission/  Fig1 to Fig6 (PDF and PNG), byte-identical copies of the main figures
  manuscript_tables/ main tables (CSV), supplementary/ tables and table notes
```

## Data sources

The raw files are not redistributed in this repository. Download each file and place it at the path given below. `src/00_verify_raw.py` computes the checksum of every file, compares it with the expected value and writes `data/MANIFEST.csv`. Every later script stops if a file it needs did not pass. `data/MANIFEST.csv` also lists the size in bytes and both the SHA-256 and MD5 checksums of every file.

### OECD
- **Dataset:** *Maritime transport CO2 emissions (experimental)*.
- **Version:** 2.0, release of 14 October 2026; downloaded 31 October 2026.
- **URL:** https://www.oecd.org/en/data/datasets/maritime-transport-co2-emissions.html
- **Path:** `data/raw/oecd/oecd_maritime_co2_raw_2026-10-31.csv` (200,921,743 bytes; full CSV download of dataflow `OECD.SDD.NAD.SEEA:DSD_MARITIME_TRANSPORT@DF_MARITIME_TRANSPORT`).
- **Checksum:** SHA-256 `88fb19b9645e4452d26e88cf8891467a3732d380a54f1b445f3735849fdf6002`.
- **Terms of use:** OECD Terms and Conditions, section 3: reuse and redistribution with attribution.

### IMF PortWatch
- **Dataset:** *Daily Chokepoints Data*; downloaded 31 October 2026.
- **URL:** https://portwatch.imf.org/datasets/3da2b9ca97684916b75c4013f95d18ab_0/about
- **Path:** `data/raw/portwatch/Daily_Chokepoints_Data.csv`.
- **Checksum:** SHA-256 `7b56fbaffba58c16ef0ff6e6024846438647e7d15861911f9c67932116f4d439`.
- **Terms of use:** as stated on the PortWatch website.
- **Recommended source line:** "Sources: Kpler; UN Global Platform; IMF PortWatch (portwatch.imf.org)."

### Verschuur and Hall (2025)
- **Dataset:** *Maritime chokepoint dependencies and systemic risks*, version 3 (published 24 November 2025), Zenodo.
- **URL:** https://doi.org/10.5281/zenodo.19663059
- **Terms of use:** CC BY 4.0.
- **Paths and checksums (MD5):**

| Path | MD5 |
|---|---|
| `data/raw/verschuur_v3/country_export_dependency.csv` | `88df0a9cc8302021d06c86c871780c2d` |
| `data/raw/verschuur_v3/country_import_dependency.csv` | `148bd8775a7d51c7207a6ff796a8d33d` |
| `data/raw/verschuur_v3/chokepoint_systemic_trade_risk.csv` | `365d388f4c23309a6a0c906f4f8fd85e` |
| `data/raw/verschuur_v3/chokepoint_systemic_economic_risk.csv` | `c0d3576ceba2be6304eefaf32e1ada45` |
| `data/raw/verschuur_v3/Maritime_chokepoint_risk_trade.ipynb` | `fc14fc4206f5f8ab52828361924759bb` |

### UNCTAD
- **Dataset:** *Merchant fleet: World fleet by flag of registration and ship type - Core indicators - Annual (analytical)*, UNCTADstat. Data refer to 1 January of each year; source Clarksons Research.
- **URL:** https://unctadstat.unctad.org/datacentre/dataviewer/US.MerchantFleet
- **Downloaded:** September 2026.
- **Path:** `data/raw/unctad/US_MerchantFleet.csv` (bulk file).
- **Checksum:** SHA-256 `a0c318d2e174e022ef8319fa08cef85cee9625ade9ca48a3dde7a15029372a62`.
- **Terms of use:** as stated on the UNCTADstat website.
- **Use:** only for the dose check of the system-level results.

## Software

- **Python:** 3.10.20.
- **Packages:** listed with their versions in `requirements.txt`: numpy, pandas, scipy and matplotlib. psutil is optional and is used only to print peak memory.
- **Platform:** the scripts use `pathlib` and run on Windows.

## How to run

From the repository root, after placing the raw files:

```
python src/run_all.py              # all steps, from the raw files to the tables and figures
python src/run_all.py --from 12    # start at a given step (file name, stem or number), for partial reruns
python src/run_all.py --list       # print the steps
```

**What `run_all.py` does:**
- It runs each script with the same Python interpreter, stops at the first step that fails, and prints the run time of each step and the total.
- The steps run in numeric order, with two exceptions:
  - `17_xu_gsc.py` runs twice: factor grid 0 to 5, then `--rmax 8` for the 0 to 8 sensitivity;
  - `20_false_positive.py` runs before `19_tables.py`, which reads its output.
- After the last step it copies the six main figures to `outputs/figures/submission/`.

**Run time:** a full run from the raw files took between 1.3 and 3.1 minutes in three test runs on the Windows machine used for testing.

**Checks and determinism:**
- Each script writes its verification results to `outputs/checks/`.
- Three checks in `verschuur_checks.csv` record known differences between the sources: two economies have no Suez Canal row, and some chokepoint names appear in only one source.
- All outputs are deterministic: a clean run reproduces every tracked file byte for byte.

## Outputs and the article

**Where the files are:**
- **Figures:** saved as `<name>.pdf`, `<name>.png` and `<name>_data.csv` in `outputs/figures/` (main) and `outputs/figures/supplementary/`.
- **Main tables (`tab_`):** in `outputs/manuscript_tables/`.
- **Supplementary tables (`stab_`):** in `outputs/manuscript_tables/supplementary/`.
- **Notes:** definitions and sources are in the notes files of each folder (`figure_notes*.md`, `table_notes*.md`).

**Main tables**

| Article item | Files |
|---|---|
| Table 1 | Data sources (described in the article; no output file) |
| Table 2 | `tab_system.csv`, `stab_robustness_world.csv`, `stab_rev_rolling_placebo_system.csv`, `stab_rev_ppml_world_types.csv` |
| Table 3 | `stab_economies_departure.csv`, `stab_economies_residence.csv`, `stab_rev_pretrend_units.csv`, `stab_rev_rolling_placebo_units.csv`, `stab_rev_revision_variants_units.csv`, `stab_rev_like_for_like_units.csv`, `stab_within_eea.csv` |
| Table 4 | `tab_rq3.csv` |

**Main figures** (submission copies in `outputs/figures/submission/`)

| Figure | File | Submission copy |
|---|---|---|
| Fig. 1 | `fig_transits` | `Fig1.pdf`, `Fig1.png` |
| Fig. 2 | `fig_world_container` | `Fig2.pdf`, `Fig2.png` |
| Fig. 3 | `fig_departure_bars` | `Fig3.pdf`, `Fig3.png` |
| Fig. 4 | `fig_departure_paths` | `Fig4.pdf`, `Fig4.png` |
| Fig. 5 | `supplementary/sfig_like_for_like` | `Fig5.pdf`, `Fig5.png` |
| Fig. 6 | `fig_rq3_scatter` | `Fig6.pdf`, `Fig6.png` |

**Supplementary tables** (`stab_` prefix and `.csv` omitted)

| Table | Files |
|---|---|
| S1 | `anomaly_flags_summary`, plus the check files in `outputs/checks/` |
| S2 | `data/reference/country_groups.csv`, `outputs/checks/group_coverage.csv` |
| S3 | `exposure`, `control_pools_quantity` |
| S4 | `robustness_economies`, `robustness_robust_changes`, `rev_revision_variants_economies`, `rev2_r17_summary` |
| S5 | `robustness_world`, `rev_revision_variants_world`, `rev2_w6` |
| S6 | `rev_container_monthly` |
| S7 | `rev_pretrend_aggregate`, `rev_pretrend_units` |
| S8 | `rev_ppml_world_types`, `rev_ppml_world`, `rev_ppml_simulation` |
| S9 | `dose_check` |
| S10 | `economies_departure` |
| S11 | `rev_rolling_placebo_gross` |
| S12 | `rev2_gross_exclusions` |
| S13 | `xu`, `xu_cv` |
| S14 | `rev2_multiple_testing`, `rev2_multiple_testing_summary` |
| S15 | `within_eea`, `within_eea_summary` |
| S16 | `false_positive` |
| S17 | `rev_rolling_placebo_bh`, `rev_rolling_placebo_units` |
| S18 | `economies_residence` |
| S19 | `rq3_variants`, `rq3_decomposition`, `rev_rq3_leave_one_out`, `rev2_rq3_hq` |
| S20 | `rev_like_for_like_summary`, `rev_like_for_like_pairs_summary`, `rev_like_for_like_units` |

**Supplementary figures** (in `outputs/figures/supplementary/`)

| Figure | File |
|---|---|
| S1 | `sfig_container_event` |
| S2 | `sfig_world_types` |
| S3 | `sfig_dose` |
| S4 | `sfig_within_eea_departure` |
| S5 | `sfig_robustness_departure` |
| S6 | `sfig_xu_vs_imputation_departure` |
| S7 | `sfig_residence_paths` |
| S8 | `sfig_xu_vs_imputation_residence` |
| S9 | `sfig_within_eea_residence` |

Further tables and figures in the output folders (for example `tab_data_panels.csv`, `tab_robust_economies.csv` and `fig_principles`) are described in the notes files.

## Decisions

The analysis decisions, with their dates, reasons and corrections, are recorded in `DECISIONS.md`.

## Licence

- **Code:** released under the MIT licence (see `LICENSE`).
- **Data:** not redistributed; they remain under the terms of their providers, listed under Data sources.

## Citation

Please cite this repository using the metadata in `CITATION.cff`. A DOI will be added after publication.
