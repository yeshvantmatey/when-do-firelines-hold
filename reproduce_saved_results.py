"""Reproduce published statistics from fixed saved predictions, without training.

Run from any working directory. Requires numpy, pandas, pyarrow, and scikit-learn.
The default checks 08E point metrics and paired intervals, 08D frozen condition
group outcomes, and the primary model's nine point estimates. The optional
--primary-bootstrap checks all 5,000 Table II replicates and nine intervals.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

TOLERANCE = 1e-10
RUN_C = "outputs/08_condition_outcomes/08C_20260930T234354_724489Z_3a31ea"
RUN_D = "outputs/08_condition_outcomes/08D_20261001T002458_892164Z_f3e697"
RUN_E = "outputs/08_condition_outcomes/08E_20261105T211309_533108Z_9ff65f"
RUN_PRIMARY = "outputs/table_ii_bootstrap_completion_v1/run_20261110T005511_936815Z"
PRIMARY_PREDICTIONS = "data/processed/baseline_modeling_v1/oof_predictions/E_FULL_EXTENDED__row.parquet"
PRIMARY_METRICS = [
    "mean_pred", "pooled_pr_auc", "pooled_roc_auc", "pooled_brier",
    "pooled_log_loss", "incident_macro_brier", "incident_macro_log_loss",
    "mixed_incident_macro_pr_auc", "mixed_incident_macro_roc_auc",
]
PROBABILITY_COLUMNS = [
    "p_full", "p_logistic", "p_local_nine", "p_shared",
    "p_baseline_unit", "p_baseline_fire",
]


class Audit:
    def __init__(self):
        self.checks = []

    def check(self, name, passed, detail=""):
        self.checks.append({"check": name, "passed": bool(passed), "detail": str(detail)})

    def require(self, name, passed, detail=""):
        self.check(name, passed, detail)
        if not passed:
            raise ValueError(f"{name}: {detail}")

    def compare(self, name, actual, expected, keys, columns):
        self.require(name + ".actual_unique_keys", not actual.duplicated(keys).any())
        self.require(name + ".expected_unique_keys", not expected.duplicated(keys).any())
        a = actual.set_index(keys).sort_index()
        b = expected.set_index(keys).sort_index()
        self.require(name + ".keys_match", a.index.equals(b.index),
                     f"actual={len(a)}, expected={len(b)}")
        for col in columns:
            av, bv = a[col].to_numpy(float), b[col].to_numpy(float)
            ok = np.isclose(av, bv, rtol=0, atol=TOLERANCE, equal_nan=True)
            finite = np.isfinite(av) & np.isfinite(bv)
            error = float(np.max(np.abs(av[finite] - bv[finite]))) if finite.any() else 0.0
            self.check(name + "." + col, ok.all(),
                       f"rows={len(av)}; max_absolute_error={error:.17g}; mismatches={int((~ok).sum())}")


def evidence(root, relative):
    path = root / "evidence" / relative
    if not path.is_file():
        raise FileNotFoundError(f"Required release evidence is missing: {path}")
    return path


def check_probabilities(audit, name, frame, columns):
    a = frame[columns].to_numpy(float)
    audit.require(name, np.isfinite(a).all() and ((a >= 0) & (a <= 1)).all())


def reproduce_08e(root, output, audit):
    print("Reproducing 08E: 66 point-metric rows and 352 paired interval rows.", flush=True)
    frame = pd.read_parquet(evidence(root, RUN_E + "/08E_matched_predictions.parquet"))
    audit.require("08E.unique_scheme_unit", not frame.duplicated(["scheme", "unit_uid"]).any())
    audit.require("08E.row_count", len(frame) == 559690)
    audit.require("08E.outcomes", frame.y.isin([0, 1]).all())
    audit.require("08E.schemes", set(frame.scheme) == {"five_fold", "forward_year"})
    check_probabilities(audit, "08E.valid_probabilities", frame, PROBABILITY_COLUMNS)
    scopes = []
    for scheme, part in frame.groupby("scheme", sort=True):
        scopes.append((scheme, "all", part))
        scopes.extend((scheme, str(year), g) for year, g in part.groupby("Year", sort=True))
    metric_rows, paired_rows = [], []
    for scope_index, (scheme, scope, part) in enumerate(scopes):
        fire_ids, codes = np.unique(part._irwin_norm.to_numpy(), return_inverse=True)
        n_fires = len(fire_ids)
        counts = np.bincount(codes, minlength=n_fires).astype(float)
        y = part.y.to_numpy(float)
        indices = [np.flatnonzero(codes == k) for k in range(n_fires)]
        rng = np.random.default_rng(20261105 + 1000 + scope_index)
        draws = rng.multinomial(n_fires, np.full(n_fires, 1 / n_fires), size=2000)
        sums, sampled = {}, {}
        for col in PROBABILITY_COLUMNS:
            p = part[col].to_numpy(float)
            q = np.clip(p, 1e-15, 1 - 1e-15)
            errors = {"brier": (p - y) ** 2,
                      "log_loss": -(y * np.log(q) + (1 - y) * np.log1p(-q))}
            mixed = [idx for idx in indices if len(np.unique(y[idx])) == 2]
            result = {
                "scheme": scheme, "scope": scope, "model": col,
                "fireline_units": len(part), "fires": n_fires,
                "fires_with_both_outcomes": len(mixed),
                "observed_held_fraction": float(y.mean()),
                "mean_predicted_held": float(p.mean()),
                "pooled_roc_auc": roc_auc_score(y, p),
                "pooled_ap": average_precision_score(y, p),
                "within_fire_roc_auc": float(np.mean([roc_auc_score(y[ix], p[ix]) for ix in mixed])),
                "within_fire_ap": float(np.mean([average_precision_score(y[ix], p[ix]) for ix in mixed])),
            }
            for metric, loss in errors.items():
                values = np.bincount(codes, weights=loss, minlength=n_fires)
                sums[(col, metric)] = values
                result["pooled_" + metric] = float(loss.mean())
                result["fire_average_" + metric] = float((values / counts).mean())
                sampled[(col, metric, "unit")] = (draws @ values) / (draws @ counts)
                sampled[(col, metric, "fire")] = (draws @ (values / counts)) / draws.sum(axis=1)
            metric_rows.append(result)
        for weighting in ["unit", "fire"]:
            baseline = "p_baseline_unit" if weighting == "unit" else "p_baseline_fire"
            pairs = [(col, baseline) for col in PROBABILITY_COLUMNS[:4]] + [
                ("p_local_nine", "p_shared"), ("p_full", "p_local_nine"),
                ("p_full", "p_shared"), ("p_full", "p_logistic"),
            ]
            for a, b in pairs:
                for metric in ["brier", "log_loss"]:
                    if weighting == "unit":
                        am = float(sums[(a, metric)].sum() / counts.sum())
                        bm = float(sums[(b, metric)].sum() / counts.sum())
                    else:
                        am = float((sums[(a, metric)] / counts).mean())
                        bm = float((sums[(b, metric)] / counts).mean())
                    delta = sampled[(a, metric, weighting)] - sampled[(b, metric, weighting)]
                    lo, hi = np.quantile(delta, [.025, .975], method="linear")
                    paired_rows.append({
                        "scheme": scheme, "scope": scope, "model": a, "comparator": b,
                        "weighting": weighting, "metric": metric, "model_error": am,
                        "comparator_error": bm, "difference": am - bm,
                        "ci_lower": lo, "ci_upper": hi, "fires": n_fires,
                        "fireline_units": len(part), "bootstrap_replicates": 2000,
                    })
    metrics, paired = pd.DataFrame(metric_rows), pd.DataFrame(paired_rows)
    metrics.to_csv(output / "08E_performance_metrics.csv", index=False)
    paired.to_csv(output / "08E_paired_error_comparisons.csv", index=False)
    audit.require("08E.metric_row_count", len(metrics) == 66)
    audit.require("08E.paired_row_count", len(paired) == 352)
    expected = pd.read_csv(evidence(root, RUN_E + "/performance_metrics.csv"), dtype={"scope": str})
    keys = ["scheme", "scope", "model"]
    audit.compare("08E.points", metrics, expected, keys, [c for c in expected if c not in keys])
    expected = pd.read_csv(evidence(root, RUN_E + "/paired_error_comparisons.csv"), dtype={"scope": str})
    keys = ["scheme", "scope", "model", "comparator", "weighting", "metric"]
    audit.compare("08E.paired", paired, expected, keys, [c for c in expected if c not in keys])


def reproduce_frozen_conditions(root, output, audit):
    print("Reproducing 08D: 24 unit-weighted frozen condition outcomes and intervals.", flush=True)
    lookup = pd.read_parquet(evidence(root, RUN_C + "/08C_unit_lookup.parquet"))
    saved = pd.read_parquet(evidence(root, RUN_C + "/08C_frozen_rule_predictions.parquet"))
    saved = saved.loc[saved.variant.eq("condition_tree")]
    frame = saved.merge(lookup, on="row_id", how="left", validate="one_to_one", indicator=True)
    audit.require("08D.frozen_membership_lookup", frame._merge.eq("both").all())
    audit.require("08D.frozen_test_population", len(frame) == 122798 and set(frame.Year) == {2023, 2024})
    audit.require("08D.frozen_leaves", set(frame.leaf_id) == {3, 4, 6, 7, 10, 11, 13, 14})
    rows = []
    for scope in ["2023_2024", "2023", "2024"]:
        selected = frame if scope == "2023_2024" else frame.loc[frame.Year.eq(int(scope))]
        for leaf in sorted(frame.leaf_id.unique()):
            part = selected.loc[selected.leaf_id.eq(leaf)]
            fire_parts = part.groupby("_irwin_norm", sort=True).y.agg(num="sum", den="size")
            key = "group|" + scope + "|" + "|".join(fire_parts.index.astype(str))
            seed = (20261001 + zlib.crc32(key.encode())) % (2 ** 32)
            rng = np.random.default_rng(seed)
            num, den = fire_parts.num.to_numpy(), fire_parts.den.to_numpy()
            draws = np.full(2000, np.nan)
            if len(fire_parts) >= 2:
                for start in range(0, 2000, 128):
                    stop = min(start + 128, 2000)
                    ids = rng.integers(0, len(fire_parts), (stop - start, len(fire_parts)))
                    draws[start:stop] = num[ids].sum(axis=1) / den[ids].sum(axis=1)
            finite = draws[np.isfinite(draws)]
            lo, hi = np.quantile(finite, [.025, .975], method="linear") if len(finite) >= 2 else (np.nan, np.nan)
            rows.append({
                "scope": scope, "leaf_id": int(leaf), "group": "leaf_" + str(leaf),
                "weight": "unit", "n_units": len(part),
                "n_source_records": part.source_record_key.nunique(), "n_fires": len(fire_parts),
                "n_held": int(part.y.sum()), "n_burned_over": int((1 - part.y).sum()),
                "held_fraction": float(num.sum() / den.sum()) if len(part) else np.nan,
                "ci_lower": lo, "ci_upper": hi,
            })
    actual = pd.DataFrame(rows)
    actual.to_csv(output / "08D_frozen_unit_outcomes.csv", index=False)
    expected = pd.read_csv(evidence(root, RUN_D + "/frozen_rule_weighting_checks.csv"), dtype={"scope": str})
    expected = expected.loc[expected.weight.eq("unit")]
    audit.require("08D.unit_group_row_count", len(actual) == len(expected) == 24)
    audit.compare("08D.frozen_unit", actual, expected, ["scope", "leaf_id"], [
        "n_units", "n_source_records", "n_fires", "n_held", "n_burned_over",
        "held_fraction", "ci_lower", "ci_upper",
    ])


class SortedRanking:
    """Weighted AP/AUC with score ties preserved; no fitting is involved."""

    def __init__(self, y, p, fire_index):
        order = np.argsort(-p, kind="stable")
        self.y = y[order].astype(float)
        self.fire = fire_index[order]
        scores = p[order]
        self.starts = np.r_[0, np.flatnonzero(scores[1:] != scores[:-1]) + 1]

    def metrics(self, multiplicity):
        weights = multiplicity[self.fire]
        tp_group = np.add.reduceat(weights * self.y, self.starts)
        fp_group = np.add.reduceat(weights * (1 - self.y), self.starts)
        tp, fp = np.cumsum(tp_group), np.cumsum(fp_group)
        positive, negative = tp[-1], fp[-1]
        if positive == 0 or negative == 0:
            raise ValueError("Single-outcome primary bootstrap replicate; no redraw is permitted.")
        precision = np.divide(tp, tp + fp, out=np.zeros_like(tp), where=(tp + fp) > 0)
        return (float(np.sum(tp_group * precision) / positive),
                float(np.sum(fp_group * (tp - .5 * tp_group)) / (positive * negative)))


def reproduce_primary(root, output, audit, bootstrap):
    print("Reproducing nine primary Table II point estimates.", flush=True)
    frame = pd.read_parquet(evidence(root, PRIMARY_PREDICTIONS))
    audit.require("primary.unique_units", frame.unit_uid.is_unique and len(frame) == 304143)
    audit.require("primary.outcome_counts", frame.hold_label.value_counts().to_dict() == {1: 205926, 0: 98217})
    audit.require("primary.fire_folds", frame.groupby("_irwin_norm").outer_fold.nunique().eq(1).all())
    check_probabilities(audit, "primary.valid_probabilities", frame, ["pred_prob"])
    cohort = pd.read_parquet(root / "data/retained_fireline_units.parquet",
                             columns=["unit_uid", "_irwin_norm", "hold_label"])
    match = frame.merge(cohort, on="unit_uid", how="outer", validate="one_to_one",
                        suffixes=("_prediction", "_cohort"), indicator=True)
    audit.require("primary.retained_cohort_identity", match._merge.eq("both").all()
                  and match._irwin_norm_prediction.eq(match._irwin_norm_cohort).all()
                  and match.hold_label_prediction.eq(match.hold_label_cohort).all())
    y, p = frame.hold_label.to_numpy(int), frame.pred_prob.to_numpy(float)
    fires = np.array(sorted(frame._irwin_norm.unique()))
    audit.require("primary.fire_count", len(fires) == 381)
    fire_index = pd.Index(fires).get_indexer(frame._irwin_norm)
    stats = []
    for _, part in frame.groupby("_irwin_norm", sort=True):
        gy, gp = part.hold_label.to_numpy(int), part.pred_prob.to_numpy(float)
        loss = (gp - gy) ** 2
        q = np.clip(gp, 1e-6, 1 - 1e-6)
        logloss = -(gy * np.log(q) + (1 - gy) * np.log(1 - q))
        mixed = len(np.unique(gy)) == 2
        stats.append([len(part), gp.sum(), loss.sum(), logloss.sum(), loss.mean(), logloss.mean(),
                      average_precision_score(gy, gp) if mixed else np.nan,
                      roc_auc_score(gy, gp) if mixed else np.nan])
    stats = np.asarray(stats)
    mixed = np.isfinite(stats[:, 6])
    audit.require("primary.mixed_fire_count", mixed.sum() == 303)
    point = [p.mean(), average_precision_score(y, p), roc_auc_score(y, p),
             stats[:, 2].sum() / len(frame), stats[:, 3].sum() / len(frame),
             stats[:, 4].mean(), stats[:, 5].mean(), stats[mixed, 6].mean(), stats[mixed, 7].mean()]
    actual = pd.DataFrame({"metric": PRIMARY_METRICS, "estimate": point})
    actual.to_csv(output / "primary_point_metrics.csv", index=False)
    expected = pd.read_csv(evidence(root, RUN_PRIMARY + "/table_ii_metrics.csv"))
    audit.compare("primary.table_ii_points", actual, expected, ["metric"], ["estimate"])
    old = pd.read_csv(evidence(root, "outputs/primary_model_freeze_v1/PRIMARY_MODEL_POINT_METRICS_V1.csv"))
    old = old.loc[old.model_id.eq("05C_FIXED_ROW_RAW"), PRIMARY_METRICS]
    audit.require("primary.fixed_model_reference", len(old) == 1)
    old = pd.DataFrame({"metric": PRIMARY_METRICS, "estimate": old.iloc[0].to_numpy(float)})
    audit.compare("primary.original_points", actual, old, ["metric"], ["estimate"])
    if not bootstrap:
        return
    print("Reproducing all nine Table II intervals from 5,000 saved whole-fire draws.", flush=True)
    with np.load(evidence(root, RUN_PRIMARY + "/fire_multiplicities.npz"), allow_pickle=False) as saved:
        counts, saved_fires = saved["counts"].copy(), saved["fire_ids"].copy()
    audit.require("primary.bootstrap_fire_order", np.array_equal(saved_fires, fires))
    audit.require("primary.bootstrap_shape", counts.shape == (5000, 381))
    audit.require("primary.bootstrap_whole_fire_draws", np.issubdtype(counts.dtype, np.integer)
                  and (counts >= 0).all() and (counts.sum(axis=1) == 381).all())
    rng = np.random.default_rng(20260825)
    seed_matches = all(np.array_equal(counts[i], np.bincount(rng.integers(0, 381, size=381), minlength=381))
                       for i in range(5000))
    audit.require("primary.bootstrap_original_seed", seed_matches)
    rank = SortedRanking(y, p, fire_index)
    audit.require("primary.ranking_point_matches_sklearn",
                  np.allclose(rank.metrics(np.ones(381)), point[1:3], rtol=0, atol=TOLERANCE))
    values = np.empty((5000, 9))
    for i, count in enumerate(counts):
        mult = count.astype(float)
        total = np.sum(mult * stats[:, 0])
        ap, auc = rank.metrics(mult)
        values[i] = [np.sum(mult * stats[:, 1]) / total, ap, auc,
                     np.sum(mult * stats[:, 2]) / total, np.sum(mult * stats[:, 3]) / total,
                     np.sum(mult * stats[:, 4]) / mult.sum(), np.sum(mult * stats[:, 5]) / mult.sum(),
                     np.sum(mult[mixed] * stats[mixed, 6]) / mult[mixed].sum(),
                     np.sum(mult[mixed] * stats[mixed, 7]) / mult[mixed].sum()]
        if i in {0, 1, 2, 999, 2499, 4999}:
            weights = mult[fire_index]
            reference = [average_precision_score(y, p, sample_weight=weights),
                         roc_auc_score(y, p, sample_weight=weights)]
            audit.check(f"primary.weighted_ranking_replicate_{i}",
                        np.allclose([ap, auc], reference, rtol=0, atol=TOLERANCE))
        if (i + 1) % 1000 == 0:
            print(f"  Table II: {i + 1:,}/5,000 replicates.", flush=True)
    audit.require("primary.all_replicates_finite", np.isfinite(values).all())
    replicates = pd.DataFrame(values, columns=PRIMARY_METRICS)
    replicates["replicate"] = np.arange(5000)
    replicates.to_parquet(output / "primary_bootstrap_replicates.parquet", index=False)
    saved = pd.read_parquet(evidence(root, RUN_PRIMARY + "/bootstrap_replicates.parquet"))
    if "replicate" not in saved:
        saved = saved.reset_index()
    audit.compare("primary.bootstrap_replicates", replicates, saved, ["replicate"], PRIMARY_METRICS)
    intervals = actual.copy()
    intervals["ci_low"], intervals["ci_high"] = np.quantile(values, [.025, .975], axis=0, method="linear")
    intervals.to_csv(output / "primary_table_ii_metrics.csv", index=False)
    audit.compare("primary.table_ii_intervals", intervals, expected, ["metric"], ["estimate", "ci_low", "ci_high"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-root", "--release-root", dest="release_root", type=Path, default=Path(__file__).resolve().parents[1] / "dataset",
                        help="Release directory containing data/ and evidence/ (default: sibling dataset folder).")
    parser.add_argument("--output", type=Path,
                        help="NEW output directory; existing directories are refused (default: RELEASE/reproduced_results).")
    parser.add_argument("--primary-bootstrap", action="store_true",
                        help="Also recompute all 5,000 Table II bootstrap replicates and nine intervals (about one minute).")
    args = parser.parse_args()
    root = args.release_root.resolve()
    output = (args.output or Path.cwd() / "reproduced_results").resolve()
    protected = [root / name for name in ["data", "evidence", "code", "docs"]]
    if output == root or root in output.parents:
        parser.error("Output must be a new result directory outside data/, evidence/, code/, and docs/.")
    if output.exists():
        parser.error(f"Output already exists; choose a new --output directory: {output}")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    audit, error = Audit(), None
    try:
        reproduce_08e(root, output, audit)
        reproduce_frozen_conditions(root, output, audit)
        reproduce_primary(root, output, audit, args.primary_bootstrap)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        audit.check("execution_completed", False, error)
    passed = error is None and all(c["passed"] for c in audit.checks)
    report = {
        "status": "PASS" if passed else "FAIL", "absolute_tolerance": TOLERANCE,
        "relative_tolerance": 0, "training": "none; saved predictions remain fixed",
        "network": "none", "release_root": str(root), "output_directory": str(output),
        "primary_bootstrap_requested": args.primary_bootstrap,
        "primary_bootstrap_replicates_checked": 5000 if args.primary_bootstrap and passed else 0,
        "checks": audit.checks, "error": error, "seconds": time.perf_counter() - started,
        "versions": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "pyarrow": pyarrow.__version__,
                     "scikit-learn": sklearn.__version__},
        "notes": ["08E uses 2,000 multinomial whole-fire resamples per scope and clips log-loss probabilities at 1e-15.",
                  "08D uses 2,000 whole-fire resamples per frozen group; CRC32 seeds preserve the original scope and fire ordering.",
                  "Primary Table II uses the saved 5,000 whole-fire multiplicities from seed 20260825 and clips log loss at 1e-6.",
                  "All intervals use the 2.5th and 97.5th percentiles with linear interpolation.",
                  "Without --primary-bootstrap, primary point estimates are checked but primary intervals are not recomputed."],
    }
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(audit.checks).to_csv(output / "validation_checks.csv", index=False)
    print(f"{report['status']}: {sum(c['passed'] for c in audit.checks)}/{len(audit.checks)} checks; {output}", flush=True)
    if error:
        print(error, file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
