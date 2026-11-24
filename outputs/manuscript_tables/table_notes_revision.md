# Table notes: analyses added after the pre-submission review (RS-D29 to RS-D33)

Supplementary tables prefixed `stab_rev_`; final numbers are assigned when the text is written. Values at full precision. Excess is in Mt CO2 over 2023-12..2025-10 unless stated.

- `stab_rev_like_for_like_summary.csv` (4 rows): RS-D29 like-for-like comparison: panel and pool sizes, totals S1/S2 (Mt, %), placebo band, gross gains and losses (S1, all and robust), robust list, for RES_TOTAL and TER_INT (reference rows read from the main outputs) and RES_INT and TER_TOT (estimated). Source: outputs/tables/like_for_like_summary.csv.
- `stab_rev_like_for_like_units.csv` (242 rows): RS-D29: all economy results for RES_INT and TER_TOT (columns as the main units files). Source: outputs/tables/like_for_like_units.csv.
- `stab_rev_like_for_like_pairs.csv` (239 rows): RS-D29: S1 % side by side for economies in both series of a pair (RES_INT vs TER_INT; RES_TOTAL vs TER_TOT). Source: outputs/tables/like_for_like_pairs.csv.
- `stab_rev_like_for_like_pairs_summary.csv` (2 rows): RS-D29: per pair, economies in both, correlations of S1 % over economies that are non-control in both, robust overlaps and the five largest differences. Source: outputs/tables/like_for_like_pairs_summary.csv.
- `stab_rev_like_for_like_exposure.csv` (269 rows): RS-D29: exposure (e_int, x_tot), Panama share, international share and control pool per economy of the RES_INT and TER_TOT panels. Source: outputs/checks/like_for_like_exposure.csv.
- `stab_rev_pretrend_aggregate.csv` (51 rows): RS-D30 (a): gamma_h as % with 95% intervals and the cluster-robust Wald test (chi-squared and F forms), for container ships, the ten cargo types, residence and departure economies. Source: outputs/tables/pretrend_aggregate.csv.
- `stab_rev_pretrend_units.csv` (21 rows): RS-D30 (b): per-unit pre-trend test over the last 12 pre-crisis months (departure 11), Newey-West (3 lags) standard errors, flag = p < 0.05. Source: outputs/tables/pretrend_units.csv.
- `stab_rev_rolling_placebo_units.csv` (272 rows): RS-D31: equal-length rule (max |placebo %| over the rolling runs, robust flag) and unit p-values (sigma, z, p per specification, p_u, sign agreement, BH candidate) for the non-control economies of RES_TOTAL, TER_INT and RES_INT. Source: outputs/tables/rolling_placebo_units.csv.
- `stab_rev_rolling_placebo_system.csv` (16 rows): RS-D31: equal-length rule for ship types and totals (world main run and B1) and for the economy totals. Source: outputs/tables/rolling_placebo_system.csv.
- `stab_rev_rolling_placebo_bh.csv` (3 rows): RS-D31: Benjamini-Hochberg candidates (q = 0.10) with the expected number of false discoveries, null sizes, and equal-length robust lists against the RS-D16 lists. Source: outputs/tables/rolling_placebo_bh.csv.
- `stab_rev_rolling_placebo_gross.csv` (40 rows): RS-D32: gross gains and losses (S1) as % of the summed counterfactual, per rolling placebo date and actual, with the placebo maxima and the rank of the actual value. Source: outputs/tables/rolling_placebo_gross.csv.
- `stab_rev_revision_variants_economies.csv` (8 rows): RS-D33: R15 (2024-01..2025-10 re-sum of R0) and R16 (stricter control pools), both principles, S1 and S2: totals, placebo bands, robust lists and changes against R0, pool members. Source: outputs/tables/revision_variants_economies.csv.
- `stab_rev_revision_variants_units.csv` (387 rows): RS-D33: per-economy results of R15 and R16. Source: outputs/tables/revision_variants_units.csv.
- `stab_rev_revision_variants_world.csv` (26 rows): RS-D33: W5 (2024-01..2025-10 re-sum of W0), main run and B1, totals and ship types, robust flags against the W0 placebo maxima. Source: outputs/tables/revision_variants_world.csv.
- `stab_rev_rq3_leave_one_out.csv` (20 rows): RS-D33: RQ3 weighted regressions (S1, S2) with each RSL economy left out in turn: RSL coefficient, HC3 standard error and 95% interval. Descriptive. Source: outputs/tables/rq3_leave_one_out.csv.
- `stab_rev_ppml_world.csv` (4 rows): RS-D33: PPML at system level, main run and B1, S1 and S2: totals, placebo band, robust flags. Source: outputs/tables/ppml_world.csv.
- `stab_rev_ppml_world_types.csv` (11 rows): RS-D33: PPML per treated ship type with the 10 placebo % and the RS-D16 rule. Source: outputs/tables/ppml_world_types.csv.
- `stab_rev_ppml_simulation.csv` (102 rows): RS-D33: PPML on simulated panels with no effect (one noise-free panel; 50 panels with multiplicative noise, sd 0.05). Source: outputs/tables/ppml_simulation.csv.
- `stab_rev_container_monthly.csv` (26 rows): RS-D33: monthly container excess (Mt, %), S1 and S2, 2023-12..2025-10, and means for 2023-12..2024-07 and 2024-08..2025-10. Source: outputs/tables/container_monthly.csv.

## Additions to existing tables

- `tab_system.csv`: the S2 rows of container ships (main run and B1) now hold the yearly excess (2023 = December, 2024, 2025 = January-October) from the W0 S2 estimates in `outputs/tables/robustness_world_container.csv` (src/13_robustness_world.py); the yearly sums add up to the window total. No other cell changed.
- `supplementary/stab_robustness_world.csv`: new column `container_max_abs_placebo_pct`, the maximum |placebo %| of container ships over the placebo runs of each estimated variant (W0, W1: 10 runs; W2: 4 runs), from `outputs/tables/robustness_world_container.csv`. Empty for W3 and W4, which re-sum W0 and have no placebo runs of their own. No other cell changed.
