"""Build and validate the two agreed Zenodo core tables without modifying inputs.

Run with the project's Python environment. Final files are published locally only
after full validation; no Zenodo API or network operation is performed.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "master": "data/processed/modeling_table_assembly_v1/fireline_hold_modeling_master_v1.parquet",
    "evidence": "data/processed/fireline_corrected_local_250m_10m/unit_evidence_rule_audit/weighted_unit_evidence_metrics.parquet",
    "supported": "data/processed/fireline_corrected_local_250m_10m/frozen_cohort/fireline_ml_cohort_frozen_v1.parquet",
    "excluded": "data/processed/fireline_corrected_local_250m_10m/frozen_cohort/fireline_ml_excluded_units_v1.parquet",
    "approach": "data/processed/fireline_dynamic_approach_v2/dynamic_approach_features_v2.parquet",
    "source_records": "outputs/08_condition_outcomes/08B_20260930T224636_898345Z_38d03c/08B_original_source_record_audit.parquet",
    "folds": "data/processed/modeling_design_v1/unit_outer_fold_and_training_weights_v1.parquet",
    "master_columns": "outputs/modeling_table_assembly_v1/MODELING_COLUMN_MANIFEST_V1.csv",
    "features": "outputs/modeling_design_v1/FEATURE_SETS_V1.json",
}
REASONS = {
    "held_support_fraction_below_0.10": 128979,
    "burned_over_support_fraction_below_0.10": 84424,
    "held_nonzero_conflict_fraction": 41302,
    "timing_coherence_below_0.50": 2460,
    "inside_at_prediction_time": 10892,
}
TS = pa.timestamp("us", tz="UTC")


def field(name, dtype, nullable=True):
    return pa.field(name, dtype, nullable=nullable)


ADDITIONS = pa.schema([
    field("_geom_hash", pa.string(), False),
    field("source_record_key", pa.string(), False),
    field("actual_line_length_m", pa.float64(), False),
    field("FeatureCategory", pa.string(), False),
    field("StrategicLineType", pa.string()),
    field("LineWidthFeet", pa.float64()),
    field("reported_width_m", pa.float64()),
    field("screened_width_m", pa.float64()),
    field("width_status", pa.string(), False),
    field("source_record_geodesic_length_m", pa.float64()),
    field("outer_fold", pa.int16(), False),
])
AUDIT_SCHEMA = pa.schema([
    field("unit_uid", pa.string(), False),
    field("_irwin_norm", pa.string(), False),
    field("_geom_hash", pa.string(), False),
    field("source_record_key", pa.string(), False),
    field("IncidentName", pa.string()),
    field("Year", pa.int64(), False),
    field("FeatureCategory", pa.string()),
    field("_engagement_norm", pa.string(), False),
    field("hold_label", pa.int8(), False),
    field("actual_line_length_m", pa.float64(), False),
    *[field(n, pa.int64(), False) for n in
      ["sample_points", "supported_points", "conflict_points", "insufficient_points"]],
    *[field(n, pa.float64(), False) for n in
      ["weighted_support_length_m", "weighted_conflict_length_m", "weighted_insufficient_length_m",
       "weighted_support_fraction", "weighted_conflict_fraction", "weighted_insufficient_fraction"]],
    field("unit_evidence", pa.string()),
    field("unit_diagnostic_reason", pa.string()),
    field("support_stage_pass", pa.bool_(), False),
    field("support_stage_reason", pa.string(), False),
    field("has_supported_challenge_interval", pa.bool_()),
    field("challenge_timing_confident", pa.bool_()),
    field("timing_stage_pass", pa.bool_()),
    field("prediction_anchor_available", pa.bool_()),
    field("prediction_t0_any_inside", pa.bool_()),
    field("clean_anchor_stage_pass", pa.bool_()),
    field("retained", pa.bool_(), False),
    field("first_exclusion_stage", pa.string()),
    field("first_exclusion_reason", pa.string()),
    field("first_exclusion_reason_origin", pa.string()),
    field("prediction_anchor_utc", TS),
    field("prediction_anchor_idx", pa.int64()),
    field("earliest_supported_interval_start_utc", TS),
    field("latest_supported_interval_end_utc", TS),
    field("dominant_supported_interval_start_utc", TS),
    field("dominant_supported_interval_end_utc", TS),
    field("dominant_interval_hours", pa.float64()),
    field("supported_event_span_hours", pa.float64()),
    field("supported_interval_count", pa.int64()),
    field("dominant_interval_weight_fraction", pa.float64()),
    field("total_supported_event_weight_m", pa.float64()),
    field("dominant_supported_weight_m", pa.float64()),
])
TIMING_MAP = {
    "has_supported_challenge_interval": "has_supported_challenge_interval",
    "challenge_timing_confident": "challenge_timing_confident",
    "timing_stage_pass": "dynamic_timing_eligible",
    "earliest_supported_interval_start_utc": "earliest_supported_interval_start_utc_timing",
    "latest_supported_interval_end_utc": "latest_supported_interval_end_utc_timing",
    "dominant_supported_interval_start_utc": "dominant_challenge_interval_start_utc",
    "dominant_supported_interval_end_utc": "dominant_challenge_interval_end_utc",
    "dominant_interval_hours": "dominant_challenge_interval_hours",
    "supported_event_span_hours": "supported_event_span_hours_timing",
    "supported_interval_count": "supported_interval_count_timing",
    "dominant_interval_weight_fraction": "dominant_interval_weight_fraction_timing",
    "total_supported_event_weight_m": "total_supported_event_weight_m",
    "dominant_supported_weight_m": "dominant_supported_weight_m",
}
ANCHOR_MAP = {
    "prediction_anchor_available": "prediction_anchor_available",
    "prediction_t0_any_inside": "prediction_t0_any_inside",
    "clean_anchor_stage_pass": "operational_anchor_clean",
    "prediction_anchor_utc": "prediction_anchor_utc",
    "prediction_anchor_idx": "prediction_anchor_idx",
}
CHECKS = []


def require(condition, name, detail=None):
    CHECKS.append({"check": name, "passed": bool(condition), "detail": detail})
    if not condition:
        raise ValueError(f"Validation failed: {name}; {detail}")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(16 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(name, columns):
    return pq.read_table(ROOT / SOURCES[name], columns=list(dict.fromkeys(columns))).to_pandas()


def indexed(df, label, key="unit_uid"):
    require(df[key].notna().all() and not df[key].duplicated().any(), label + "_unique_key")
    return df.set_index(key, drop=False)


def value_equal(left, right):
    """Exact Arrow value equality, treating paired nulls and NaNs as equal."""
    if not left.type.equals(right.type):
        return False
    eq = pc.fill_null(pc.equal(left, right), False)
    eq = pc.or_(eq, pc.and_(pc.is_null(left), pc.is_null(right)))
    if pa.types.is_floating(left.type):
        eq = pc.or_(eq, pc.fill_null(pc.and_(pc.is_nan(left), pc.is_nan(right)), False))
    return bool(pc.all(eq).as_py())


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def run(output):
    output = output.resolve()
    require(output.is_relative_to(ROOT), "output_within_workspace")
    data_dir, validation_dir = output / "data", output / "validation"
    for directory in [data_dir, validation_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    final_retained = data_dir / "retained_fireline_units.parquet"
    final_audit = data_dir / "selection_audit.parquet"
    require(not final_retained.exists() and not final_audit.exists(), "no_existing_final_tables_overwritten")
    retained_tmp = final_retained.with_suffix(".parquet.partial")
    audit_tmp = final_audit.with_suffix(".parquet.partial")
    print("Hashing input files before building.", flush=True)
    source_manifest = {}
    for key, rel in SOURCES.items():
        p = ROOT / rel
        source_manifest[key] = {"path": rel, "bytes": p.stat().st_size,
                                "mtime_ns": p.stat().st_mtime_ns, "sha256": digest(p)}

    master_file = pq.ParquetFile(ROOT / SOURCES["master"])
    master_schema = master_file.schema_arrow
    master_names = master_schema.names
    feature_names = json.loads((ROOT / SOURCES["features"]).read_text())["E_FULL_EXTENDED"]
    column_manifest = pd.read_csv(ROOT / SOURCES["master_columns"])
    require(master_file.metadata.num_rows == 304143 and len(master_names) == 929, "master_shape")
    require(column_manifest["column"].tolist() == master_names, "master_manifest_exact_column_order")
    require(len(feature_names) == len(set(feature_names)) == 803 and set(feature_names) <= set(master_names),
            "exact_803_primary_predictors_present")
    require(not (set(ADDITIONS.names) & set(master_names)), "added_columns_do_not_overwrite_master")
    require(len(AUDIT_SCHEMA) == 46, "agreed_audit_column_count")
    meta = read("master", ["unit_uid", "_irwin_norm", "IncidentName", "Year", "_engagement_norm",
                          "hold_label", "prediction_anchor_utc", "operational_anchor_clean",
                          "prediction_t0_any_inside"])
    mi = indexed(meta, "master")
    require(meta["_irwin_norm"].nunique() == 381, "retained_fire_count")
    require(meta.hold_label.value_counts().to_dict() == {1: 205926, 0: 98217}, "retained_outcomes")
    require(meta.Year.value_counts().sort_index().to_dict() ==
            {2020: 48596, 2021: 101517, 2022: 31232, 2023: 10467, 2024: 112331}, "retained_year_counts")

    evidence_columns = AUDIT_SCHEMA.names[:22]
    evidence_columns = [x for x in evidence_columns if x not in {"source_record_key", "hold_label"}]
    w = read("evidence", evidence_columns)
    w["source_record_key"] = w["_irwin_norm"] + "|" + w["_geom_hash"]
    require(set(w["_engagement_norm"].unique()) == {"Held", "Burned Over"}, "candidate_outcome_categories")
    w["hold_label"] = w["_engagement_norm"].map({"Held": 1, "Burned Over": 0}).astype("int8")
    wi = indexed(w, "candidate_evidence")
    require(len(w) == 572200 and w["_irwin_norm"].nunique() == 415, "candidate_shape")
    require(set(mi.index) <= set(wi.index), "all_retained_units_in_candidates")
    for name in ["_irwin_norm", "Year", "_engagement_norm", "hold_label"]:
        require((wi.loc[mi.index, name].to_numpy() == mi[name].to_numpy()).all(),
                "master_candidate_agreement_" + name)

    source_cols = ["source_record_key", "_irwin_norm", "_geom_hash", "Year", "_engagement_norm",
                   "FeatureCategory", "StrategicLineType", "LineWidthFeet", "reported_width_m",
                   "screened_width_m", "width_status", "geodesic_length_m"]
    source = indexed(read("source_records", source_cols), "source_records", "source_record_key")
    require(len(source) == 570111, "source_record_count")
    require((source.source_record_key == source["_irwin_norm"] + "|" + source["_geom_hash"]).all(),
            "source_key_definition")
    require(set(w.source_record_key) <= set(source.index), "all_candidates_join_source_records")
    sr = source.loc[w.source_record_key]
    for name in ["_irwin_norm", "_geom_hash", "Year", "_engagement_norm", "FeatureCategory"]:
        require((sr[name].to_numpy() == w[name].to_numpy()).all(), "candidate_source_agreement_" + name)
    del sr
    sf = indexed(read("folds", ["unit_uid", "_irwin_norm", "Year", "hold_label", "outer_fold"]), "folds")
    require(set(sf.index) == set(mi.index), "fold_membership_exact")
    require(sf.groupby("_irwin_norm").outer_fold.nunique().eq(1).all(), "fires_not_split_between_folds")
    require(set(sf.outer_fold.unique()) == set(range(5)), "five_fold_values")
    for name in ["_irwin_norm", "Year", "hold_label"]:
        require((sf.loc[mi.index, name].to_numpy() == mi[name].to_numpy()).all(), "fold_agreement_" + name)

    fcols = ["unit_uid", "final_temporally_corroborated", "final_exclusion_reason"] + list(TIMING_MAP.values())
    f = indexed(read("supported", fcols), "support_pass_records")
    e = indexed(read("excluded", ["unit_uid", "final_temporally_corroborated", "final_exclusion_reason"]),
                "support_exclusions")
    require(len(f) == 317495 and len(e) == 254705, "support_stage_counts")
    require(set(f.index).isdisjoint(e.index) and set(f.index) | set(e.index) == set(wi.index),
            "support_partition_disjoint_exhaustive")
    require(f.final_temporally_corroborated.all() and not e.final_temporally_corroborated.any(),
            "support_stage_saved_flags")
    require(f.final_exclusion_reason.eq("included").all(), "support_pass_reason_is_included")
    a = indexed(read("approach", ["unit_uid"] + list(ANCHOR_MAP.values())), "approach")
    require(len(a) == 315035, "approach_population")
    timing_ids = set(f.index[f.dynamic_timing_eligible])
    require(set(a.index) == timing_ids, "approach_equals_timing_pass_membership")
    require(set(a.index[a.operational_anchor_clean]) == set(mi.index), "clean_anchor_equals_final_membership")
    require(a.prediction_anchor_available.all(), "evaluated_anchors_available")
    require(a.prediction_t0_any_inside.eq(~a.operational_anchor_clean).all(), "final_inside_exclusion_rule")
    require(a.prediction_anchor_utc.eq(f.loc[a.index, "earliest_supported_interval_start_utc_timing"]).all(),
            "prediction_time_uses_corrected_earliest_interval")
    require(mi.prediction_anchor_utc.eq(a.loc[mi.index, "prediction_anchor_utc"]).all(),
            "retained_prediction_times_match")

    audit = wi.copy()
    stage = pd.concat([f[["final_temporally_corroborated", "final_exclusion_reason"]],
                       e[["final_temporally_corroborated", "final_exclusion_reason"]]]).reindex(audit.index)
    audit["support_stage_pass"] = stage.final_temporally_corroborated
    audit["support_stage_reason"] = stage.final_exclusion_reason
    for new, old in TIMING_MAP.items():
        audit[new] = f[old].reindex(audit.index)
    for new, old in ANCHOR_MAP.items():
        audit[new] = a[old].reindex(audit.index)
    audit["retained"] = audit.index.isin(mi.index)
    for col in ["first_exclusion_stage", "first_exclusion_reason", "first_exclusion_reason_origin"]:
        audit[col] = pd.Series(pd.NA, index=audit.index, dtype="string")
    audit.loc[e.index, "first_exclusion_stage"] = "support_conflict"
    audit.loc[e.index, "first_exclusion_reason"] = e.final_exclusion_reason
    audit.loc[e.index, "first_exclusion_reason_origin"] = "saved_reason"
    timing_fail = f.index[~f.dynamic_timing_eligible]
    anchor_fail = a.index[~a.operational_anchor_clean]
    audit.loc[timing_fail, "first_exclusion_stage"] = "timing"
    audit.loc[timing_fail, "first_exclusion_reason"] = "timing_coherence_below_0.50"
    audit.loc[timing_fail, "first_exclusion_reason_origin"] = "derived_from_saved_flags"
    audit.loc[anchor_fail, "first_exclusion_stage"] = "prediction_time"
    audit.loc[anchor_fail, "first_exclusion_reason"] = "inside_at_prediction_time"
    audit.loc[anchor_fail, "first_exclusion_reason_origin"] = "derived_from_saved_flags"
    require(audit.first_exclusion_reason.value_counts().to_dict() == REASONS, "exact_exclusion_reason_counts")
    require(audit.retained.sum() == 304143 and (~audit.retained).sum() == 268057, "final_partition_counts")
    require(audit.first_exclusion_reason.isna().eq(audit.retained).all(), "reason_null_only_for_retained")

    eps = 1e-12
    expected_support = (audit.weighted_support_fraction >= .10 - eps) & (
        audit["_engagement_norm"].eq("Burned Over") | (audit.weighted_conflict_fraction <= eps))
    require(expected_support.eq(audit.support_stage_pass).all(), "support_rules_reproduce_saved_flags")
    require(f.dynamic_timing_eligible.eq(f.has_supported_challenge_interval &
            (f.dominant_interval_weight_fraction_timing >= .50 - eps)).all(),
            "timing_rule_reproduces_saved_flags")
    require((audit.supported_points + audit.conflict_points + audit.insufficient_points).eq(audit.sample_points).all(),
            "point_counts_partition_samples")
    require(np.allclose(audit.weighted_support_fraction + audit.weighted_conflict_fraction +
                        audit.weighted_insufficient_fraction, 1, rtol=0, atol=1e-10),
            "weighted_fractions_sum_to_one")
    for name in ["weighted_support_fraction", "weighted_conflict_fraction", "weighted_insufficient_fraction"]:
        require(audit[name].between(-eps, 1 + eps).all(), "fraction_range_" + name)
    require(audit.loc[e.index, list(TIMING_MAP)].isna().all().all(), "uncomputed_timing_is_null")
    require(audit.loc[audit.index.difference(a.index), list(ANCHOR_MAP)].isna().all().all(),
            "uncomputed_prediction_checks_are_null")
    for name in [x.name for x in AUDIT_SCHEMA if pa.types.is_timestamp(x.type)]:
        dates = audit[name].dropna()
        require(dates.dt.year.between(2020, 2024).all(), "no_legacy_epoch_dates_" + name)
    require(np.allclose(
        (f.dominant_challenge_interval_end_utc - f.dominant_challenge_interval_start_utc).dt.total_seconds() / 3600,
        f.dominant_challenge_interval_hours, rtol=0, atol=1e-9), "corrected_interval_duration")
    require(np.allclose(
        (f.latest_supported_interval_end_utc_timing - f.earliest_supported_interval_start_utc_timing).dt.total_seconds() / 3600,
        f.supported_event_span_hours_timing, rtol=0, atol=1e-9), "corrected_event_span")
    require(np.allclose(f.dominant_supported_weight_m / f.total_supported_event_weight_m,
                        f.dominant_interval_weight_fraction_timing, rtol=0, atol=1e-12),
            "corrected_timing_concentration")

    # The first 929 columns remain exact copies of the model master.
    attrs = wi.loc[mi.index, ["_geom_hash", "source_record_key", "actual_line_length_m"]].copy()
    for name in ["FeatureCategory", "StrategicLineType", "LineWidthFeet", "reported_width_m",
                 "screened_width_m", "width_status"]:
        attrs[name] = source.loc[attrs.source_record_key, name].to_numpy()
    attrs["source_record_geodesic_length_m"] = source.loc[attrs.source_record_key, "geodesic_length_m"].to_numpy()
    attrs["outer_fold"] = sf.loc[attrs.index, "outer_fold"].to_numpy()
    raw_width = attrs.LineWidthFeet.to_numpy(dtype=float)
    screen_expected = np.where(np.isfinite(raw_width) & (raw_width > 0) & (raw_width <= 300),
                               raw_width * .3048, np.nan)
    require(np.allclose(attrs.reported_width_m, raw_width * .3048, equal_nan=True, rtol=0, atol=1e-12),
            "width_conversion")
    require(np.allclose(attrs.screened_width_m, screen_expected, equal_nan=True, rtol=0, atol=1e-12),
            "width_screen")
    require(attrs.screened_width_m.notna().sum() == 41309, "screened_width_count")
    require(attrs.source_record_key.nunique() == 142999, "represented_source_record_count")

    audit_arrays = [pa.array(audit[x.name], type=x.type, from_pandas=True) for x in AUDIT_SCHEMA]
    audit_table = pa.Table.from_arrays(audit_arrays, schema=AUDIT_SCHEMA)
    for x in AUDIT_SCHEMA:
        require(x.nullable or audit_table[x.name].null_count == 0, "audit_required_" + x.name)
    audit_table = audit_table.replace_schema_metadata({
        b"release_scope": b"572200 corrected candidates in 415 fires; not the full NIFC archive",
        b"timing_sources": json.dumps(TIMING_MAP).encode(),
        b"null_semantics": b"Later-stage values are null when not evaluated; do not interpret as false",
    })
    pq.write_table(audit_table, audit_tmp, compression="zstd", row_group_size=50000)
    print("Selection audit staged: 572,200 rows, 46 columns.", flush=True)
    retained_metadata = {k: v for k, v in (master_schema.metadata or {}).items() if k != b"pandas"}
    retained_metadata.update({
        b"release_primary_predictors": json.dumps(feature_names).encode(),
        b"release_notice": b"Only the ordered 803-column allowlist is the primary feature matrix",
        b"original_master_columns": json.dumps(master_names).encode(),
    })
    retained_schema = pa.schema(list(master_schema) + list(ADDITIONS), metadata=retained_metadata)
    written = 0
    with pq.ParquetWriter(retained_tmp, retained_schema, compression="zstd") as writer:
        for batch in master_file.iter_batches(batch_size=25000):
            table = pa.Table.from_batches([batch])
            rows = attrs.loc[table["unit_uid"].to_pylist()]
            extra = [pa.array(rows[x.name], type=x.type, from_pandas=True) for x in ADDITIONS]
            for x, arr in zip(ADDITIONS, extra):
                require(x.nullable or arr.null_count == 0, "retained_required_" + x.name + "_" + str(written))
            combined = pa.Table.from_arrays(list(table.columns) + extra, schema=retained_schema)
            writer.write_table(combined)
            written += len(table)
            print(f"Retained rows staged: {written:,}", flush=True)
    require(written == 304143, "retained_written_count")
    del audit_arrays
    gc.collect()

    # Reopen all outputs. Compare every original cell, not merely sampled rows.
    saved_audit = pq.read_table(audit_tmp)
    require(saved_audit.schema.equals(audit_table.schema, check_metadata=True), "audit_schema_roundtrip")
    for name in AUDIT_SCHEMA.names:
        require(value_equal(audit_table[name], saved_audit[name]), "audit_roundtrip_" + name)
    saved_file = pq.ParquetFile(retained_tmp)
    require(saved_file.metadata.num_rows == 304143 and len(saved_file.schema_arrow) == 940,
            "retained_final_shape")
    require(saved_file.schema_arrow.names == master_names + ADDITIONS.names, "retained_exact_column_order")
    require(all(saved_file.schema_arrow.field(n).equals(master_schema.field(n)) for n in master_names),
            "all_original_arrow_field_types_preserved")
    compared_rows = 0
    for before, after in zip(master_file.iter_batches(batch_size=25000),
                             saved_file.iter_batches(batch_size=25000), strict=True):
        require(before.num_rows == after.num_rows, "comparison_batch_rows_" + str(compared_rows))
        for j, name in enumerate(master_names):
            if not value_equal(before.column(j), after.column(j)):
                require(False, "original_values_preserved", {"column": name, "offset": compared_rows})
        ids = after.column(0).to_pylist()
        for j, x in enumerate(ADDITIONS):
            expected = pa.array(attrs.loc[ids, x.name], type=x.type, from_pandas=True)
            if not value_equal(expected, after.column(len(master_names) + j)):
                require(False, "added_values_preserved", {"column": x.name, "offset": compared_rows})
        compared_rows += before.num_rows
    require(compared_rows == 304143, "all_929_original_columns_and_11_additions_verified")
    # Windows prevents renaming while an explicit ParquetFile reader is open.
    saved_file.close()
    master_file.close()
    print("All original values, types, missingness and row order verified after reopening.", flush=True)

    print("Rechecking source integrity.", flush=True)
    for key, before in source_manifest.items():
        p = ROOT / SOURCES[key]
        require(p.stat().st_size == before["bytes"] and p.stat().st_mtime_ns == before["mtime_ns"]
                and digest(p) == before["sha256"], "source_unchanged_" + key)

    # Local publication happens only after the complete validation above.
    retained_tmp.rename(final_retained)
    audit_tmp.rename(final_audit)
    output_manifest = []
    for p in [final_retained, final_audit]:
        pf = pq.ParquetFile(p)
        output_manifest.append({"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size,
                                "rows": pf.metadata.num_rows, "columns": len(pf.schema_arrow),
                                "sha256": digest(p)})
    issues = [
        {"severity": "documented_source_issue", "issue": "Legacy selection timestamps",
         "handling": "Only corrected frozen-cohort timing fields were used. No fallback to legacy epoch timestamps. Unreconstructed timing remains null."},
        {"severity": "scope", "issue": "Selection universe is 572200 corrected candidates in 415 fires",
         "handling": "Not Engaged source records and fires excluded before corrected-unit production are outside this audit universe."},
        {"severity": "pending_package_work", "issue": "Core tables only",
         "handling": "Geometry, full dictionary, model/evaluation companions, release terms and Zenodo metadata are not packaged in this step."},
    ]
    summary = {
        "status": "PASS_CORE_TABLES_VALIDATED_PACKAGE_INCOMPLETE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "builder": str(Path(__file__).relative_to(ROOT)), "builder_sha256": digest(Path(__file__)),
        "versions": {"python": platform.python_version(), "pandas": pd.__version__,
                     "pyarrow": pa.__version__, "numpy": np.__version__},
        "retained": {"rows": 304143, "columns": 940, "fires": 381, "source_records": 142999,
                     "held": 205926, "burned_over": 98217, "primary_predictors": 803,
                     "screened_width_available": 41309},
        "selection": {"rows": 572200, "columns": 46, "fires": 415, "excluded": 268057,
                      "first_exclusion_counts": REASONS,
                      "held_fail_both_support_and_conflict": int((
                          audit["_engagement_norm"].eq("Held") &
                          (audit.weighted_support_fraction < .10 - eps) &
                          (audit.weighted_conflict_fraction > eps)).sum())},
        "checks": CHECKS, "issues": issues, "outputs": output_manifest,
        "column_sources": {"added_source_attributes": SOURCES["source_records"],
                           "source_record_geodesic_length_m": "08B source-record audit: geodesic_length_m",
                           "timing_map": TIMING_MAP, "anchor_map": ANCHOR_MAP},
        "numeric_rule_tolerance": eps,
    }
    json_write(validation_dir / "source_manifest.json", source_manifest)
    json_write(validation_dir / "build_report.json", summary)
    json_write(validation_dir / "primary_predictor_columns.json", feature_names)
    json_write(validation_dir / "column_schemas.json", {
        "retained_fireline_units": [{"name": x.name, "type": str(x.type), "nullable": x.nullable,
                                    "primary_predictor": x.name in feature_names} for x in retained_schema],
        "selection_audit": [{"name": x.name, "type": str(x.type), "nullable": x.nullable} for x in AUDIT_SCHEMA],
    })
    (validation_dir / "checksums.sha256").write_text(
        "".join(x["sha256"] + "  " + x["path"] + "\n" for x in output_manifest), encoding="utf-8")
    text_report = [
        "# Core dataset build validation", "",
        "Status: PASS. The two core tables are validated; the complete Zenodo package is still pending.", "",
        "Retained table: 304,143 units, 381 fires, 940 columns; 205,926 Held and 98,217 Burned Over.",
        "Selection audit: 572,200 candidates, 415 fires, 46 columns; 268,057 excluded.",
        "All 929 original master columns were compared cell-by-cell after writing, including null/NaN values and row order.",
        "All nine source inputs were hashed before and after the build and remained unchanged.",
        "Only the ordered 803 primary predictors are model inputs. The wider retained table is an archival analytical table.", "",
        "## Exclusions", "",
    ] + [f"- {k}: {v:,}" for k, v in REASONS.items()] + [
        "", "## Issues and scope", "",
    ] + [f"- {i['issue']}: {i['handling']}" for i in issues] + [
        "", "Later selection stages that were not evaluated remain null, not false.",
        "The first exclusion reason does not imply that all other criteria passed.",
        "Prediction times use the earliest supported interval, not the dominant interval.",
        "No files have been uploaded to Zenodo.",
    ]
    (validation_dir / "VALIDATION_REPORT.md").write_text("\n".join(text_report) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "outputs": output_manifest}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "zenodo_upload_v1")
    args = parser.parse_args()
    run(args.output)
