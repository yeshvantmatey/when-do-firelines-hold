# Dependencies and reproducibility scope

Use a separate Python 3.12 virtual environment for release checks. Install
`requirements-verification.txt` to run `verify_release.py` and
`reproduce_saved_results.py`. The requirements state minimum package versions;
they are not a lockfile. `verification_environment.txt` records the environment
used for the existing saved-prediction checks.

The three portable figure redraws use the versions in
`requirements-figures.txt`. Their small scientific inputs are included in
`figures/inputs/`; no raw product downloads are required to redraw those figures.
`docs/FIGURE_REPRODUCTION.md` describes the provenance and interpretation of each
input. Installing Python packages requires package access, but the verification,
saved-result reproduction and portable redraw commands use local inputs only.

Historical extraction and training notebooks have additional dependencies and
intermediate-data requirements. `environment/RECORDED_RUN_VERSIONS.csv` preserves
versions recovered from saved scientific runs. The adjacent
`SAVED_VERSION_EVIDENCE.csv` identifies the evidence sources.
`CURRENT_IMPORTED_PACKAGE_VERSIONS.csv` reports the later packaging environment;
it must not be mistaken for the environment of every original run.

`audit/IMPORT_INVENTORY.csv` lists imports in the historical notebooks. Their
geospatial, GPU, GDAL and PROJ dependencies are not captured by a complete tested
environment lockfile. Consult `docs/HISTORICAL_CODE_GUIDE.md` before reconstructing
the original workflow. The retained release tables support saved-result checks,
but they do not replace every intermediate file expected by those notebooks.
