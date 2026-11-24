# Figure notes: analyses added after the pre-submission review (RS-D29 to RS-D33)

Each figure is saved as PDF (vector) and PNG (300 dpi), with a data file holding the plotted numbers. The dashed vertical line on time axes marks 2023-12, the first crisis month.

No separate figure of the container monthly path (RS-D33): its S1 % is drawn in sfig_container_event; the numbers are in outputs/tables/container_monthly.csv.

### sfig_like_for_like

- Files: `outputs/figures/supplementary/sfig_like_for_like.pdf`, `outputs/figures/supplementary/sfig_like_for_like.png`
- Data file: `outputs/figures/supplementary/sfig_like_for_like_data.csv`
- Source tables: outputs/tables/like_for_like_units.csv, like_for_like_summary.csv (RES_INT, TER_TOT); outputs/tables/rsd4_residence_units.csv, rsd4_departure_units.csv (RES_TOTAL, TER_INT)
- Specification: RS-D29; main estimates of each series, window 2023-12..2025-10; bars S1, diamonds S2.
- Definitions: Panels from left: residence, all voyages (RES_TOTAL = A+B+D+E+F); residence, international voyages (RES_INT = D+E+F); departure, international voyages (TER_INT); departure, all voyages (TER_TOT = TER_DOM + TER_INT, domestic voyages counted in the economy where they take place). Gross gains = sum of positive economy totals; gross losses = sum of negative economy totals (non-control economies); net = total excess. Hatched part = contribution of the economies robust under RS-D16 in that series (S1).

### sfig_container_event

- Files: `outputs/figures/supplementary/sfig_container_event.pdf`, `outputs/figures/supplementary/sfig_container_event.png`
- Data file: `outputs/figures/supplementary/sfig_container_event_data.csv`
- Source tables: outputs/tables/pretrend_aggregate.csv (test container); outputs/tables/container_monthly.csv (from outputs/figures/fig_world_container_data.csv)
- Specification: Pre-crisis points: RS-D30 (a)1, S1 model on untreated observations, CONTAINER treated, the eight non-transit types as controls, W_h for h = 1..12 (2022-12..2023-11), RS-D15 weights. Crisis months: RS-D2 main run (W0), S1.
- Definitions: Pre-crisis points: exp(gamma_h) - 1 in %, with 95% intervals exp(gamma_h +- 1.96 se) - 1, se cluster-robust by ship type (9 clusters; the covariance of the 12 terms has rank 7, so the joint Wald test uses its Moore-Penrose inverse). Crisis months: (observed - S1 counterfactual) / S1 counterfactual x 100. The two parts come from different samples (pre-crisis: CONTAINER and eight non-transit types; crisis months: the main run with ten transit types treated).
