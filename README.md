# When Do Firelines Hold? Predicting Recorded Outcomes from Weather and Landscape Conditions

Code supporting *When Do Firelines Hold? Predicting Recorded Outcomes from Weather and Landscape Conditions*.

**Development version, 1.0.0-draft.** The versioned code release and shared Zenodo record are being prepared. Their links remain placeholders.

| Resource | Identifier |
|---|---|
| Public code repository | https://github.com/yeshvantmatey/when-do-firelines-hold |
| Paper code release | [GITHUB-RELEASE-URL] |
| Exact code commit | [GITHUB-COMMIT-SHA] |
| Shared dataset, saved results, complete analysis archive and code snapshot | [ZENODO-DOI] |

## What is included

- `notebooks/`: 46 historical analysis notebooks, with outputs and execution state cleared and workstation paths normalized.
- `verify_release.py`: checks the released dataset, prediction joins, fire-held-out folds, training-only baselines and current file hashes.
- `reproduce_saved_results.py`: reproduces saved prediction statistics, condition-group Held fractions and paired uncertainty calculations without fitting models.
- `figures/`: portable redraws for the study-extent map, real NIFC–NIROPS example and methods schematic, with small plotted inputs and reference outputs. An explicitly historical editorial renderer is also included.
- `requirements-verification.txt`, `requirements-figures.txt`, and `environment/`: dependency requirements and recorded version evidence.
- `docs/` and `audit/`: interpretation, reproduction limits, original source mappings and provenance.

The full retained dataset, selection audit, saved predictions and complete analysis archive are distributed through the shared Zenodo record. They are intentionally outside this Git repository. Small scientific inputs needed by the standalone figure redraws remain in `figures/inputs/`.

## Download and arrange the data

Download and extract the package from [ZENODO-DOI]. An example layout is:

```text
work/
  github_code/          # this repository
  zenodo/
    dataset/
      data/
      evidence/
    analysis_archive/
    code_snapshot/     # archived copy of the paper's code
```

The repository folder may have a different name. Supply the actual dataset directory with `--dataset-root`. The two core Parquet tables preserve 304,143 retained fireline units and the 572,200-candidate selection audit. The primary feature list contains 803 predictors; the additional archival fields must not all be used as model inputs.

## Verify and reproduce saved results

From the repository root, using Python 3.12 and a separate virtual environment:

```text
python -m pip install -r requirements-verification.txt
python verify_release.py --dataset-root ../zenodo/dataset --output ../verification_results
python reproduce_saved_results.py --dataset-root ../zenodo/dataset --primary-bootstrap --output ../reproduced_results
```

Choose new output directories outside the released dataset. The commands above assume the illustrated GitHub checkout layout. When running inside `zenodo/code_snapshot/`, use `--dataset-root ../dataset` instead. The default dataset location is a sibling `dataset/` directory, which also suits the archived snapshot.

Verification uses local files only. The result script checks primary-model estimates, 08E diagnostic comparisons and frozen condition groups. The `--primary-bootstrap` option also reproduces all 5,000 primary whole-fire bootstrap replicates and intervals. Predictions and group definitions remain fixed; no models are retrained. Results and full predictor definitions are indexed in `docs/RESULTS_GUIDE.md` and the Zenodo dataset dictionaries.

## Reproduce the added figures

```text
python -m pip install -r requirements-figures.txt
python figures/reproduce_study_extent.py --output ../redrawn_figures/study_extent
python figures/reproduce_nifc_nirops_example.py --output ../redrawn_figures/nifc_nirops_example
python figures/reproduce_schematic.py --output ../redrawn_figures/schematic
```

Each directory must be new. The standalone redraws use packaged small inputs and do not download data. `figures/regenerate_figures.ipynb` supplies the same commands in notebook form. See `docs/FIGURE_REPRODUCTION.md` for data meaning, source attribution, exact inputs and the limitations of historical editorial outputs.

## Scope of the historical notebooks

The original scientific workflow is preserved for inspection. It is not a one-command reconstruction of all raw geospatial data and fitted models. Historical training and extraction notebooks require intermediate geometries, trajectories, raster caches or model-table layouts that are not fully included. Configure `FIRELINE_PROJECT_ROOT` to a separate research workspace before running them. Do not rename the retained release table to impersonate an original intermediate table. `docs/HISTORICAL_CODE_GUIDE.md` explains these dependencies; its earlier audit statements are labeled as historical.

No operational reliability or causal fireline effect is established by the retrospective data. NIFC supplies recorded outcome labels; NIROPS provides timing evidence used in retrospective selection.

## Licensing and citation

Original software is licensed under MIT. Original scientific data, figures and documentation are licensed under CC BY 4.0 to the extent the contributors hold the relevant rights. Upstream data and third-party files retain their own terms. Read `LICENSE`, `LICENSE_SCOPE.md` and `THIRD_PARTY_NOTICES.md`; the software license does not relabel the bundled scientific data or public-domain boundaries.

`CITATION.cff` records the authors and local candidate version. Cite the named code release and the shared Zenodo record once their real links are available. The Zenodo snapshot should match the exact paper code version. Unassigned DOI and release links remain comments in citation metadata.

Authors: Yeshvant Matey, Raymond de Callafon and Ilkay Altintas. Research support: Google.org, for work at the Societal Computing and Innovation Lab at the San Diego Supercomputer Center. Generative AI tools assisted code development and documentation; the authors are responsible for the analysis and interpretation.

The shared Zenodo archive will preserve the code version supporting the paper. `.gitignore` excludes secrets, local environments, bulk data and generated outputs while retaining the packaged figure inputs. `.gitattributes` preserves file bytes across checkouts for snapshot integrity.
