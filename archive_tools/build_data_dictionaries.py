"""Build release documentation from immutable local tables and recorded specifications.

Run from the repository root with .venv/Scripts/python.exe. Writes only beside this file.
"""
import os  # Configurable project root for the public release.
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CORE = ROOT / 'zenodo_upload_v1'
MASTER = 'data/processed/modeling_table_assembly_v1/fireline_hold_modeling_master_v1.parquet'
MANIFEST = 'outputs/modeling_table_assembly_v1/MODELING_COLUMN_MANIFEST_V1.csv'
LF_DICT = 'outputs/landfire_feature_architecture_v5/LANDFIRE_FEATURE_DICTIONARY_V5.csv'
SCHEMA = json.loads((CORE / 'validation/column_schemas.json').read_text())
ALLOW = json.loads((CORE / 'validation/primary_predictor_columns.json').read_text())
# Read the immutable original build inputs above. The staged release relocates
# this allowlist to the following package-relative location.
PACKAGE_ALLOWLIST = 'data/primary_predictor_columns.json'
ALLOW_POS = {n:i+1 for i,n in enumerate(ALLOW)}

def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

MAN = {x['column']:x for x in csv_rows(ROOT / MANIFEST)}
LF = {x['feature']:x for x in csv_rows(ROOT / LF_DICT)}
spec = importlib.util.spec_from_file_location('core_builder',ROOT / 'scripts/build_zenodo_core_v1.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
SOURCES = builder.SOURCES
NB = {
    'approach':'notebooks/04A_v3_extended_exact_approach.ipynb',
    'approach_v2':'notebooks/04A_v2_dynamic_approach_features.ipynb',
    'hrrr':'notebooks/04B1_v2_HRRR_production_features.ipynb',
    'terrain':'notebooks/04C1_3DEP_terrain_production.ipynb',
    'landfire':'notebooks/04D1C_v5_LANDFIRE_feature_architecture.ipynb',
    'source':'notebooks/08B_original_firelines_scale_and_selection.ipynb',
    'evidence':'notebooks/03M_unit_evidence_rule_audit.ipynb',
    'frozen':'notebooks/03N_freeze_corrected_ml_cohort.ipynb',
}
UPSTREAM = {x['source']:x['path'].replace((os.environ.get("FIRELINE_PROJECT_ROOT", ".") + '/'),'').replace('\\','/') for x in csv_rows(ROOT / 'outputs/modeling_table_assembly_v1/SOURCE_SCHEMA_INVENTORY_V1.csv')}
DEFAULT_MISSING = 'Null/NaN is preserved from the source; it is not a numeric zero. No imputation is applied in the release.'

# Definition, units, semantic evidence, unresolved details. Empty units means not applicable.
D = {}
def define(name,definition,units='',evidence='scripts/build_zenodo_core_v1.py',unresolved=''):
    D[name]=(definition,units,evidence,unresolved)

define('unit_uid','Unique corrected fireline-unit identifier; join key between the two tables.','identifier',unresolved='Identifier construction/versioning is not specified by the core release builder; treat as an opaque key.')
define('_irwin_norm','Normalized incident identifier used to group units and hold entire incidents out of training.','identifier',unresolved='Exact upstream normalization procedure is not restated in the release builder; preserve stored identifier.')
define('IncidentName','Incident name retained from source metadata.','text')
define('Year','Study incident year; released values cover 2020 through 2024.','calendar year')
define('_engagement_norm','Normalized outcome category: Held or Burned Over. Outcome-derived metadata; never a predictor.','category')
define('hold_label','Conditional hold outcome: 1 = Held; 0 = Burned Over. The labels describe engaged candidate units, not all recorded firelines.','binary label')
define('prediction_anchor_utc','Prediction time: earliest supported challenge-interval start, using corrected timing; not the dominant interval start.','UTC timestamp')
define('prediction_anchor_idx','Zero-based NIROPS observation index of the earliest supported challenge-interval start.','index',NB['approach_v2'])
define('operational_anchor_clean','True when a prediction anchor is available and no sampled unit point is already inside the fire at that anchor.','boolean',NB['approach_v2'])
define('prediction_t0_any_inside','True if at least one unit sample has negative cached signed fire distance at prediction time.','boolean',NB['approach_v2'])
define('longitude','Longitude of unit geometry centroid used for HRRR extraction, transformed to EPSG:4326.','degrees east',NB['hrrr'])
define('latitude','Latitude of unit geometry centroid used for HRRR extraction, transformed to EPSG:4326.','degrees north',NB['hrrr'])
define('_geom_hash','Stored source-record geometry hash; combined with _irwin_norm to identify an original source record.','identifier',unresolved='Hash algorithm/canonicalization is not specified by the release builder; the hash is not geometry.')
define('source_record_key','Parent source-record identifier: _irwin_norm + "|" + _geom_hash. Several corrected units may share this key.','identifier')
define('actual_line_length_m','Actual corrected unit line length, conserved by the summed sample-length weights; distinct from full parent-record length.','m',NB['evidence'])
define('FeatureCategory','Original recorded fireline feature category joined from the source-record audit.','category',unresolved='External source category codebook is not bundled; preserve the recorded category verbatim.')
define('StrategicLineType','Original recorded strategic-line-type attribute joined from the source-record audit.','category',unresolved='External source category codebook is not bundled; preserve the recorded category verbatim.')
define('LineWidthFeet','Reported source-record line width in feet; unfiltered, and potentially missing, zero, negative or above the review threshold.','ft',NB['source'])
define('reported_width_m','Reported source-record line width converted to metres: LineWidthFeet * 0.3048.','m')
define('screened_width_m','Reported width converted to metres only for finite 0 < LineWidthFeet <= 300; other values are null. The 300 ft bound is a review trigger, not a physical feasibility limit.','m')
define('width_status','Width classification: Missing; Non-numeric; Nonfinite; Negative; Zero; Positive, at or below review flag; Positive, above review flag. Review flag = 300 ft.','category',NB['source'])
define('source_record_geodesic_length_m','Full parent source-record geodesic geometry length from the 08B audit field geodesic_length_m; may be shared by multiple units.','m')
define('outer_fold','Saved incident-held-out cross-validation assignment, integers 0 through 4; every unit from one incident has the same fold.','fold index')

define('local_fire_to_line_distance_geom_m','Shortest geometric distance from the observed fire geometry at the anchor to the corrected unit geometry.','m',NB['approach_v2'])
define('approach_azimuth_deg','Shortest-vector azimuth from the observed fire geometry toward the line; clockwise from north, modulo 360.','degrees',NB['approach_v2'])
define('fireline_orientation_deg','Principal-axis orientation of line vertices, clockwise from north modulo 180.','degrees',NB['approach_v2'])
define('approach_vs_line_angle_deg','Acute angle between approach azimuth and principal-axis line orientation: min(d, 180-d), d = abs(approach modulo 180 - orientation).','degrees',NB['approach_v2'])
define('approach_direction_reliable','True when shortest fire-to-line distance is finite and at least 25 m and approach azimuth is finite.','boolean',NB['approach_v2'])
define('exact_has_previous_observation','True when both anchor and immediately preceding NIROPS observation times exist.','boolean',NB['approach'])
define('exact_previous_interval_hours','Elapsed time from immediately preceding NIROPS observation to the anchor observation.','h',NB['approach'])
define('exact_history_observation_count','Number of available NIROPS observations among anchor and up to three preceding observations.','count',NB['approach'])
define('exact_history_span_hours','Hours from earliest available observation in the four-observation history to anchor.','h',NB['approach'])
define('exact_history_any_cached_inside','Whether any finite cached-inside fraction in the observation history is positive; upstream code returns false if no finite fractions exist.','boolean',NB['approach'])
define('exact_approach_rate_available','True if anchor is clean, a previous observation exists and last mean approach rate is nonmissing.','boolean',NB['approach'])
define('exact_positive_last_mean_approach','True if last mean approach rate is greater than zero; comparison with a missing rate yields false in upstream code.','boolean',NB['approach'])
define('exact_eta_last_mean_available','True if uncapped last-interval mean ETA is nonmissing.','boolean',NB['approach'])

define('primary_extended_init_utc','Latest primary 00/06/12/18 UTC HRRR extended cycle initialized at least 3 h before prediction time under an assumed delivery delay; actual delivery times were not verified.','UTC timestamp',NB['hrrr'])
define('hrrr_selected_init_utc','Selected archived HRRR cycle after eligible older-cycle fallback, initialized at least 3 h before prediction time under an assumed delivery delay; actual delivery times were not verified.','UTC timestamp',NB['hrrr'])
define('hrrr_fallback_steps','Number of older six-hour extended-cycle steps taken from primary cycle to selected cycle.','count',NB['hrrr'])
define('hrrr_actual_store_leads','Number of hourly forecast leads available in the selected archive run.','count',NB['hrrr'])
define('hrrr_weather_available','Selected archived run supplies required variables and reaches prediction time; does not guarantee all later horizons are available or verify actual delivery by prediction time.','boolean',NB['hrrr'])
define('hrrr_failure_reason','Saved extraction/fallback failure reason; null in successfully processed groups.','text',NB['hrrr'])
define('adaptive_eta_source','Selected ETA estimator: history median first, then last-interval median; otherwise unavailable.','category',NB['hrrr'])
define('adaptive_eta_raw_h','Uncapped adaptive ETA selected from exact_eta_history_median_h, falling back to exact_eta_last_median_h.','h',NB['hrrr'])
define('adaptive_eta_query_h','Adaptive ETA clipped to the interval 1 to 18 hours for forecast querying.','h',NB['hrrr'])
define('hrrr_forecast_age_at_t0_h','Prediction anchor minus selected HRRR initialization time.','h',NB['hrrr'])
define('hrrr_gust_sentinel_cleaned_any','True when at least one negative gust-derived field was replaced with missing during saved-table cleanup.','boolean',NB['hrrr'])
define('hrrr_gust_sentinel_cleaned_count','Number of negative gust-derived fields replaced with missing for this unit.','count',NB['hrrr'])
define('terrain_direction_valid','True when approach_direction_reliable is true (missing treated as false) and approach azimuth is finite.','boolean',NB['terrain'])
define('terrain_block_id','Identifier of terrain extraction block; computational provenance only.','identifier',NB['terrain'])
define('terrain_dem_patch_valid_fraction','Fraction of finite elevation pixels in the entire processing DEM patch, shared by units in that block.','fraction',NB['terrain'])
define('terrain_source_tile_ids','Semicolon-separated identifiers of source 3DEP tiles used in the processing patch.','text',NB['terrain'])
define('terrain_block_runtime_s','Elapsed processing time of the extraction block, copied to its units.','s',NB['terrain'])
define('terrain_line_valid_fraction','Arc-length-weighted fraction of line sample positions with finite elevation.','fraction',NB['terrain'])
define('terrain_centroid_elevation_m','3DEP elevation sampled at the unit centroid.','m',NB['terrain'])
define('terrain_cross_slope_tangent_mean','Arc-length-weighted mean terrain gradient projected onto (cos(approach azimuth), -sin(approach azimuth)) in east/north coordinates.','dimensionless',NB['terrain'])

for name,desc in {
 'sample_points':'Total number of sample points contributing to unit evidence.',
 'supported_points':'Number of points classified temporally_supported.',
 'conflict_points':'Number of points classified trajectory_conflict.',
 'insufficient_points':'Number of points classified insufficient_temporal_evidence.'}.items():
    define(name,desc,'count',NB['evidence'])
for status,point in [('support','temporally_supported'),('conflict','trajectory_conflict'),('insufficient','insufficient_temporal_evidence')]:
    define(f'weighted_{status}_length_m',f'Sum of sample-length weights for points classified {point}; each weight is geometry-part length divided by sample count in that part.','m',NB['evidence'])
    define(f'weighted_{status}_fraction',f'weighted_{status}_length_m divided by total sample-length weight; denominator reconstructs actual_line_length_m.','fraction',NB['evidence'])
define('unit_evidence','Saved original 03L unit-level evidence category: temporally_supported, trajectory_conflict or insufficient_temporal_evidence; this is not the later weighted support-stage decision.','category',NB['evidence'])
define('unit_diagnostic_reason','Saved original 03L explanation of unit_evidence; labels identify supported crossings/approaches, point conflicts or absence of support.','category',NB['evidence'])
define('support_stage_pass','Saved support/conflict-stage pass: weighted support fraction >= 0.10 and, for Held units, weighted conflict fraction == 0 (validation tolerance 1e-12).','boolean')
define('support_stage_reason','Saved support/conflict-stage reason: included or first applicable support/conflict exclusion.','category')
define('has_supported_challenge_interval','Saved frozen-cohort indicator that a supported challenge interval exists.','boolean')
define('challenge_timing_confident','Saved frozen-cohort indicator that dominant supported-interval weight fraction is at least 0.50 (tolerance 1e-12); kept separately from interval existence.','boolean',NB['frozen'])
define('timing_stage_pass','Saved dynamic_timing_eligible: supported interval exists and dominant interval weight fraction >= 0.50 (validation tolerance 1e-12).','boolean')
define('prediction_anchor_available','Saved flag indicating that an earliest-supported prediction anchor could be constructed.','boolean')
define('clean_anchor_stage_pass','Saved operational_anchor_clean flag; retained membership requires this flag after support and timing stages pass.','boolean')
define('retained','True for units present in retained_fireline_units; false for excluded candidates.','boolean')
define('first_exclusion_stage','First failed stage in order support_conflict, timing, prediction_time; null for retained units.','category')
define('first_exclusion_reason','First applicable exclusion reason, using saved support reasons and derived timing/prediction-time reasons; does not establish that later criteria passed.','category')
define('first_exclusion_reason_origin','saved_reason for support/conflict exclusions; derived_from_saved_flags for timing and prediction-time exclusions; null for retained units.','category')
define('earliest_supported_interval_start_utc','Corrected earliest start timestamp among supported challenge intervals, copied from frozen-cohort *_timing field.','UTC timestamp')
define('latest_supported_interval_end_utc','Corrected latest end timestamp among supported challenge intervals, copied from frozen-cohort *_timing field.','UTC timestamp')
define('dominant_supported_interval_start_utc','Corrected start of supported interval carrying greatest total sample-length weight.','UTC timestamp')
define('dominant_supported_interval_end_utc','Corrected end of supported interval carrying greatest total sample-length weight.','UTC timestamp')
define('dominant_interval_hours','Elapsed hours between corrected dominant supported interval start and end.','h')
define('supported_event_span_hours','Elapsed hours from earliest supported interval start to latest supported interval end.','h')
define('supported_interval_count','Count of distinct supported observation-index intervals.','count',NB['evidence'])
define('dominant_interval_weight_fraction','dominant_supported_weight_m divided by total_supported_event_weight_m.','fraction')
define('total_supported_event_weight_m','Total sample-length weight assigned to supported challenge events with valid start/end indices.','m',NB['evidence'])
define('dominant_supported_weight_m','Sample-length weight in the dominant supported interval; ties are resolved by earliest end index, then earliest start index.','m',NB['evidence'])

METRIC_LABELS = {'mean':'weighted mean','median':'weighted median','p10':'weighted 10th percentile','p90':'weighted 90th percentile','min':'minimum','max_sample':'maximum at sampled positions'}
WEATHER = {
 'u10_grid_mps':('10 m wind grid-x component','m/s'), 'v10_grid_mps':('10 m wind grid-y component','m/s'),
 'u10_earth_east_mps':('10 m wind eastward Earth-coordinate component','m/s'), 'v10_earth_north_mps':('10 m wind northward Earth-coordinate component','m/s'),
 'wind10_speed_mps':('10 m wind speed, hypot(eastward,northward)','m/s'), 'gust_mps':('gust speed','m/s'),
 't2_c':('2 m air temperature converted from kelvin by subtracting 273.15','degrees C'), 'rh2_pct':('2 m relative humidity','percent'),
 'wind10_toward_approach_mps':('wind component east*sin(azimuth) + north*cos(azimuth), along fire-to-line approach','m/s'),
 'wind10_cross_approach_mps':('wind component -east*cos(azimuth) + north*sin(azimuth), transverse to approach','m/s')}

def horizon(tag):
    if tag=='t0': return 'prediction time'
    if tag.startswith('p'): return f'{tag[1:-1]} h after prediction time'
    return f'{tag[3:]}% of adaptive_eta_query_h after prediction time'

def resolve(name):
    if name in D: return D[name]
    if name in LF:
        f=LF[name]
        definition=f"LANDFIRE {f['product']}; region {f['region']}; statistic {f['statistic']}. {f['description']}"
        return definition,f['units'],LF_DICT,''
    m=re.fullmatch(r'exact_(t0|tm[123])_(.+)',name)
    if m:
        tag,metric=m.groups(); when='at anchor observation' if tag=='t0' else f'at {tag[2:]} observation(s) before anchor (not a fixed hourly lag)'
        if metric.startswith('exact_'):
            stat=metric.split('_')[1]; desc=f"Arc-length-{METRIC_LABELS[stat]} of exact sample-point distance to the NIROPS fire-geometry boundary {when}."; units='m'
        elif metric=='cached_inside_fraction': desc=f'Arc-length-weighted fraction with negative cached signed distance {when}.'; units='fraction'
        elif metric=='sample_points': desc=f'Number of line sample points used {when}.'; units='count'
        elif metric=='weight_sum': desc=f'Sum of represented line-length sample weights {when}.'; units='m'
        elif metric=='observation_index': desc=f'Zero-based NIROPS observation index {when}.'; units='index'
        else: desc=f'UTC NIROPS observation time {when}.'; units='UTC timestamp'
        return desc,units,NB['approach'],''
    m=re.fullmatch(r'exact_last_(mean|median|p10|min)_approach_rate_m_per_h',name)
    if m: return f'(Previous-observation {m[1]} distance minus anchor {m[1]} distance) / previous interval hours; positive values indicate approach.','m/h',NB['approach'],''
    m=re.fullmatch(r'exact_history_(mean|median|p10)_(approach_rate_m_per_h|trend_r2)',name)
    if m:
        desc=f'Ordinary least-squares fit of {m[1]} distance versus observation time across up to four observations: '
        return desc+('negative slope; positive values indicate approach.' if m[2].startswith('approach') else 'coefficient of determination; constant distance yields 1.'),('m/h' if m[2].startswith('approach') else 'dimensionless'),NB['approach'],''
    m=re.fullmatch(r'exact_eta_(last|history)_(mean|median|p10)_h(?:_cap(18|48))?',name)
    if m:
        return f"Estimated time to arrival: max(anchor {m[2]} distance,0) / {m[1]} {m[2]} approach rate; missing for nonfinite inputs or nonpositive rate."+(f' Capped at {m[3]} h.' if m[3] else ''),'h',NB['approach'],''
    m=re.fullmatch(r'hrrr_(t0|p[0-9]+h|eta[0-9]+)_(lead_h|relative_h|valid_time_error_min|available)',name)
    if m:
        tag,kind=m.groups(); when=horizon(tag)
        choices={
          'lead_h':(f'Rounded whole-hour forecast lead from selected initialization for requested {when}.','h'),
          'relative_h':(f'Requested offset from prediction time: {tag[3:]}% of adaptive_eta_query_h.','h'),
          'valid_time_error_min':(f'Selected valid time minus requested {when}; signed rounding error.','min'),
          'available':(f'True if the saved 2 m temperature is finite at {when}.','boolean')}
        return *choices[kind],NB['hrrr'],''
    m=re.fullmatch(r'hrrr_(.+)_(t0|p[0-9]+h|eta[0-9]+)',name)
    if m and m[1] in WEATHER:
        desc,units=WEATHER[m[1]]
        return f'HRRR forecast {desc}, bilinearly sampled at unit centroid for the nearest hourly lead to {horizon(m[2])}.',units,NB['hrrr'],''
    m=re.fullmatch(r'hrrr_window_0_(6h|12h|18h|eta)_(.+)',name)
    if m:
        end='adaptive_eta_query_h' if m[1]=='eta' else m[1]
        field=m[2]
        prefix=f'Across available unique rounded hourly forecast leads from prediction time through {end}: '
        if field=='n_hours': return prefix+'count of selected leads (may be incomplete window).','count',NB['hrrr'],''
        s=re.fullmatch(r'(t2_c|rh2_pct)_(mean|max|min)',field)
        if s: var,stat=s.groups(); desc,units=WEATHER[var]
        else:
            s=re.fullmatch(r'(wind10_speed|gust|toward|cross)_(mean|max|abs_max)_mps',field)
            if not s: raise ValueError(name)
            var,stat=s.groups(); var={'wind10_speed':'wind10_speed_mps','gust':'gust_mps','toward':'wind10_toward_approach_mps','cross':'wind10_cross_approach_mps'}[var]; desc,units=WEATHER[var]
        return prefix+f'{stat.replace("_"," ")} of {desc}, ignoring NaN inputs.',units,NB['hrrr'],''
    m=re.fullmatch(r'terrain_context_(100|250|500)m_(.+)',name)
    if m:
        descriptions={'elevation_mean_m':('mean elevation','m'),'elevation_std_m':('elevation standard deviation','m'),'relief_m':('maximum minus minimum elevation','m'),'slope_mean_deg':('mean slope','degrees'),'slope_max_deg':('maximum slope','degrees'),'valid_fraction':('finite DEM pixel fraction','fraction'),'tpi_m':('centroid elevation minus context mean elevation','m')}
        desc,units=descriptions[m[2]]
        return f'3DEP {desc} in the square context window of nominal {m[1]} m half-width around unit centroid.',units,NB['terrain'],''
    m=re.fullmatch(r'terrain_(elevation|slope|approach_slope)_(mean|median|p10|p90|max_sample)_(m|deg)',name)
    if m:
        quantity={'elevation':'3DEP elevation','slope':'terrain slope','approach_slope':'signed slope along approach direction, degrees(arctan(gradient dot approach unit vector))'}[m[1]]
        return f'Arc-length-{METRIC_LABELS[m[2]]} of {quantity} at line samples.',('m' if m[3]=='m' else 'degrees'),NB['terrain'],''
    m=re.fullmatch(r'terrain_aspect_(sin|cos)_mean',name)
    if m: return f'Arc-length-weighted mean {m[1]} of terrain aspect angle at line samples.','dimensionless',NB['terrain'],''
    return 'Stored source field; detailed definition has not been established from inspected release evidence.','',MANIFEST,'Definition and units require author review.'

def missing(name,source,table):
    if table=='selection_audit':
        if name.startswith('first_exclusion_'): return 'Null exactly for retained units; no exclusion reason applies.'
        if name in builder.TIMING_MAP: return 'Null for support/conflict-stage failures because timing was not evaluated; other missingness, if any, is preserved from corrected frozen-cohort timing. Null is not false.'
        if name in builder.ANCHOR_MAP: return 'Null unless support/conflict and timing stages passed; prediction-anchor checks were not evaluated for earlier failures. Null is not false.'
    if name=='screened_width_m': return 'Null when width is missing/nonfinite, nonpositive, or above the 300 ft review flag; use width_status to distinguish.'
    if name=='hrrr_failure_reason': return 'Null for successful HRRR processing; nonnull text records a failure reason.'
    if source=='landfire':
        f=LF[name]
        s='NoData -9999 is masked before scaling; valid canopy zero is retained. Missing values are not zero exposure.'
        if f['direction_required']=='True': s+=' Directional fields are missing when approach direction is unreliable.'
        if f['statistic'].startswith('positive_'): s+=' Positive-conditioned statistics are missing if there are no valid positive values.'
        return s
    if source=='hrrr': return 'Missing when selected forecast/horizon or required ETA/direction is unavailable; negative gust-derived values were replaced with missing. See availability and provenance fields; null is not zero weather.'
    if source=='approach': return 'Missing when observation history or required geometry/rate is unavailable; ETA is missing for nonpositive approach rate. Release preserves upstream nulls/NaNs; see definition for boolean conventions.'
    if source=='terrain': return 'Missing for invalid/unavailable DEM support; approach-relative terrain is missing when direction is unreliable. Release preserves upstream nulls/NaNs.'
    return DEFAULT_MISSING

def provenance(name,table):
    if table=='retained_fireline_units':
        if name in MAN:
            src=MAN[name]['source']; return src,MASTER+'; upstream: '+UPSTREAM.get(src,'05A frozen core metadata'),name
        if name in ['_geom_hash','source_record_key','actual_line_length_m']:
            return 'unit_evidence',SOURCES['evidence'],('_irwin_norm + "|" + _geom_hash' if name=='source_record_key' else name)
        if name=='outer_fold': return 'fold_assignment',SOURCES['folds'],name
        return 'source_record_audit',SOURCES['source_records'],('geodesic_length_m' if name=='source_record_geodesic_length_m' else name)
    if name in builder.TIMING_MAP: return 'frozen_cohort',SOURCES['supported'],builder.TIMING_MAP[name]
    if name in builder.ANCHOR_MAP: return 'dynamic_approach',SOURCES['approach'],builder.ANCHOR_MAP[name]
    if name in ['support_stage_pass','support_stage_reason']: return 'frozen_cohort',SOURCES['supported']+'; '+SOURCES['excluded'],('final_temporally_corroborated' if name.endswith('pass') else 'final_exclusion_reason')
    if name in ['retained','first_exclusion_stage','first_exclusion_reason','first_exclusion_reason_origin']: return 'release_builder','scripts/build_zenodo_core_v1.py','derived from saved membership/flags/reasons'
    if name=='hold_label': return 'release_builder',SOURCES['evidence'],'_engagement_norm: Held=1; Burned Over=0'
    if name=='source_record_key': return 'release_builder',SOURCES['evidence'],'_irwin_norm + "|" + _geom_hash'
    return 'unit_evidence',SOURCES['evidence'],name

def scan(path):
    pf=pq.ParquetFile(path); counts={n:[0,0] for n in pf.schema_arrow.names}
    for batch in pf.iter_batches(batch_size=25000):
        for n,arr in zip(batch.schema.names,batch.columns):
            counts[n][0]+=arr.null_count
            if pa.types.is_floating(arr.type): counts[n][1]+=int(pc.sum(pc.fill_null(pc.is_nan(arr),False)).as_py())
    return pf,counts

def write_csv(path,rows):
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

allrows=[]
for table in ['retained_fireline_units','selection_audit']:
    pf,counts=scan(CORE/'data'/f'{table}.parquet')
    assert [x['name'] for x in SCHEMA[table]]==pf.schema_arrow.names
    rows=[]
    for pos,f in enumerate(pf.schema_arrow):
        name=f.name; src,path,source_col=provenance(name,table); d,units,ev,unresolved=resolve(name)
        primary=table=='retained_fireline_units' and name in ALLOW_POS
        role=('primary_predictor' if primary else MAN[name]['role']) if name in MAN and table=='retained_fireline_units' else ('split_assignment' if name=='outer_fold' else 'audit_metadata')
        if table=='selection_audit':
            role='selection_indicator' if name in ['retained','support_stage_pass','timing_stage_pass','clean_anchor_stage_pass'] else ('target' if name=='hold_label' else 'selection_audit_metadata')
        if table=='retained_fireline_units' and role=='feature_candidate': role='excluded_candidate_metadata'
        if name in ['unit_uid','_geom_hash','source_record_key','IncidentName'] and not primary: role='identifier'
        if name=='_irwin_norm' and not primary: role='incident_grouping_key'
        if name=='_engagement_norm' and not primary: role='target_derived'
        row={'table':table,'column_position_1based':pos+1,'column_name':name,'role':role,'original_manifest_role':MAN.get(name,{}).get('role','') if table=='retained_fireline_units' else '',
             'primary_predictor':primary,'primary_predictor_position_1based':ALLOW_POS.get(name,'') if primary else '',
             'arrow_datatype':str(f.type),'schema_nullable':f.nullable,'observed_null_count':counts[name][0],'observed_nan_count':counts[name][1],'observed_missing_count':sum(counts[name]),
             'definition':d,'units':units,'missing_value_semantics':missing(name,src,table),'source_family':src,'source_provenance':path,'source_column_or_derivation':source_col,'definition_evidence':ev,
             'definition_status':'partially_resolved' if unresolved else 'documented','unresolved_definition_details':unresolved,
             'landfire_tier':LF.get(name,{}).get('tier',''),'landfire_region':LF.get(name,{}).get('region',''),'landfire_product':LF.get(name,{}).get('product',''),'landfire_statistic':LF.get(name,{}).get('statistic',''),'direction_required':LF.get(name,{}).get('direction_required','')}
        assert str(f.type)==SCHEMA[table][pos]['type'] and f.nullable==SCHEMA[table][pos]['nullable']
        rows.append(row)
    write_csv(OUT/f'{table}_data_dictionary.csv',rows)
    allrows.extend(rows)
    pf.close()

unresolved=[r for r in allrows if r['definition_status']!='documented']
write_csv(OUT/'UNRESOLVED_DEFINITIONS.csv',[{k:r[k] for k in ['table','column_name','definition','unresolved_definition_details','definition_evidence']} for r in unresolved])
support=['LANDFIRE_FEATURE_DICTIONARY_V5.csv','LANDFIRE_REGION_DEFINITION_V5.csv','FBFM40_GROUP_MAPPING_V5.csv','LANDFIRE_FEATURE_RULES_V5.csv']
(OUT/'source_specs').mkdir(exist_ok=True)
sources=[MANIFEST,LF_DICT,'outputs/modeling_table_assembly_v1/SOURCE_SCHEMA_INVENTORY_V1.csv','scripts/build_zenodo_core_v1.py',*NB.values(),'zenodo_upload_v1/validation/column_schemas.json','zenodo_upload_v1/validation/primary_predictor_columns.json']
for name in support:
    p=ROOT/'outputs/landfire_feature_architecture_v5'/name
    shutil.copyfile(p,OUT/'source_specs'/name)
    sources.append(p.relative_to(ROOT).as_posix())
proof={'dictionary_rows':{'retained_fireline_units':940,'selection_audit':46},'primary_predictors':sum(r['primary_predictor'] for r in allrows),'package_primary_predictor_allowlist':PACKAGE_ALLOWLIST,'original_core_validation_package_location':'validation/core/','schema_and_order_verified':True,'missing_counts':'Full Arrow batch scan; null and floating NaN counted separately; no imputations.',
       'package_provenance_locations':'CSV source paths preserve original repository provenance. Included evidence files are at evidence/{original_relative_path}; notebooks are at code/notebooks/{filename}. Upstream products referenced by provenance are not necessarily bundled.',
       'partially_resolved_rows':len(unresolved),'partially_resolved_unique_columns':sorted({r['column_name'] for r in unresolved}),
       'definition_source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(set(sources))}}
assert len(allrows)==986 and proof['primary_predictors']==803
(OUT/'DATA_DICTIONARY_VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,indent=2))
