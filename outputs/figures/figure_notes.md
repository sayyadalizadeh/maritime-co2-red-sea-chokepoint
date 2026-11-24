# Figure notes

Each figure is saved as PDF (vector) and PNG (300 dpi), with a data file holding the plotted numbers. Emissions are in Mt CO2, or kt CO2 per day where per-day values are plotted. The dashed vertical line on time axes marks 2023-12, the first crisis month. The estimation window ends in 2025-10.

## Main figures

### fig_transits

- Files: `outputs/figures/fig_transits.pdf`, `outputs/figures/fig_transits.png`
- Data file: `outputs/figures/fig_transits_data.csv`
- Source tables: outputs/checks/portwatch_relative_transits.csv (from the PortWatch daily file via data/interim/portwatch_monthly.csv.gz)
- Specification: Monthly mean of daily total transits (n_total) divided by the chokepoint's own mean over 2019-01..2023-11; 2019-01..2025-10.
- Definitions: Horizontal line at 1 = pre-crisis mean (January 2019 to November 2023, as in the y-axis label). Dashed vertical line = 2023-12 (shock month).

### fig_world_container

- Files: `outputs/figures/fig_world_container.pdf`, `outputs/figures/fig_world_container.png`
- Data file: `outputs/figures/fig_world_container_data.csv`
- Source tables: data/interim/world_by_vessel.csv.gz (W RES_TOTAL by ship type); outputs/tables/rsd2_types.csv (max_abs_placebo)
- Specification: RS-D2 main run (W0): transit types treated, non-transit types as controls; RS-D15 S1 and S2; 2019-01..2025-10.
- Definitions: Lines 'S1 fit (to November 2023) and counterfactual' and 'S2 fit (to November 2023) and counterfactual': up to 2023-11 they are fitted values of the model on untreated observations, multiplied by the smearing factor S_u; from 2023-12 they are the counterfactual. Band (from 2023-12 only): S1 counterfactual x (1 +- m/100), m = CONTAINER's maximum absolute placebo percentage over the 10 RS-D16 placebo runs of the main run (8.4490%). Per-day values in kt CO2 per day.

### fig_departure_bars

- Files: `outputs/figures/fig_departure_bars.pdf`, `outputs/figures/fig_departure_bars.png`
- Data file: `outputs/figures/fig_departure_bars_data.csv`
- Source tables: outputs/tables/rsd4_departure_units.csv; outputs/tables/xu_gsc.csv
- Specification: Departure principle (TER_INT), R0 main estimates (RS-D4, RS-D15), window 2023-12..2025-10; Xu (2017) generalized synthetic control (RS-D20, r chosen from 0..5).
- Definitions: Economies shown: non-control economies that are robust (RS-D16) or have |S1 excess| >= 1 Mt (31 economies), sorted by S1 excess. x-axis: excess summed over December 2023 to October 2025. Filled bars: robust; hollow bars: not robust. Diamonds: S2 excess. Crosses ('Generalized synthetic control (robust only)'): Xu (2017) generalized synthetic control excess, robust economies only.

### fig_departure_paths

- Files: `outputs/figures/fig_departure_paths.pdf`, `outputs/figures/fig_departure_paths.png`
- Data file: `outputs/figures/fig_departure_paths_data.csv`
- Source tables: data/interim/panel_departure.csv.gz; re-computed with src/09_imputation.py (same data and specification as outputs/tables/rsd4_departure_units.csv)
- Specification: Departure principle (TER_INT), R0, RS-D15 S1 and S2 with the Panama term; 2023-11 excluded from estimation (RS-D14). Panels shown 2021-01..2025-10; each panel has its own y-axis.
- Definitions: Solid black: observed per-day TER_INT. Dashed blue ('S1 fit (to November 2023) and counterfactual'): S1 fitted values up to 2023-11 (exp(fitted) x S_u) and the S1 counterfactual from 2023-12. Dotted vermillion: S2 counterfactual from 2023-12. Cross ('Observed, November 2023 (excluded from estimation)'): observed value in 2023-11, which is excluded from estimation and from the lines. Order: EGY, SAU, MYS, ESP, IND, LKA, MUS, LBN, AZE.

### fig_principles

- Files: `outputs/figures/fig_principles.pdf`, `outputs/figures/fig_principles.png`
- Data file: `outputs/figures/fig_principles_data.csv`
- Source tables: outputs/tables/rsd4_summary.csv
- Specification: R0 main estimates, both principles, window 2023-12..2025-10; bars S1, diamonds S2.
- Definitions: Gross gains = sum of positive economy totals; gross losses = sum of negative economy totals (non-control economies); net = total excess. Hatched part = the contribution of robust economies (RS-D16) to gains and to losses (S1). Control economies have zero excess by construction.

### fig_rq3_scatter

- Files: `outputs/figures/fig_rq3_scatter.pdf`, `outputs/figures/fig_rq3_scatter.png`
- Data file: `outputs/figures/fig_rq3_scatter_data.csv`
- Source tables: outputs/tables/rsd4_departure_units.csv; data/interim/exposure.csv; outputs/tables/rq3_coefficients.csv (departure, S1, weighted)
- Specification: Departure principle, R0 S1, non-control economies (88).
- Definitions: Point area proportional to the economy's window counterfactual (S1; the largest point has 250 pt^2). x-axis: x_v, the share of maritime export value through the Suez Canal. Groups: RSL (triangles), CPA (squares), other economies (circles; group 'other' in the data file; includes HQ and EEA economies). Line ('Weighted fit, other economies (S1)'): weighted RQ3 fit evaluated for other economies, const + b x x_v = 3.490 + 24.954 x x_v, over the observed range of x_v. Labels: RSL members and robust economies. Where a label cannot sit next to its point, a thin grey line joins them.

## Supplementary figures

### sfig_residence_paths

- Files: `outputs/figures/supplementary/sfig_residence_paths.pdf`, `outputs/figures/supplementary/sfig_residence_paths.png`
- Data file: `outputs/figures/supplementary/sfig_residence_paths_data.csv`
- Source tables: data/interim/panel_residence.csv.gz; re-computed with src/09_imputation.py (same data and specification as outputs/tables/rsd4_residence_units.csv)
- Specification: Residence principle (RES_TOTAL), R0, RS-D15 S1 and S2 with the Panama term; 2021-01..2025-10; no excluded month.
- Definitions: As fig_departure_paths. Economies: the 11 residence robust economies (AZE BEL CHL GIN HKG JOR KAZ MAR MUS OMN SYC), alphabetical.

### sfig_robustness_departure

- Files: `outputs/figures/supplementary/sfig_robustness_departure.pdf`, `outputs/figures/supplementary/sfig_robustness_departure.png`
- Data file: `outputs/figures/supplementary/sfig_robustness_departure_data.csv`
- Source tables: outputs/tables/robustness_economies.csv
- Specification: Departure principle, S1 window excess, variants R0-R10, R12, R13 (R11 is residence-only; R14 is leave-one-out and is not shown).
- Definitions: One panel per economy, each with its own x-axis. Dashed vertical line: R0 value. Missing marker: economy not estimated in that variant (ESP in R2, EEA dropped). Variant definitions in src/12_robustness_economies.py.

### sfig_world_types

- Files: `outputs/figures/supplementary/sfig_world_types.pdf`, `outputs/figures/supplementary/sfig_world_types.png`
- Data file: `outputs/figures/supplementary/sfig_world_types_data.csv`
- Source tables: outputs/tables/rsd2_types.csv
- Specification: RS-D2 main run (W0), transit types, window 2023-12..2025-10.
- Definitions: Grey band: from -m to +m, m = the type's maximum absolute placebo % over the 10 RS-D16 placebo runs. A type is robust when S1 and S2 share a sign and both exceed m in absolute value. Axis labels are readable names of the OECD ship-type codes, which are kept in the data file: CONTAINER = Container ships; VEHICLE = Vehicle carriers; BULK_CARRIER = Bulk carriers; OIL_TANKER = Oil tankers; CHEM_TANKER = Chemical tankers; LIQ_GAS_TANKER = Liquefied-gas tankers; RO_RO = Ro-ro ships; GEN_CARGO = General cargo ships; OTHER_LIQ_TANKER = Other liquids tankers; REFRIG_BULK = Refrigerated bulk carriers.

### sfig_dose

- Files: `outputs/figures/supplementary/sfig_dose.pdf`, `outputs/figures/supplementary/sfig_dose.png`
- Data file: `outputs/figures/supplementary/sfig_dose_data.csv`
- Source tables: outputs/tables/rsd2_dose_check.csv
- Specification: RS-D2 dose check; W0 S1 and S2 excess summed over the category's OECD types; three categories computed (tanker skipped: UNCTAD labels for chemical tankers and liquefied gas carriers absent).
- Definitions: x-axis ('Pre-crisis Suez transits per ship and year'): d_c = PortWatch Suez Canal mean daily transits 2019-01..2023-11 x 365 / UNCTAD world number of ships of the category on 1 January 2023. Each category is labelled at its upper marker. Where a label cannot sit next to its point, a thin grey line joins them.

### sfig_within_eea_residence

- Files: `outputs/figures/supplementary/sfig_within_eea_residence.pdf`, `outputs/figures/supplementary/sfig_within_eea_residence.png`
- Data file: `outputs/figures/supplementary/sfig_within_eea_residence_data.csv`
- Source tables: outputs/tables/within_eea.csv
- Specification: RS-D19 within-EEA estimate, residence principle, S1, against the R0 S1 estimate; economies outside the within-EEA control pool.
- Definitions: Filled markers: robust within the EEA panel (RS-D16 rule within that panel). Labels: economies robust within the EEA panel or in R0, ESP, GRC and FRA, and any economy with |S1 %| >= 20 in either estimate; other economies are shown unlabelled. Where a label cannot sit next to its point, a thin grey line joins them.

### sfig_within_eea_departure

- Files: `outputs/figures/supplementary/sfig_within_eea_departure.pdf`, `outputs/figures/supplementary/sfig_within_eea_departure.png`
- Data file: `outputs/figures/supplementary/sfig_within_eea_departure_data.csv`
- Source tables: outputs/tables/within_eea.csv
- Specification: RS-D19 within-EEA estimate, departure principle, S1, against the R0 S1 estimate; economies outside the within-EEA control pool.
- Definitions: Filled markers: robust within the EEA panel (RS-D16 rule within that panel). Labels: economies robust within the EEA panel or in R0, ESP, GRC and FRA, and any economy with |S1 %| >= 20 in either estimate; other economies are shown unlabelled. Where a label cannot sit next to its point, a thin grey line joins them.

### sfig_xu_vs_imputation_residence

- Files: `outputs/figures/supplementary/sfig_xu_vs_imputation_residence.pdf`, `outputs/figures/supplementary/sfig_xu_vs_imputation_residence.png`
- Data file: `outputs/figures/supplementary/sfig_xu_vs_imputation_residence_data.csv`
- Source tables: outputs/tables/xu_gsc.csv
- Specification: Residence principle, R0 robust economies: RS-D15 S1 and S2 (R0) and Xu (2017) generalized synthetic control (RS-D20, r chosen from 0..5), window 2023-12..2025-10.
- Definitions: Sorted by S1 %.

### sfig_xu_vs_imputation_departure

- Files: `outputs/figures/supplementary/sfig_xu_vs_imputation_departure.pdf`, `outputs/figures/supplementary/sfig_xu_vs_imputation_departure.png`
- Data file: `outputs/figures/supplementary/sfig_xu_vs_imputation_departure_data.csv`
- Source tables: outputs/tables/xu_gsc.csv
- Specification: Departure principle, R0 robust economies: RS-D15 S1 and S2 (R0) and Xu (2017) generalized synthetic control (RS-D20, r chosen from 0..5), window 2023-12..2025-10.
- Definitions: Sorted by S1 %.
