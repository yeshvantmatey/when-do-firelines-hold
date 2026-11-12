# Third-party data and software notices

The project licenses cover original contributions only. Source datasets, public-domain material, third-party software, templates, and their existing notices retain the terms described below. Keep source metadata alongside any redistributed subsets. The project does not imply endorsement by a source agency, the dataset authors, or the American Meteorological Society.

## NIFC fireline engagement archive

Source: Arkowitz, A. P.; Ritter, S. M.; Thompson, M. P.; Young, J. D.; Pietruszka, B. M.; and Calkin, D. E. (2025), *Fireline engagement from the National Interagency Fire Center Feature Service from 2017–2024*. USDA Forest Service Research Data Archive. <https://doi.org/10.2737/RDS-2025-0011>.

The published metadata states that the government-funded data may be used without additional permissions or fees and requests citation of the source dataset in publications, presentations, and research products. Access constraints are listed as none. The original metadata ZIP is retained with the shared dataset evidence. Our retained analytical tables and figure subsets have been selected and transformed; they are not the complete, unmodified source archive.

## Curated NIROPS perimeter archive

Source: Magstadt and colleagues (2026), *A high spatial resolution daily fire perimeter progression dataset for wildfires in the Western United States: 2020–2024*, Mendeley Data, version 1. <https://doi.org/10.17632/95rj5d379g.1>.

The source record specifies CC BY 4.0: <https://creativecommons.org/licenses/by/4.0/>. Preserve the source attribution and license, and identify modifications. The project selected observations and fireline units, calculated timing and approach features, and prepared figure subsets. Included NIROPS-derived subsets therefore do not represent an unchanged copy of the complete source dataset.

## NOAA HRRR forecasts

Source and archive: <https://registry.opendata.aws/noaa-hrrr-pds/>.

NOAA's archive terms permit public reuse and request attribution for use or redistribution of unaltered NOAA data. Modified data must not be described as original, unaltered NOAA data, and use must not imply NOAA endorsement or affiliation. The project contains derived forecast predictors and summaries. Keep the NOAA source credit and identify those transformations.

## USGS 3DEP elevation

Source: <https://www.usgs.gov/3d-elevation-program>.

USGS describes 3DEP products as available without use restrictions. USGS-authored or produced data are generally in the U.S. public domain; preserve any product-specific notices and third-party exceptions. Credit USGS for the elevation source. The project contains derived terrain summaries rather than a complete 3DEP redistribution.

USGS credit guidance: <https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits>.

## LANDFIRE vegetation and fuels products

Source: <https://landfire.gov/data>.

LANDFIRE's *Definitions, Quality, and Standards Annual Report*, version 3.0 (July 2026), describes released LANDFIRE data as freely available and in the public domain. Preserve product metadata and source attribution. This statement concerns the released LANDFIRE products used here; it does not assert rights over all underlying data privately contributed to LANDFIRE.

The project contains derived vegetation, fuel, and canopy summaries. Product vintages, scaling, spatial sampling, and historical-availability qualifications remain documented in the dataset dictionaries and provenance records.

Report: <https://www.landfire.gov/data-downloads/documents/LF_Definitions_Quality_and_Standards_Annual_Report.pdf>.

## U.S. Census Bureau cartographic boundaries

The study-extent figure uses the 2023 state cartographic boundary file at 1:20,000,000 scale. Source: <https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_state_20m.zip>.

The bundled boundary metadata permits use in products and publications with acknowledgement of the Census Bureau. Retain that metadata and credit the Bureau. The boundary data provide small-scale display context; their metadata cautions against using the generalized shapes for area or perimeter calculations, geocoding, or precise geographic relationships. The project does not treat those boundaries as measurements of fireline or fire geometry.

TIGER/Line is a registered trademark of the U.S. Census Bureau. Its use here identifies the source data and does not imply endorsement or provide a proprietary product name.

## AMS LaTeX support files

The American Meteorological Society's `ametsocV6.2.cls` carries copyright 2021 American Meteorological Society and is distributed under LPPL 1.3 or later. Its notice defines the work as `ametsocV6.2.cls`, `ametsocV6.bst`, `amsdocsV6.2.pdf`, and `AMS_RefsV6.pdf`. The complete four-file work is included unchanged in `analysis_archive/` of the related shared Zenodo package (https://doi.org/10.5281/zenodo.24148495). The AMS support work is not distributed in this GitHub repository.

The bibliography style `ametsocV6.bst` retains its copyright notice for Patrick W. Daly (1994–2005), its 2021 update attribution, and its stated LPPL version 1 or later terms. The notices are preserved in all included copies, including historical snapshots. The supplied LPPL 1.3c text is at `LICENSES/LPPL-1.3c.txt`; the upstream license page is <https://www.latex-project.org/lppl/>.

The project's MIT and CC BY 4.0 licenses do not relicense those AMS support files. Scientific report content authored for this study is separately covered by CC BY 4.0 as specified in `LICENSE_SCOPE.md`.

## External software dependencies

NumPy, pandas, PyArrow, scikit-learn, LightGBM, Matplotlib, GeoPandas, and other dependencies are identified in the environment and requirements files. They are installed separately and retain their own licenses. The project license is not a license grant for an external dependency's implementation.

License-source URLs and source notice checks were reviewed during release preparation on 11 November 2026. No upload or publication is implied by this notice.
