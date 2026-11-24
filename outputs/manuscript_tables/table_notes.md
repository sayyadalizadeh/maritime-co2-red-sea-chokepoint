# Table notes

One line per table: source and definitions. Excess is in Mt CO2 over 2023-12..2025-10 unless stated; % is excess as a share of the counterfactual.

## Main tables

- `tab_data_panels.csv` (19 rows): Data sources, windows, panel sizes, control pools and excluded months. Sources: data/MANIFEST.csv, src/config.py, outputs/checks/panel_checks.csv, exposure_checks.csv, anomaly_months.csv, estimation_checks.csv.
- `tab_system.csv` (8 rows): World (W) RES_TOTAL by ship type, RS-D2 main run (transit types treated) and benchmark B1 (CONTAINER treated), S1 and S2; excess 2023-12..2025-10 (2023 = December, 2025 = January-October); placebo band = [min, max] of the 10 aggregate placebo % applied to the counterfactual total; robust per RS-D16; Panama-normal = excess summed over 2024-08..2025-10. Sources: outputs/tables/rsd2_summary.csv, rsd2_types.csv, rsd2_types_B1.csv.
- `tab_robust_economies.csv` (20 rows): Economies robust (RS-D16) under either principle, R0: S1 and S2 window excess (Mt, % of counterfactual), max |placebo %| over the 10 placebo runs, Xu (2017) generalized synthetic control (RS-D20, r from 0..5), and the number of robustness variants R1-R11 run for that principle in which the economy stays robust (residence: R1 R2 R3 R7 R8 R9 R10 R11; departure: R1-R10; an economy dropped by a variant counts as not robust), and the number of placebo dates (0-5) at which the economy is pseudo-robust in the false-positive calibration (RS-D23). Sources: outputs/tables/rsd4_<principle>_units.csv, xu_gsc.csv, robustness_robust_changes.csv, false_positive_by_economy.csv.
- `tab_rq3.csv` (8 rows): RQ3 (RS-D18): weighted least squares of the window excess % (R0) on exposure and group indicators, non-control economies, weights = window counterfactual of the same specification; coefficient (HC3 standard error). Associations, not causal effects. Source: outputs/tables/rq3_coefficients.csv.

## Supplementary tables

- `stab_economies_residence.csv` (125 rows): All economy results, residence principle, R0 (S1, S2, by year, 10 placebo %, max |placebo %|, robust). Source: outputs/tables/rsd4_residence_units.csv.
- `stab_economies_departure.csv` (122 rows): All economy results, departure principle, R0 (S1, S2, by year, 10 placebo %, max |placebo %|, robust). Source: outputs/tables/rsd4_departure_units.csv.
- `stab_exposure.csv` (144 rows): Exposure measures (x_v, x_q, m_v, Bab el-Mandeb share), pre-crisis component sums A, B, D, E, F (t), e_res, panel and group flags, control pools. Source: data/interim/exposure.csv (src/07_exposure.py).
- `stab_control_pools_quantity.csv` (2 rows): Control pools under quantity-based exposure (R9) and changes against the value-based pools. Source: outputs/checks/robustness_r9_pools.csv.
- `stab_robustness_economies.csv` (88 rows): Robustness variants R0-R14, economies, both principles, S1 and S2. Source: outputs/tables/robustness_economies.csv.
- `stab_robustness_robust_changes.csv` (20 rows): Robust economies gained and lost against R0 per variant. Source: outputs/tables/robustness_robust_changes.csv.
- `stab_robustness_world.csv` (20 rows): Robustness variants W0-W4, world, main run and B1. Source: outputs/tables/robustness_world.csv.
- `stab_rq3_variants.csv` (54 rows): RQ3 coefficients, all variants (weighted, unweighted, weighted excluding counterfactual < 1 Mt), S1 and S2, HC3 SE and 95% intervals. Source: outputs/tables/rq3_coefficients.csv.
- `stab_rq3_decomposition.csv` (26 rows): Excess by group and by exposure tercile, and the robust share of gross gains and losses. Source: outputs/tables/rq3_decomposition.csv.
- `stab_within_eea.csv` (48 rows): Within-EEA estimates (RS-D19) per EEA economy with R0 values. Source: outputs/tables/within_eea.csv.
- `stab_within_eea_summary.csv` (4 rows): Within-EEA totals, placebo bands and robust lists. Source: outputs/tables/within_eea_summary.csv.
- `stab_xu.csv` (40 rows): Xu (2017) generalized synthetic control (RS-D20) for the R0 robust economies, r chosen by cross-validation from 0..5 (main) and 0..8 (sensitivity). Sources: outputs/tables/xu_gsc.csv, xu_gsc_r8.csv.
- `stab_xu_cv.csv` (42 rows): Cross-validation mean squared prediction error by r. Sources: outputs/checks/xu_gsc_cv.csv, xu_gsc_cv_r8.csv.
- `stab_false_positive.csv` (12 rows): False-positive calibration of the robust rule (RS-D23): for each principle and placebo date p, the non-control economies that pass the RS-D16 rule when the S1 and S2 placebo % at p are treated as the main result and the other four dates (S1, S2; 8 runs) as placebos; summary rows give the mean and maximum count, the actual R0 robust count and the number of dates whose count is >= the actual count. The actual rule uses a 23-month window and 10 placebo runs, the pseudo version windows of at most 12 months and 8 runs. Source: outputs/tables/false_positive_calibration.csv.
- `stab_dose_check.csv` (4 rows): RS-D2 dose check by ship-type category. Source: outputs/tables/rsd2_dose_check.csv.
- `stab_anomaly_flags_summary.csv` (3 rows): RS-D14 anomaly scan: flags per principle and window. Sources: outputs/checks/anomaly_flags.csv, anomaly_months.csv.
