# Locate the results supporting the manuscript

Evidence paths below are relative to the `dataset/` folder in the shared Zenodo package https://doi.org/10.5281/zenodo.24148495, not the software directory. Files under `evidence` retain their original project-relative locations. Historical identifiers such as `incident_macro`, `mixed_incident_macro`, `pr_auc`, and `row` are preserved in saved files; in the manuscript these correspond to fire-average, within-fire, average precision (AP), and equal fireline-unit weighting as applicable. Do not rename stored fields silently.

| Manuscript result | Authoritative saved material |
|---|---|
| Primary five-fold predictions | `evidence/data/processed/baseline_modeling_v1/oof_predictions/E_FULL_EXTENDED__row.parquet` |
| Complete primary Table II with 5,000-resample intervals | `evidence/outputs/table_ii_bootstrap_completion_v1/run_20261110T005511_936815Z/` |
| Annual forward-year predictions and historical unit baseline | `evidence/data/processed/forward_temporal_generalization_v1/FORWARD_TEMPORAL_PREDICTIONS_V1.parquet` |
| Alternative fixed models | `evidence/outputs/alternative_model_benchmark_v1/` and the combined predictions under `evidence/data/processed/alternative_model_benchmark_v1/` |
| Fixed LightGBM calibration | `evidence/outputs/fixed_primary_nested_calibration_v1/` |
| Tuned challenger models | `evidence/outputs/nested_challenger_gpu_v1/` and corresponding saved prediction files |
| Cutoff transfer | `evidence/outputs/lightgbm_temporal_decision_policy_v1/` |
| Observation-context comparison | `evidence/outputs/observation_process_proxy_sensitivity_v1/` |
| SHAP summaries | `evidence/outputs/frozen_model_interpretation_v1/` |
| Condition trees and frozen memberships | `evidence/outputs/08_condition_outcomes/08C_20260930T234354_724489Z_3a31ea/` |
| Unit-weighted condition-group fractions and sensitivity | `evidence/outputs/08_condition_outcomes/08D_20261001T002458_892164Z_f3e697/` |
| Matched local/shared models, logistic comparison, unit/fire baselines, and remaining diagnostics | `evidence/outputs/08_condition_outcomes/08E_20261105T211309_533108Z_9ff65f/` |

The complete Table II completion directory supersedes missing intervals in the original `primary_model_freeze_v1` table outputs. Both are retained to preserve provenance. Archived `.tex` snippets are historical output artifacts and may use the earlier manuscript layout; they are not the current AMS manuscript.

The eight displayed condition groups correspond to frozen leaf IDs 3, 4, 6, 7, 10, 11, 13, and 14 in that order. Main-paper percentages use unit weights in `frozen_rule_weighting_checks.csv`, scope `2023_2024`. The 08C frozen prediction file also includes two width-subset variants; filter `variant == 'condition_tree'` before reproducing the eight main groups.

For 08E, `(scheme, unit_uid)` is the prediction key. `five_fold` has 304,143 rows and `forward_year` has 255,547 rows. Do not pool both schemes together as independent examples. `p_baseline_unit` uses training-unit prevalence; `p_baseline_fire` uses the mean of training-fire Held fractions. The test weighting used to calculate a score is a separate choice. The saved comparison tables explicitly identify both models and weighting.

`reproduce_saved_results.py` independently checks the saved primary and 08E point estimates, 08E paired intervals, and annual/combined unit-weighted condition fractions. The optional primary-bootstrap calculation reproduces the 5,000 saved whole-fire draws. Historical alternative-model, calibration, SHAP, and cutoff outputs are included with their source notebooks, but the portable result script does not recompute every historical output in those stages. No model is retrained by either release verification script.
