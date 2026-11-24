# Analysis decisions

This file records the analysis decisions of the study, with their dates and reasons, including later corrections. Each decision keeps its code (RS-D1, RS-D2, …), because the scripts and the check files refer to these codes. All dates are in 2026.

## Order of the decisions

- **RS-D1 to RS-D17** (19 and 20 November) were fixed before the economy-level estimates were first computed. This includes the placebo dates and the robust rule (RS-D16). One correction followed the first economy-level run: the Panama restriction months of RS-D15 (see Corrections).
- **RS-D18 to RS-D28** (21 and 22 November) came after the first economy-level and system-level estimates had been seen. They add explanatory analyses, supplementary checks, presentation choices and the code licence. They do not change the estimator, the placebo dates or the robust rule.
- **RS-D29 to RS-D33** (23 November) are analyses added after an internal pre-submission review. **RS-D34**, the criterion for naming economies in the abstract, was fixed on the same day, before the results of RS-D29 to RS-D33 were seen. RS-D35 to RS-D38 came after those results.
- **RS-D39 to RS-D42** (24 November) came after a second internal pre-submission review. RS-D42 adds supplementary analyses only.
- **RS-D43** (25 November) concerns the publication of this repository.

## Corrections

- **Panama restriction months (RS-D15, corrected 20 November).**
  - As first written, the rule set R = 1 in every month in which Panama Canal transits were below 0.90 times their 2019-01…2023-11 mean. The same decision stated that this gives the drought-restriction episode 2023-11…2024-07.
  - Applied to all months, the rule also selected 2020-05, 2020-06, 2020-07 and 2021-09, which are pandemic demand dips, not restrictions. The first economy-level run showed this inconsistency.
  - The rule was corrected to months from 2023-01 on, which gives 2023-11…2024-07. The all-months reading is kept as robustness variant R1.
- **Label "main (corrected R)".** In the economy robustness table, variant R0 is labelled "main (corrected R)". It is the main estimate with the corrected Panama restriction months described above. It is not a different specification.
- **PPML simulation check (RS-D33).**
  - As first written, the check required every one of 50 simulated noisy panels with no effect to give an excess within ±1%. It failed: S1 had 12 of 50 panels outside ±1% and S2 had 25 of 50. The spread of single panels depends on the chosen noise level, not on the estimator.
  - The check was redefined before the PPML results were reported. (a) On a noise-free simulated panel with no effect, the excess must be zero. (b) Over the 50 noisy panels, the mean excess must lie within ±1%. Both parts pass, and the per-panel results are reported.
- **Departure pre-trend window (RS-D30(b), implementation).** The per-unit departure test first used the window 2022-11…2023-10 instead of 2022-12…2023-10 (the last twelve pre-crisis months without the excluded 2023-11). This was corrected before the results were reported. The set of flagged economies did not change.
- **Abstract criterion applied as written (RS-D38).** RS-D34 was fixed before the results of RS-D29 to RS-D33 were seen. It was then applied exactly as written: a pre-trend flag excludes an economy from the abstract whatever the sign of the pre-crisis deviation. Egypt, Sri Lanka, India and Malaysia (departure), and Spain (within the EEA), are therefore not named in the abstract.
- **Analyses after the internal pre-submission reviews.** RS-D29 to RS-D33 and RS-D42 were added after internal pre-submission reviews. They are supplementary or robustness analyses. They leave the main estimates, the placebo dates and the robust rule unchanged.
- **Replaced or dropped decisions.**
  - RS-D2 and RS-D4 were revised on 20 November to use the RS-D15 estimator.
  - RS-D16 replaced a planned bootstrap.
  - RS-D17 replaced the EEA row of RS-D6; its part (ii) was later replaced by RS-D19.
  - RS-D21 dropped the continuous-treatment difference-in-differences.
  - RS-D39 replaced the title of RS-D35.
  - The figure and table numbering of RS-D22 and RS-D25 was later updated; the current mapping is in `README.md`.

## Decisions

### RS-D1: Study window (19 November)
- **Pre-crisis period:** 2019-01 to 2023-11.
- **Shock start:** 2023-12.
- **Main estimation end:** 2025-10, giving 23 crisis months.
- **Reasons for the end date:**
  - Strait of Hormuz traffic fell from 2025-11 and collapsed after hostilities began on 28 February 2026.
  - The OECD domestic/international classification changes from 2026-01.
- **Sensitivity checks:**
  - a residence-principle window ending 2026-02;
  - for departure-based models, the pre-crisis period without 2021-11 to 2022-10 (an apparent reclassification episode).
- **From 2026-03:** descriptive use only.

### RS-D2: System-level excess (19 November; revised 20 November)
- **Data:** world residence-based emissions by ship type, as per-day values, 2019-01 to 2025-10.
- **Treated types:** the ten cargo (transit) types, treated from 2023-12.
- **Controls:** the eight non-cargo types.
- **Excluded:** cruise ships, because PortWatch has no matching category; they are described only.
- **Estimator:** RS-D15 without the Panama term (S1 main, S2 robustness), with RS-D16 placebos.
- **Comparisons:**
  - benchmark B1, with container ships treated and all other types as controls;
  - a sum restricted to 2024-08…2025-10, after Panama Canal traffic recovered;
  - a dose check: excess by ship category against pre-crisis Suez transits per ship, using the UNCTAD fleet counts.
- **Stated weakness:** the control types are small and not trade-driven, so they track trade demand only partly.

### RS-D3: Exposure measures (19 November)
- **Departure principle:** the economy's value share of maritime exports passing the Suez Canal (Verschuur and Hall, version 3). The quantity share is used as robustness.
- **Residence principle:** a shift-share measure that weights the export share, the import share and the world-average share by the economy's pre-crisis emission components. It is used together with an indicator for the headquarters economies of the nine alliance carriers on Asia–Europe services (HQ).
- **Robustness:** Planned robustness: ONE assigned to Japan, and consolidated subsidiaries assigned to their own economies. Only the first was carried out, as the RQ3 sensitivity with Japan added to HQ (RS-D42(e)); the second was not carried out.
- **Stated limitation:** no public pre-crisis data link operators to routes.

### RS-D4: Economy-level excess (19 November; revised 20 November)
- **Estimator:** RS-D15 for each principle (residence: total residence-based emissions; departure: international voyages by departure economy), with the Panama term.
- **Panels:** residence 125 economies, departure 122.
- **Control pools** (assumed to have zero excess): economies in the lowest exposure tercile, excluding the Red Sea littoral, Cape-route Africa, HQ economies and Russia. Residence 29, departure 34.
- **Reported:**
  - excess per economy, by year and for the window, in S1 and S2;
  - robust flags;
  - gross gains and losses;
  - a comparison of the two principles.
- **System total:** the net figure comes from RS-D2.

### RS-D5: Redistribution channels (19 November)
- **Three channels:**
  1. longer voyages for Suez-dependent exporters;
  2. traffic loss on the Red Sea / Gulf of Aden littoral;
  3. traffic gain in Cape-route Africa.
- Gains and losses are reported separately.
- Both groups are excluded from the control pools.

### RS-D6: Concurrent events (19 November)
| Event | Handling |
|---|---|
| EU ETS and FuelEU Maritime | See RS-D17. |
| Panama Canal restrictions | Panama term (economies); restricted sum (world). |
| COVID-19 | Robustness without 2020–2021. |
| Sanctions on Russia | Russia out of the control pool; robustness without Russia. |
| US–China tariffs | Leave-one-out of large economies. |
| Fleet growth and demand | Common month effects. |

Further robustness checks: placebo dates, quantity-based exposure, a vessel aggregate without fishing, and the residence window to 2026-02.

### RS-D7: Repository name (19 November)
`maritime-co2-red-sea-chokepoint`.

### RS-D8: Data vintage (19 November)
- The OECD and PortWatch downloads of 31 October 2026 and Verschuur and Hall version 3 are frozen.
- A re-download before submission was planned as a revision-sensitivity check; it was not carried out.

### RS-D9: Vessel aggregate (19 November)
- **Main aggregate:** all vessels.
- **Robustness:** all vessels without fishing. At world level this is built as all vessels minus fishing.

### RS-D10: Sample of economies (19 November)
- Balanced panels per principle within the window.
- Switzerland has no departure series; it is shown separately.
- World, OECD and "other countries" aggregates are excluded from economy panels.

### RS-D11: September 2025 (19 November)
- The OECD series shows a September 2025 anomaly. It is absorbed by month effects in the economy models.
- System totals are reported with and without that month.

### RS-D12: Target journal (19 November)
Transportation Research Part D. The format requirements of the journal's guide for authors are followed.

### RS-D13: Unpublished components (20 November)
- In the residence exposure, a component that is absent in a pre-crisis month is set to zero. Reason: the published components already add up to the residence total.
- Economy-months where the components and the total differ by more than 1% are listed.

### RS-D14: Anomalous months (20 November)
- **Fixed exclusion:** 2023-11 is excluded from all departure-principle estimation, because of a documented departure anomaly in that month. The reference month for that principle is 2023-10.
- **Pre-specified anomaly scan,** run in every estimation step:
  - each economy-month's log value is compared with the economy's centred seven-month median; deviations larger than 0.4 are flagged;
  - a month is system-wide anomalous if at least four large economies are flagged;
  - system-wide anomalous months are excluded;
  - isolated flags stay in the main estimate and are dropped in a robustness run.
- **Result on the frozen data:** departure, 2023-11 only; residence, none.
- **Robustness:** 2023-11 included; 2023-09 to 2023-11 excluded.

### RS-D15: Imputation estimator (20 November; Panama months corrected 20 November)
- **Model:** weighted least squares on untreated observations, with outcome the log of the per-day value.
- **Specifications:**
  - S1: unit × calendar-month effects, month effects and, for economies, a Panama term P × R (exposure × restriction months);
  - S2: S1 plus unit-specific linear trends.
- **Weights:** pre-crisis mean per-day value.
- **Counterfactual:** the fitted value with a smearing factor. **Excess:** observed minus counterfactual.
- **R:** months from 2023-01 on in which Panama Canal transits were below 0.90 of their pre-crisis mean (2023-11…2024-07); see Corrections.

### RS-D16: Placebo inference and robust rule (20 November)
- **Placebo dates:** 2020-12, 2021-06, 2021-12, 2022-06 and 2022-12. Each run keeps the data up to 11 months after its date (at most to the last pre-crisis month) and is run with S1 and S2.
- **Robust unit:** S1 and S2 agree in sign, and the smaller absolute percentage exceeds the unit's largest absolute placebo percentage.
- **Aggregate placebo band:** the range of the ten aggregate placebo percentages.
- This replaces a planned bootstrap. The dates and the rule were fixed before results were seen.

### RS-D17: EEA and the maritime EU ETS (20 November)
- No EEA-specific month effects in the main estimate: they cannot be identified, because no EEA economy is in a control pool.
- **Robustness:**
  - EEA economies dropped;
  - a within-EEA estimate (RS-D19).

### RS-D18: Explaining differences across economies, RQ3 (21 November)
- **Data:** non-control economies; outcome the window excess % (S1 and S2).
- **Regressors:** exposure and group indicators.
- **Estimation:** weighted least squares (weights = counterfactual) with HC3 standard errors.
- **Variants:** unweighted; without small economies.
- **Decomposition** by group and exposure tercile.
- Results are reported as associations, not causal effects.

### RS-D19: Within-EEA check (21 November)
- RS-D15 and RS-D16 applied within the EEA economies.
- **Control pool:** the bottom exposure tercile within the EEA, excluding HQ economies.

### RS-D20: Generalized synthetic control (Xu, 2017) on robust economies (21 November)
- **Units:** robust economies against each principle's control pool.
- **Factors:** factors from the control units; the number of factors (0–5) is chosen by leave-one-period-out cross-validation; same placebo dates.
- **Supplementary sensitivity** (added the same day, after the 0–5 grid chose its upper end, 5): the grid 0–8. The main results keep 0–5.

### RS-D21: Continuous-treatment difference-in-differences dropped (21 November)
Its role, how effects scale with exposure, is covered by RS-D18.

### RS-D22: Figures and tables (21 November)
- Six main figures, four main tables and supplementary material.
- The current numbering is in `README.md`.

### RS-D23: False-positive calibration of the robust rule (21 November)
- Each placebo date is treated in turn as a pseudo-shock, against the other four dates.
- The pseudo-robust counts are compared with the actual count. No re-estimation.
- **Stated asymmetry:** shorter windows and fewer runs than the actual rule.

### RS-D24: Article outline (21 November)
Sections, length and plain scientific style; claims follow the tables and figures.

### RS-D25: Supplementary numbering (21 November)
Numbering by first citation. Later updated; the current mapping is in `README.md`.

### RS-D26: Code licence (21 November)
- MIT licence for the code.
- Data are not redistributed; the README explains how to obtain and verify each raw file.

### RS-D27: Repository hygiene (21 November)
- Working files are kept out of the repository.
- Outputs must be byte-identical after a clean run (fixed row order; run times printed, not stored).
- The public history is one fresh commit of the final tree.

### RS-D28: Figure lettering (22 November)
- All text in figures is at least 8 pt at print width.
- Layouts may change; plotted values may not.

### RS-D29: Like-for-like comparison of the two principles (23 November; internal pre-submission review)
- **Reason:** the main residence series includes domestic voyages, while the main departure series covers international voyages only.
- **Added series:**
  - international voyages under residence (`RES_INT`), compared with international voyages under departure;
  - all voyages under departure (`TER_TOT`), compared with all voyages under residence.
- **Rules:** the same as for the main estimates (panels, anomaly scan, control pools, estimator, placebos).

### RS-D30: Pre-trend tests (23 November; internal pre-submission review)
Following Test 1 of Borusyak, Jaravel and Spiess (2024):
- **(a) Aggregate:** twelve pre-crisis month terms for the treated units, with a cluster-robust Wald test. Run for container ships, all cargo types and the non-control economies of each principle.
- **(b) Per unit:** robust economies and container ships, with Newey–West standard errors; a pre-trend is flagged at p < 0.05.

### RS-D31: Equal-length placebo inference (23 November; internal pre-submission review; supplementary)
- Rolling placebo dates with the same 23-month window as the main estimate.
- **Outputs:**
  - an equal-length version of the robust rule;
  - unit p-values from standardized placebo statistics;
  - Benjamini–Hochberg candidates at q = 0.10.
- The RS-D16 rule stays the main rule.

### RS-D32: Gross gains and losses against placebos (23 November; internal pre-submission review)
The actual gross gains and losses (S1) are compared with those at each rolling placebo date.

### RS-D33: Further robustness variants (23 November; internal pre-submission review)
- **R15 / W5:** the main estimates summed without December 2023.
- **R16:** stricter control pools.
- **RQ3:** each Red Sea economy left out in turn.
- **PPML at system level:** with the redefined simulation check (see Corrections).
- **Container ships:** the monthly path.

### RS-D34: Criterion for naming economies in the abstract (23 November; fixed before the results of RS-D29 to RS-D33 were seen)
An economy is named only if all of these hold:
- it is robust under RS-D16;
- it has no pre-trend flag under RS-D30(b);
- if it is an EEA economy, it is also robust in the within-EEA check.

### RS-D35: Title (23 November)
The title no longer speaks of a cost that someone bears. Replaced by RS-D39.

### RS-D36: Spain (23 November)
- No mechanism is proposed for Spain's departure-based gain without a verified source.
- Its within-EEA result is reported beside its main result.

### RS-D37: Public decision record (23 November)
- This file lists the decisions with dates, corrections and reasons.
- The article states that the placebo dates and the rule were fixed before the economy-level estimates were computed.

### RS-D38: Applying RS-D34 (23 November, after the results of RS-D29 to RS-D33)
- RS-D34 is applied as written (see Corrections).
- **Named:** Saudi Arabia and Mauritius (departure) meet all criteria.
- **Not named:** Azerbaijan also meets them but is not named, because the Caspian Sea has no open-sea link to Suez.
- **Abstract:** states the pattern for the Red Sea economies and the gross shift against placebos; after RS-D42(a) showed that the gross shift depends on a few economies, the gross-shift statement was removed from the abstract (RS-D41).
- **Results section:** reports every flagged economy with the size and sign of its pre-crisis deviation.
- **Comparing the principles:** rests on the all-voyages pair.

### RS-D39: Title (24 November; replaces RS-D35)
*How two accounting principles record shipping emissions from the Red Sea crisis* (12 words or fewer, as the journal requires).

### RS-D40: Article structure and format (24 November)
- The journal's section structure and formatting requirements are followed.
- Dataset references are marked as datasets.

### RS-D41: Estimand and wording (24 November)
- **Estimand:** deviations from a model-based counterfactual during the crisis period, not isolated causal effects of rerouting. Economy results are changes in recorded allocation, not physical movements of emissions.
- **Wording rules:**
  - Red Sea results refer to the four observed Red Sea economies, with the sum without Egypt beside them.
  - The residence headline uses the HQ group.
  - Azerbaijan and Kazakhstan are reported as negative controls.
  - Saudi Arabia's and Mauritius's status is stated separately under each inference method.

### RS-D42: Supplementary analyses after a second internal pre-submission review (24 November)
- **(a)** Gross shifts without Egypt, Saudi Arabia and Malaysia, singly and jointly.
- **(b)** Benjamini–Yekutieli beside Benjamini–Hochberg.
- **(c)** Family-wise calibration of the unit statistics.
- **(d) R17:** control pools without Gibraltar, Panama, the Bahamas and the Marshall Islands (hub, registry and bunkering economies).
- **(e)** RQ3 with the HQ group extended by Hong Kong, and by Hong Kong and Japan.
- **(f) W6:** container ships with the pre-crisis period starting 2021-07, with one placebo date; non-inferential.

All are supplementary; the main results are unchanged.

### RS-D43: Publication of the repository (25 November)
- **What:** code and derived outputs are published on GitHub under the MIT licence; raw data are not redistributed.
- **History:** the public history is one fresh commit.
- **Archive:** a Zenodo archive with a DOI follows after acceptance.
