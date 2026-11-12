"""Verify the release files and cohort/prediction joins without training or network access."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1] / 'dataset'
RUN_E = 'outputs/08_condition_outcomes/08E_20261105T211309_533108Z_9ff65f'

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def run(output, hashes=True):
    checks = []
    def check(ok, name, detail=None):
        checks.append({'name': name, 'passed': bool(ok), 'detail': detail})
        if not ok:
            raise ValueError(name + ': ' + str(detail))
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Choose a new output directory outside the dataset package.')
    output.mkdir(parents=True, exist_ok=False)
    try:
        retained_path = ROOT / 'data/retained_fireline_units.parquet'
        audit_path = ROOT / 'data/selection_audit.parquet'
        rf, af = pq.ParquetFile(retained_path), pq.ParquetFile(audit_path)
        check((rf.metadata.num_rows, len(rf.schema_arrow)) == (304143, 940), 'retained_dimensions')
        check((af.metadata.num_rows, len(af.schema_arrow)) == (572200, 46), 'audit_dimensions')
        features = json.loads((ROOT / 'data/primary_predictor_columns.json').read_text())
        check(len(features) == len(set(features)) == 803, 'ordered_803_predictors_unique')
        check(set(features).issubset(rf.schema_arrow.names), 'predictors_present')
        check(not set(features).intersection({'hold_label', '_engagement_norm', '_irwin_norm',
            'unit_uid', 'source_record_key', 'outer_fold', 'Year', 'prediction_anchor_utc'}),
            'identifiers_outcomes_folds_not_predictors')
        cols = ['unit_uid', '_irwin_norm', 'source_record_key', 'Year', 'hold_label',
                'outer_fold', 'prediction_anchor_utc', 'screened_width_m']
        retained = pd.read_parquet(retained_path, columns=cols)
        audit = pd.read_parquet(audit_path)
        check(retained.unit_uid.is_unique and audit.unit_uid.is_unique, 'unique_unit_keys')
        check(retained._irwin_norm.nunique() == 381 and audit._irwin_norm.nunique() == 415, 'fire_counts')
        check(retained.hold_label.value_counts().to_dict() == {1: 205926, 0: 98217}, 'outcome_counts')
        check(retained.Year.value_counts().sort_index().to_dict() ==
            {2020: 48596, 2021: 101517, 2022: 31232, 2023: 10467, 2024: 112331}, 'year_counts')
        check(retained.source_record_key.nunique() == 142999, 'retained_source_record_count')
        check(audit.retained.sum() == 304143 and (~audit.retained).sum() == 268057, 'audit_partition')
        check(set(audit.loc[audit.retained, 'unit_uid']) == set(retained.unit_uid), 'exact_retained_membership')
        check(audit.first_exclusion_reason.isna().eq(audit.retained).all(), 'exclusion_reason_only_for_excluded')
        check(audit.first_exclusion_reason.dropna().value_counts().to_dict() == {
            'held_support_fraction_below_0.10': 128979,
            'burned_over_support_fraction_below_0.10': 84424,
            'held_nonzero_conflict_fraction': 41302,
            'timing_coherence_below_0.50': 2460,
            'inside_at_prediction_time': 10892}, 'exclusion_counts')
        check(retained.groupby('_irwin_norm').outer_fold.nunique().eq(1).all(), 'fire_stays_in_one_outer_fold')
        check(set(retained.outer_fold) == set(range(5)), 'five_outer_folds')
        width = retained.screened_width_m.dropna()
        check(len(width) == 41309 and width.gt(0).all() and width.le(91.44).all(), 'screened_width_domain')
        merged = retained.merge(audit.loc[audit.retained], on='unit_uid', suffixes=('_r', '_a'), validate='one_to_one')
        for col in ['_irwin_norm', 'source_record_key', 'Year', 'hold_label', 'prediction_anchor_utc']:
            check(merged[col+'_r'].eq(merged[col+'_a']).all(), 'core_join_'+col)
        check(merged.prediction_t0_any_inside.eq(False).all(), 'retained_clean_prediction_time')
        check(merged.challenge_timing_confident.eq(True).all(), 'retained_timing_agreement')
        check(merged.support_stage_pass.eq(True).all(), 'retained_support_stage')
        predictions = pd.read_parquet(ROOT / 'evidence' / RUN_E / '08E_matched_predictions.parquet')
        check(not predictions.duplicated(['scheme', 'unit_uid']).any(), 'prediction_key_unique')
        probability_cols = ['p_full', 'p_baseline_unit', 'p_baseline_fire', 'p_logistic', 'p_local_nine', 'p_shared']
        p = predictions[probability_cols].to_numpy()
        check(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(), 'probability_domain')
        for scheme, test in predictions.groupby('scheme'):
            expected = retained if scheme == 'five_fold' else retained.loc[retained.Year.ge(2021)]
            check(set(test.unit_uid) == set(expected.unit_uid), 'complete_predictions_'+scheme)
            joined = test.merge(retained, on='unit_uid', suffixes=('_p', '_r'), validate='one_to_one')
            for col in ['_irwin_norm', 'source_record_key', 'Year', 'outer_fold', 'prediction_anchor_utc']:
                check(joined[col+'_p'].eq(joined[col+'_r']).all(), 'prediction_join_'+scheme+'_'+col)
            check(joined.y.eq(joined.hold_label).all(), 'prediction_labels_'+scheme)
            for split, group in test.groupby('split'):
                value = int(split)
                train = retained.loc[retained.outer_fold.ne(value)] if scheme == 'five_fold' else retained.loc[retained.Year.lt(value)]
                check(not set(train._irwin_norm).intersection(group._irwin_norm), 'disjoint_fires_'+scheme+'_'+split)
                if scheme == 'forward_year':
                    check(train.Year.max() < group.Year.min(), 'forward_year_order_'+split)
                unit_prior = train.hold_label.mean()
                fire_prior = train.groupby('_irwin_norm').hold_label.mean().mean()
                check(np.allclose(group.p_baseline_unit, unit_prior, rtol=0, atol=1e-12), 'training_unit_baseline_'+scheme+'_'+split)
                check(np.allclose(group.p_baseline_fire, fire_prior, rtol=0, atol=1e-12), 'training_fire_baseline_'+scheme+'_'+split)
        primary = pd.read_parquet(ROOT / 'evidence/data/processed/baseline_modeling_v1/oof_predictions/E_FULL_EXTENDED__row.parquet')
        same = primary.merge(predictions.loc[predictions.scheme.eq('five_fold'), ['unit_uid','p_full']], on='unit_uid', validate='one_to_one')
        check(np.array_equal(same.pred_prob.to_numpy(), same.p_full.to_numpy()), 'primary_prediction_identity')
        forward = pd.read_parquet(ROOT / 'evidence/data/processed/forward_temporal_generalization_v1/FORWARD_TEMPORAL_PREDICTIONS_V1.parquet')
        same = forward.merge(predictions.loc[predictions.scheme.eq('forward_year'), ['unit_uid','p_full']], on='unit_uid', validate='one_to_one')
        check(np.array_equal(same.pred_forward_fixed_05c.to_numpy(), same.p_full.to_numpy()), 'forward_prediction_identity')
        if hashes:
            manifest = ROOT / 'validation/release_file_manifest.json'
            if manifest.exists():
                entries = json.loads(manifest.read_text())['files']
                for entry in entries:
                    path = (ROOT / entry['path']).resolve()
                    check(path.is_relative_to(ROOT), 'manifest_path_'+entry['path'])
                    check(path.is_file() and sha256(path) == entry['sha256'], 'sha256_'+entry['path'])
            else:
                raise FileNotFoundError('release_file_manifest.json missing; use --skip-hashes only while staging.')
        status = 'PASS'
    except Exception as exc:
        status = 'FAIL'
        (output / 'release_validation.json').write_text(json.dumps({'status': status, 'checks': checks,
            'error': repr(exc)}, indent=2) + '\n', encoding='utf-8')
        raise
    report = {'status': status, 'checks_passed': len(checks), 'hashes_checked': hashes,
              'scope': 'Files, counts, joins, fixed folds, prediction identity, training-only baselines; no retraining.', 'checks': checks}
    (output / 'release_validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': status, 'checks_passed': len(checks), 'output': str(output)}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-root', type=Path, default=ROOT, help='Extracted dataset release folder.')
    parser.add_argument('--output', type=Path, default=Path.cwd() / 'release_verification')
    parser.add_argument('--skip-hashes', action='store_true', help='For staging only; skip the final package checksum manifest.')
    args = parser.parse_args()
    ROOT = args.dataset_root.resolve()
    run(args.output, not args.skip_hashes)
