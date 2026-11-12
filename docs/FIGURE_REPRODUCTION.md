# Reproduce the added manuscript figures

The `figures/` folder adds the study-extent map, real NIFC–NIROPS example, and methods schematic sources omitted from the earlier code snapshot. Portable adapters read packaged inputs and require a new output directory. No models are fitted and no released inputs are overwritten. The plotting definitions, recorded outcomes, distances, coordinates, and selection checks remain unchanged.

## Installation and commands

Use Python 3.12 and install the tested figure dependencies from the code-release folder:

```text
python -m pip install -r requirements-figures.txt
python figures/reproduce_study_extent.py --output ../../redrawn_figures/study_extent
python figures/reproduce_nifc_nirops_example.py --output ../../redrawn_figures/nifc_nirops_example
python figures/reproduce_schematic.py --output ../../redrawn_figures/schematic
```

Each output directory must be new and outside the released code, dataset, and analysis-archive folders. The scripts refuse existing output directories. `figures/regenerate_figures.ipynb` provides the same three redraws in a notebook. Set its output root before running. Installation downloads dependencies; the redraw scripts themselves do not download data or call external services.

## Packaged inputs and meaning

| Figure | Inputs and interpretation |
|---|---|
| Study extent | Saved `fire_locations_and_sizes.csv` with 381 fire-level representative locations and counts summing to 304,143 retained fireline units. Representative locations are means of unit longitude and latitude, not ignition locations or fire-perimeter centroids. Census state boundaries provide geographic context. |
| NIFC–NIROPS example | Two retained 250 m fireline units from Deep Creek Canyon (2021); seven NIROPS perimeters; 22 saved checked positions; 154 position-by-observation signed distances; source firelines for context; and the 261 retained-unit membership records for the example fire. Geometry-bearing Parquet extracts preserve the original analysis CRS and coordinates. The original geographic GeoJSON extracts are also included. |
| Methods schematic | Numerical and drawing definitions extracted from notebook 07D. The figure illustrates the definitions and sampling rules; its shapes are not observed fire perimeters. It needs no empirical input file. |

For the example figure, NIFC supplies the outcome labels. NIROPS supplies timing and compatibility evidence, not independent label validation. The signed raster distances are capped at -251/+251 m, so the endpoint values are not exact measured distances. Times in the packaged trajectory CSV use ISO 8601 UTC. The original trajectory array used microseconds since epoch despite its `times_ns` field name. The display uses the original 11 checked positions on each example unit. The 50 m band drawn around vector perimeters is illustrative; the study's stored evidence used a 25 m grid.

The seven observations run from 16 June to 1 July 2021. The first approach/crossing interval spans 18.5 hours. The final context perimeter is the last NIROPS observation, not the NIFC final fire perimeter. Source fireline records shown in gray need not represent entire constructed firelines.

## Sources and attribution

- Fireline source: Arkowitz and colleagues, USDA Forest Service Research Data Archive, DOI `10.2737/RDS-2025-0011`.
- NIROPS source: Magstadt and colleagues, Mendeley Data version 1, DOI `10.17632/95rj5d379g.1`.
- State boundaries: U.S. Census Bureau, 2023 cartographic boundary files, scale 1:20,000,000. The original ZIP and extracted files are included under `figures/inputs/study_extent/`. Source URL: <https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip>.

The figure-source provenance records and `source_manifest.json` identify original project-relative paths and hashes. The relative source paths document provenance and are not promises that all upstream caches are bundled. Runtime adapters use only the plotted inputs packaged in `figures/inputs/`.

## Historical editorial source

`figures/original_sources/build_editorial_assets.py` preserves the earlier editorial builder. Its corresponding saved CSV inputs are under `figures/inputs/editorial_historical/`. To redraw the historical outputs safely:

```text
python figures/reproduce_editorial_historical.py --output ../../redrawn_figures/editorial_historical
```

The historical builder generates four figures and six table snippets. Its forward-year panel uses **fire-average Brier score**, its regime figure describes the earlier surrogate analysis, and its primary table retains the originally missing intervals. Those outputs must not replace the later pooled-results figure, direct condition-group analysis, or completed primary-performance table. The current pooled forward-year and condition plotting sources are the already archived `notebooks/08_series_paper_figure_refresh.ipynb` and `notebooks/08_series_condition_figure_publication.ipynb`. The baseline-comparison figure comes from the 08E saved-result work. Their original path and dependency limitations are described in the general code guide.

Historical notebook copies in `figures/original_sources/` have outputs and execution state removed. They are provenance sources, not the portable entry points. Use the `reproduce_*.py` scripts or the new regeneration notebook for these additions.

## Verification

All four portable scripts completed successfully against packaged inputs. The real NIFC–NIROPS and schematic PNGs were pixel-identical to the retained reference PNGs. The study-extent redraw retained the 381 coordinates, counts, legends, bounds, and assertions. Its tight image bounds differed by three horizontal pixels and one vertical pixel in the tested environment; the figure was visually reviewed. PDF binary equality is not required because generation metadata can differ. The original reference files remain under `figures/reference_outputs/`.

`figures/validation.json` records tested package versions and comparison results. No scientific analysis or model training was rerun for these figure additions.
