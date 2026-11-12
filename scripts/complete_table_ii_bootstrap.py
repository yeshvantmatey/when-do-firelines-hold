"""Complete Table II from fixed saved predictions; no model fitting.

The fire ordering, seed, draws, and percentile method match notebook 05E.
The three missing metrics use the same draws as the existing six metrics.
"""
from __future__ import annotations

import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260825
REPS = 5000
MODEL = "05C_FIXED_ROW_RAW"
INPUTS = {
    "predictions": ROOT / "data/processed/baseline_modeling_v1/oof_predictions/E_FULL_EXTENDED__row.parquet",
    "master": ROOT / "data/processed/modeling_table_assembly_v1/fireline_hold_modeling_master_v1.parquet",
    "point_metrics": ROOT / "outputs/primary_model_freeze_v1/PRIMARY_MODEL_POINT_METRICS_V1.csv",
    "existing_intervals": ROOT / "outputs/primary_model_freeze_v1/INCIDENT_CLUSTER_BOOTSTRAP_CI_V1.csv",
    "original_notebook": ROOT / "notebooks/05E_primary_model_freeze_and_incident_uncertainty.ipynb",
}
LABELS = {
    "mean_pred": "Mean predicted Held probability",
    "pooled_pr_auc": "Pooled AP",
    "pooled_roc_auc": "Pooled ROC-AUC",
    "pooled_brier": "Pooled Brier score",
    "pooled_log_loss": "Pooled log loss",
    "incident_macro_brier": "Fire-average Brier score",
    "incident_macro_log_loss": "Fire-average log loss",
    "mixed_incident_macro_pr_auc": "Within-fire AP",
    "mixed_incident_macro_roc_auc": "Within-fire ROC-AUC",
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class SortedRanking:
    """Exact weighted AP/AUC with a single score sort and explicit tie groups."""

    def __init__(self, y, p, fire_index):
        order = np.argsort(-p, kind="stable")
        self.y = y[order].astype(np.float64)
        self.fire = fire_index[order]
        scores = p[order]
        self.starts = np.r_[0, np.flatnonzero(scores[1:] != scores[:-1]) + 1]

    def metrics(self, multiplicity):
        weights = multiplicity[self.fire]
        tp_group = np.add.reduceat(weights * self.y, self.starts)
        fp_group = np.add.reduceat(weights * (1 - self.y), self.starts)
        tp = np.cumsum(tp_group)
        fp = np.cumsum(fp_group)
        positive, negative = tp[-1], fp[-1]
        if positive == 0 or negative == 0:
            raise ValueError("Single-outcome bootstrap replicate; do not silently redraw.")
        precision = np.divide(tp, tp + fp, out=np.zeros_like(tp), where=(tp + fp) > 0)
        ap = np.sum(tp_group * precision) / positive
        # Each negative gets credit for higher-scoring positives and half of ties.
        auc = np.sum(fp_group * (tp - .5 * tp_group)) / (positive * negative)
        return float(ap), float(auc)


def render_latex(summary):
    lines = [
        r"\begin{table}[!t]",
        r"\centering\footnotesize\setlength{\tabcolsep}{3pt}",
        r"\caption{Primary LightGBM performance on fires excluded from training. Held is the positive outcome.}",
        r"\label{tab:primary}",
        r"\begin{tabular}{>{\raggedright\arraybackslash}p{1.7in}>{\raggedright\arraybackslash}p{0.5in}>{\raggedright\arraybackslash}p{0.95in}}",
        r"\toprule",
        r"\textbf{Metric} & \textbf{Estimate} & \textbf{95\% bootstrap interval} \\",
        r"\midrule",
    ]
    for row in summary.itertuples(index=False):
        lines.append(f"{row.label} & {row.estimate:.3f} & {row.ci_low:.3f}--{row.ci_high:.3f} " + r"\\")
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{\columnwidth}\footnotesize",
        r"AP denotes average precision. ROC-AUC denotes the area under the receiver operating characteristic curve. Pooled measures combine all 304,143 test fireline units. The mean predicted Held probability gives each fireline unit equal weight. Fire-average Brier score and log loss average errors within each fire and then equally across all 381 fires. Within-fire AP and ROC-AUC are calculated separately for the 303 fires containing both outcomes and then averaged equally across those fires. Intervals are the 2.5th and 97.5th percentiles from 5,000 bootstrap resamples of the 381 fires with replacement. Each selected fire contributes all its fireline units; within-fire ranking uses only selected fires containing both outcomes. Predictions remain fixed throughout resampling.",
        r"\end{minipage}",
        r"\end{table}",
    ]
    return "\n".join(lines) + "\n"


def run(output_root=None):
    started = time.perf_counter()
    checks = []

    def check(condition, name):
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    if output_root is None:
        output_root = ROOT / "outputs/table_ii_bootstrap_completion_v1"
    run_dir = Path(output_root) / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {k: {"path": str(p.relative_to(ROOT)), "sha256": sha256(p),
                    "bytes": p.stat().st_size} for k, p in INPUTS.items()}
    frame = pd.read_parquet(INPUTS["predictions"])
    check(len(frame) == 304143 and frame.unit_uid.is_unique, "304143_unique_saved_predictions")
    check(not frame[["unit_uid", "_irwin_norm", "hold_label", "pred_prob"]].isna().any().any(), "no_missing_ids_outcomes_probabilities")
    check(frame.hold_label.value_counts().to_dict() == {1: 205926, 0: 98217}, "outcome_counts")
    check(frame.groupby("_irwin_norm").outer_fold.nunique().eq(1).all(), "one_test_fold_per_fire")
    master = pd.read_parquet(INPUTS["master"], columns=["unit_uid", "_irwin_norm", "hold_label"])
    match = frame.merge(master, on="unit_uid", how="outer", validate="one_to_one", indicator=True,
                        suffixes=("_pred", "_master"))
    check(match._merge.eq("both").all() and
          match._irwin_norm_pred.eq(match._irwin_norm_master).all() and
          match.hold_label_pred.eq(match.hold_label_master).all(), "exact_cohort_identity_and_labels")
    del master, match
    y = frame.hold_label.to_numpy(dtype=np.int8)
    p = frame.pred_prob.to_numpy(dtype=float)
    check(np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(), "finite_probabilities_in_range")
    fires = np.array(sorted(frame._irwin_norm.unique()))
    check(len(fires) == 381, "381_fires")
    fire_index = pd.Index(fires).get_indexer(frame._irwin_norm)
    rank = SortedRanking(y, p, fire_index)
    old_points = pd.read_csv(INPUTS["point_metrics"]).set_index("model_id").loc[MODEL]
    old_cis = pd.read_csv(INPUTS["existing_intervals"])
    old_cis = old_cis.loc[old_cis.model_id.eq(MODEL)].set_index("metric")
    point = {"mean_pred": p.mean(), "pooled_pr_auc": average_precision_score(y, p),
             "pooled_roc_auc": roc_auc_score(y, p)}
    stats = []
    for fire, g in frame.groupby("_irwin_norm", sort=True):
        gy, gp = g.hold_label.to_numpy(int), g.pred_prob.to_numpy(float)
        loss = (gp - gy) ** 2
        cp = np.clip(gp, 1e-6, 1 - 1e-6)
        logloss = -(gy * np.log(cp) + (1 - gy) * np.log(1 - cp))
        mixed = len(np.unique(gy)) == 2
        stats.append([len(g), gp.sum(), loss.sum(), logloss.sum(), loss.mean(), logloss.mean(),
                      average_precision_score(gy, gp) if mixed else np.nan,
                      roc_auc_score(gy, gp) if mixed else np.nan])
    stats = np.asarray(stats)
    mixed = np.isfinite(stats[:, 6])
    check(mixed.sum() == 303, "303_mixed_outcome_fires")
    point.update({"pooled_brier": stats[:, 2].sum() / len(frame),
                  "pooled_log_loss": stats[:, 3].sum() / len(frame),
                  "incident_macro_brier": stats[:, 4].mean(),
                  "incident_macro_log_loss": stats[:, 5].mean(),
                  "mixed_incident_macro_pr_auc": stats[mixed, 6].mean(),
                  "mixed_incident_macro_roc_auc": stats[mixed, 7].mean()})
    for metric, value in point.items():
        check(np.isclose(value, old_points[metric], rtol=0, atol=2e-12), "reproduced_point_" + metric)

    # A tied-score fixture includes zero weights and repeated complete groups.
    sy = np.array([0, 1, 0, 1, 1, 0, 1, 0])
    sp = np.array([.9, .9, .6, .6, .6, .1, .1, .1])
    sf = np.array([0, 0, 1, 1, 1, 2, 2, 3])
    sm = np.array([0., 3., 2., 1.])
    sv = SortedRanking(sy, sp, sf).metrics(sm)
    check(np.allclose(sv, [average_precision_score(sy, sp, sample_weight=sm[sf]),
                          roc_auc_score(sy, sp, sample_weight=sm[sf])], rtol=0, atol=2e-12),
          "ties_and_zero_weights_match_sklearn")
    check(np.allclose(rank.metrics(np.ones(381)), [point["pooled_pr_auc"], point["pooled_roc_auc"]],
                      rtol=0, atol=2e-12), "optimized_unweighted_ranking_matches_sklearn")
    rng = np.random.default_rng(SEED)
    multiplicities = np.empty((REPS, 381), dtype=np.uint16)
    values = np.empty((REPS, len(LABELS)))
    validation_draws = {0, 1, 2, 999, 2499, 4999}
    print("Starting 5,000 whole-fire resamples; fixed predictions; seed 20260825.", flush=True)
    for rep in range(REPS):
        draw = rng.integers(0, 381, size=381)
        mult = np.bincount(draw, minlength=381).astype(float)
        multiplicities[rep] = mult
        total_units = np.sum(mult * stats[:, 0])
        ap, auc = rank.metrics(mult)
        values[rep] = [np.sum(mult * stats[:, 1]) / total_units, ap, auc,
                       np.sum(mult * stats[:, 2]) / total_units,
                       np.sum(mult * stats[:, 3]) / total_units,
                       np.sum(mult * stats[:, 4]) / mult.sum(),
                       np.sum(mult * stats[:, 5]) / mult.sum(),
                       np.sum(mult[mixed] * stats[mixed, 6]) / mult[mixed].sum(),
                       np.sum(mult[mixed] * stats[mixed, 7]) / mult[mixed].sum()]
        if rep in validation_draws:
            unit_w = mult[fire_index]
            check(np.allclose([ap, auc], [average_precision_score(y, p, sample_weight=unit_w),
                                        roc_auc_score(y, p, sample_weight=unit_w)],
                              rtol=0, atol=2e-12), "weighted_sklearn_match_rep_" + str(rep))
            if rep == 0:
                copies = np.repeat(np.arange(len(y)), unit_w.astype(int))
                check(np.allclose([values[rep, 0], ap, auc],
                                  [p[copies].mean(), average_precision_score(y[copies], p[copies]),
                                   roc_auc_score(y[copies], p[copies])], rtol=0, atol=2e-12),
                      "literal_whole_fire_duplication_matches_weighted_metrics")
        if (rep + 1) % 500 == 0:
            print(f"{rep + 1:,}/5,000 resamples complete ({time.perf_counter() - started:.1f}s).", flush=True)
    check(np.isfinite(values).all(), "all_replicates_defined_and_finite")
    check((multiplicities.sum(axis=1) == 381).all(), "381_whole_fire_draws_in_every_replicate")
    boot = pd.DataFrame(values, columns=LABELS)
    rows = []
    for metric, label in LABELS.items():
        lo, hi = np.quantile(boot[metric], [.025, .975], method="linear")
        if metric in old_cis.index:
            check(np.allclose([lo, hi], old_cis.loc[metric, ["ci_low", "ci_high"]].to_numpy(float),
                              rtol=0, atol=2e-12), "reproduced_existing_interval_" + metric)
            # Preserve the exact original saved decimal values for the other six rows.
            lo, hi = old_cis.loc[metric, ["ci_low", "ci_high"]].to_numpy(float)
        rows.append({"metric": metric, "label": label, "estimate": float(old_points[metric]),
                     "ci_low": float(lo), "ci_high": float(hi),
                     "new_interval": metric not in old_cis.index})
    for key, path in INPUTS.items():
        check(sha256(path) == manifest[key]["sha256"], "original_input_unchanged_" + key)
    summary = pd.DataFrame(rows)
    summary.to_csv(run_dir / "table_ii_metrics.csv", index=False)
    boot.index.name = "replicate"
    boot.to_parquet(run_dir / "bootstrap_replicates.parquet", index=True)
    np.savez_compressed(run_dir / "fire_multiplicities.npz", counts=multiplicities, fire_ids=fires.astype(str))
    (run_dir / "primary_table.tex").write_text(render_latex(summary), encoding="utf-8")
    report = {"status": "PASS", "seed": SEED, "replicates": REPS, "fires_per_draw": 381,
              "fire_order": "sorted _irwin_norm", "draw": "default_rng(seed).integers(0,381,size=381)",
              "interval": "2.5th and 97.5th percentiles; numpy linear interpolation",
              "training": "none; saved predictions fixed", "stratification": "none",
              "source_manifest": manifest, "checks": checks,
              "versions": {"python": platform.python_version(), "numpy": np.__version__,
                           "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
              "script_sha256": sha256(Path(__file__)), "seconds": time.perf_counter() - started,
              "note": "All six previously reported intervals reproduced; original input files unchanged."}
    (run_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(summary[["label", "estimate", "ci_low", "ci_high"]].to_string(index=False), flush=True)
    print("Saved:", run_dir, flush=True)
    return run_dir, summary


if __name__ == "__main__":
    run()
