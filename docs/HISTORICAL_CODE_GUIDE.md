> Historical audit of the earlier combined staging package. The present publication copies additionally replace local paths with configurable/project-relative paths and clear notebook execution state. Source hashes and unchanged-source statements below refer to the earlier snapshot. Use the current README and release manifest for the GitHub code folder and shared Zenodo package.

# Code guide

The code archive contains **46 selected research notebooks and two original scripts**. It preserves the scientific source for the retained cohort, primary model, alternative analyses, and 08A–E reviewer diagnostics. It is an archival source snapshot, not a tested portable pipeline from raw geospatial products to every paper result. The release-level verification and saved-result reproduction scripts are documented in the main README; the notebooks described here have separate external-input requirements.

## What was preserved

`code/NOTEBOOK_INDEX.csv` lists every source notebook considered, its selected/excluded status, role, selection reason, and saved evidence. The 52 omitted notebooks are superseded versions, development pilots, earlier acquisition attempts, or editorial manuscript-building iterations. Some earlier-numbered production notebooks are retained because later final notebooks read their outputs. A higher version number does not always replace all earlier processing.

The selected notebook cells, including code and Markdown, are unchanged. Only code-cell outputs, execution counts, notebook widget state, and execution-timing metadata were cleared in the archive copies. No original notebook or script was modified. Kernel and language metadata remain as historical records. The copies were parsed and compared with their originals; research cells were not executed during packaging.

`code/audit/SOURCE_SHA256.csv` gives original and archived file SHA-256 values, source-cell hashes, and counts of cleared outputs/execution counts. Whole-notebook hashes change because output clearing and JSON serialization change the file. Source-cell hashes match. The two selected scripts were copied byte for byte:

- `code/scripts/complete_table_ii_bootstrap.py`: completes Table II intervals from saved fixed out-of-fold predictions.
- `code/scripts/build_zenodo_core_v1.py`: original builder and validator of the two retained core tables.

These original scripts retain their original path assumptions. They are not substitutes for the separate release-level scripts.

## Scientific sequence

| Stage | Selected source | Dependency and interpretation |
|---|---|---|
| Source preparation | 01; 02b | Extract source archives and resolve mapped-record version history. The earlier 02 canonical table is explicitly superseded by 02b. The saved 01 report is only a one-byte placeholder; its presence is not evidence of a completed audit. |
| Temporal precursor | 03G v2; 03H v2 | Produce segmentation and the precursor cohort subsequently read by 03L. These remain required historical dependencies. |
| Corrected units and targets | 03L; 03M; 03N | Correct local geometry, audit weighted evidence, and freeze supported units and timing. The 03N cohort has 317,495 supported units; later clean-anchor modeling retains 304,143 units from 381 fires. |
| Fire approach | 04A v2; 04A v3 | V3 extends V2 approach inputs. V2 also supplies the raster-distance comparison in 08D. |
| Weather and terrain | 04B1 v2; 04C1 | Production HRRR features and 3DEP terrain/sample indexes. |
| LANDFIRE provenance and definition | 04D0; 04D1B v2; 04D1C v5 | Temporal vintage audit, independent provenance check, and frozen feature specification. |
| LANDFIRE resolved vintages | 04D1E v3; 04D1E v5 | V3 performs full extraction/recovery; V5 repairs final shard schemas without rerunning extraction. |
| LANDFIRE archived vintages | 04D1F v2 and v3; 04D1G v7; 04D1I v2 | Inventory/disambiguation, acquisition validation, and full extraction. V2/V3 inventory notebooks resolve different archive questions. |
| LANDFIRE consolidation | 04D1J | Consolidates all five retrospective vintages for final model-table assembly. |
| Modeling table and design | 05A; 05B | Assemble predictors and freeze incident-grouped outer/inner folds and weights. |
| Primary OOF model and freeze | 05C; 05C1; 05D; 05E; 05E1 | Fixed LightGBM OOF experiments, calibration/tuning audits, primary freeze, and incident-cluster uncertainty. The selected primary is fixed `E_FULL_EXTENDED`, ordinary row weighting, raw probabilities. |
| Table II and full-data fit | 05E2; 05F | Complete saved-prediction intervals; separately fit the full-data serialized model. The full-data fit is not a performance estimate. |
| Sensitivity and interpretation | 05G; 05H; both 05I notebooks; 05J | Observation-process sensitivity, forward-year evaluation, interpretation/input regimes, and results assembly. Both 05I files perform distinct analyses. |
| Alternative models | 06A; 06A v2; 06B; 06C | Fixed alternatives, runtime finalization, exploratory GPU challengers, and scenario-specific temporal threshold policies. These do not replace the frozen primary model. |
| Condition analyses | 08A; 08B; 08C; 08D; 08E | Recorded conditions, scale/selection, interpretable rules, robustness, and reviewer diagnostics. These retain their exploratory qualifications and frozen grouping rules. |
| Figure refresh | `08_series_paper_figure_refresh`; `08_series_condition_figure_publication` | Replot saved 08-series results. They do not train models or supply missing upstream inputs. |

This table is a dependency guide, not a promise that executing files alphabetically is sufficient. Notebooks also depend on saved checkpoints, schemas, intermediate outputs, and timestamped run folders.

## Matching source to saved runs

All five selected 08-series notebook fingerprints match the corresponding final, non-smoke manifests:

| Notebook | Saved run |
|---|---|
| 08A | `08A_20260930T220658_104767Z_614ae3` |
| 08B | `08B_20260930T224636_898345Z_38d03c` |
| 08C | `08C_20260930T234354_724489Z_3a31ea` |
| 08D | `08D_20261001T002458_892164Z_f3e697` |
| 08E | `08E_20261105T211309_533108Z_9ff65f` |

`code/audit/NOTEBOOK_MANIFEST_MATCHES.csv` records the hash algorithms and values. For 08A–D the saved algorithm hashes the JSON list of all cell source values. 08E hashes normalized Python ASTs plus non-code cell text and normalizes only the operational resume-path setting, matching the notebook's own algorithm. Output clearing preserves both kinds of source fingerprint.

Earlier notebook selection is supported by actual input references, saved build/configuration cards, manifests, and output locations identified in the notebook index. Most earlier stages do not have a saved notebook-source hash. Their artifact linkage is therefore weaker than the 08A–E exact-source matches; this archive does not invent such a guarantee.

## Runtime evidence

`code/environment/RECORDED_RUN_VERSIONS.csv` transcribes saved version evidence. `SAVED_VERSION_EVIDENCE.csv` identifies and hashes its sources: the baseline and alternative-model `SOFTWARE_VERSIONS_V1.csv` files and the five selected 08-series run manifests. The recorded primary-model environment includes Python 3.12.1, NumPy 2.5.2, pandas 3.0.5, scikit-learn 1.9.0, and LightGBM 4.7.0. The alternative-model record adds XGBoost 3.4.1, CatBoost 1.2.10, and Interpret 0.7.8. The 08-series manifests supply additional versions including PyArrow, Matplotlib, Shapely, and Joblib where recorded.

`CURRENT_IMPORTED_PACKAGE_VERSIONS.csv` separately lists versions observed in the packaging interpreter for imported third-party modules. It is not a historical environment lockfile and was not substituted for saved run records. `code/audit/IMPORT_INVENTORY.csv` lists imports by source, cell, and line. Geospatial/source reconstruction additionally uses packages such as GeoPandas, Pyogrio, PyProj, Rasterio, Shapely, Requests, S3FS/FSSpec, Xarray, and Zarr. The complete historical binary/GDAL/PROJ/CUDA environment was not preserved or reconstructed here. 06B contains GPU-oriented training assumptions. No new package installation or model fitting was performed to validate that path.

## Inputs and portability gaps

The two core tables are `data/retained_fireline_units.parquet` and `data/selection_audit.parquet`. They support a retained-cohort release and saved-result checks. They do not recreate every original raw source table, geometry shard, trajectory cache, or intermediate schema expected by these notebooks.

| Input family | Original expected locations/examples | Release limitation |
|---|---|---|
| Source products | `Fireline_QAQC_2017_2024/`, `NIROPS_2020_2024/`, extracted source geodatabases and polygons | Original raw products are not redistributed in this archive; obtain the cited source products separately before source reconstruction. |
| Original mapped-record population | `data/processed/fireline/fireline_qaqc_version_resolved.parquet` | The retained table and selection audit do not replace the full original geometry-bearing source population read by 08A/08B. |
| Unit reconstruction | `data/processed/fireline_dynamic_250m/` and `data/processed/fireline_corrected_local_250m_10m/` units, sample points, trajectories, evidence, and frozen/excluded cohorts | These substantial cached/intermediate inputs are not comprehensively packaged. In particular, 08E's manifest enumerates hundreds of trajectory files. |
| Feature extraction | Original approach, HRRR, 3DEP, and LANDFIRE feature products, rasters, downloaded archives, and block caches | Core predictors are retained, but extraction inputs and original intermediate schemas are not comprehensively packaged. Source services and download URLs may also change. |
| Model-table and design paths | `data/processed/modeling_table_assembly_v1/fireline_hold_modeling_master_v1.parquet`, original design files | Original names/layout differ from release core tables. A separate adaptation must verify schema, identifiers, feature order, and folds before any refit. Merely renaming a released table is not a validated adapter. |
| Saved evidence | Original `outputs/...` and prediction paths | Selected evidence is under `evidence/` with original relative paths below it. Unchanged notebooks generally expect the original project layout and do not automatically resolve this added prefix. |
| Figure/manuscript paths | `overleaf_revision_08_series_20261001/...` | Figure refresh notebooks retain historical manuscript-directory assumptions; publishing/manuscript assembly is outside this code snapshot. |

Most historical notebooks contain a hardcoded Windows project root. Others discover a root by checking for the original folders and expect their own source at `notebooks/<name>.ipynb`. The archival copies are under `code/notebooks/`; this intentionally preserves their source rather than silently changing the scientific code. Before rerunning an archival notebook, make a separate working copy, restore or explicitly map its expected inputs, configure its root, review output locations, and verify the relevant cohort/schema and grouping checks. Running directly against a live research workspace can write outputs or resume checkpoints.

Three inventories make those gaps reviewable:

- `LOCAL_PATH_INVENTORY.csv`: statically resolvable path assignments and path literals. Entries may be inputs, outputs, or directories; this is not a complete executable dependency graph. Runtime-generated paths and all indirect I/O cannot be resolved statically.
- `MANIFEST_INPUTS.csv`: explicit input references from the five final 08A–E saved manifests. Availability is recorded at audit time using the release's `evidence/<original-relative-path>` convention. It does not treat a renamed/merged core table as an identical original input.
- `ABSOLUTE_PATHS.csv`: hardcoded absolute path literals with source cell and line. Paths remain unchanged in source; they do not imply the same paths exist on another machine.

The audit timestamp is in `code/audit/ARCHIVE_AUDIT_SUMMARY.json`. `STATIC_PARSE_LIMITATIONS.csv` records any code cells that could not be parsed. Availability columns reflect that timestamp, not a future release modification.

## Source inspection and verification limits

The copied source was scanned for private-key markers, recognized token formats, credentials embedded in URLs, and credential-named literal assignments. No candidates were detected. `SECRET_PATTERN_SCAN.csv` records only locations and categories if matches occur and never stores matching values. This pattern scan is not a proof that arbitrary secrets cannot exist. Cleared notebook outputs are not included in the archival copies.

Checks completed for this snapshot: JSON parsing, Python AST parsing for static inventory, unchanged source-cell comparison, original/copy SHA-256 capture, original-file rehash after copying, and the five recorded 08A–E source-fingerprint comparisons. Research notebooks were not rerun, all historical outputs were not regenerated, and geospatial acquisition/training reproducibility was not tested.

`code/archive_tools/build_archival_snapshot.py` records the packaging procedure. It is a source-workspace packaging utility and expects the original `notebooks/`, `scripts/`, and saved outputs outside the staged release. It is not a standalone consumer reproduction script. No license was chosen and no upload or publication was performed by this procedure.
