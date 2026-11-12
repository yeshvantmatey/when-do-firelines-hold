"""Create the source-only archival snapshot without executing research code.

Run from the original project root with its Python interpreter. Writes only the
staging code tree and docs/CODE_GUIDE.md. Source files are never modified.
Static dependency analysis is deliberately conservative, not a runnable DAG.
"""
from __future__ import annotations

import ast
import copy
import csv
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "zenodo_release_staging_v1"
CODE = STAGE / "code"
AUDIT = CODE / "audit"
NOW = datetime.now(timezone.utc).isoformat()

# Selection is based on actual input references and saved output evidence.
SELECTION = [
    ("01_fireline_nirops_joinability_audit", "source audit", "Initial archive extraction and joinability; raw source products required. Saved audit report is a one-byte placeholder, not successful-run evidence.", "outputs/audit/JOINABILITY_REPORT.md"),
    ("02b_fireline_version_resolution", "deduplication", "Final version resolution; supersedes the 02 current-row-only canonical file.", "outputs/fireline_version_resolution/FIRELINE_VERSION_RESOLUTION_REPORT.md"),
    ("03G_v2_fireline_temporal_production", "temporal precursor", "Retained because 03L reuses this production segmentation and 03H cohort.", "data/processed/fireline_dynamic_250m/PRODUCTION_CONFIG.json"),
    ("03H_v2_temporal_dataset_quality_audit", "temporal precursor", "Writes the v2 cohort read by corrected 03L production.", "data/processed/fireline_dynamic_250m/ml_cohort/DATASET_CARD_V2.json"),
    ("03L_corrected_local_unit_production", "corrected units", "Final corrected local geometry and NIROPS evidence production.", "data/processed/fireline_corrected_local_250m_10m/PRODUCTION_CONFIG.json"),
    ("03M_unit_evidence_rule_audit", "target evidence", "Weighted evidence audit feeding frozen 03N labels.", "outputs/unit_evidence_rule_audit"),
    ("03N_freeze_corrected_ml_cohort", "cohort freeze", "Final supported cohort and timing subset; precedes clean-anchor modeling selection.", "data/processed/fireline_corrected_local_250m_10m/frozen_cohort/DATASET_CARD_FROZEN_V1.json"),
    ("04A_v2_dynamic_approach_features", "approach precursor", "Required by 04A v3 and 08D raster-distance comparison; not an interchangeable older version.", "outputs/dynamic_approach_features_v2"),
    ("04A_v3_extended_exact_approach", "approach production", "Final exact approach features and clean operational anchors.", "outputs/extended_exact_approach_v3"),
    ("04B1_v2_HRRR_production_features", "weather production", "Final HRRR extraction and gust cleanup consumed by 05A.", "outputs/hrrr_production_v2/PRODUCTION_GROUP_MANIFEST.csv"),
    ("04C1_3DEP_terrain_production", "terrain production", "Final terrain features and sample/block indexes used by LANDFIRE.", "outputs/terrain_3dep_production_v1/TERRAIN_BLOCK_MANIFEST.csv"),
    ("04D0_LANDFIRE_pre_event_vintage_audit", "LANDFIRE provenance", "Temporal vintage mapping audit retained as source provenance.", "outputs/landfire_vintage_audit_v1"),
    ("04D1B_v2_LANDFIRE_provenance_audit", "LANDFIRE provenance", "Final independent fuel product provenance audit, not an extraction pilot.", "outputs/landfire_provenance_audit_v2/LANDFIRE_PROVENANCE_AUDIT_V2_REPORT.md"),
    ("04D1C_v5_LANDFIRE_feature_architecture", "LANDFIRE contract", "Frozen feature contract used by final production and consolidation.", "data/processed/landfire_feature_architecture_v5/landfire_feature_spec_v5.json"),
    ("04D1E_v3_LANDFIRE_recovery_resume", "LANDFIRE resolved production", "Last full extraction/recovery implementation; v5 only repairs its final shards.", "outputs/landfire_resolved_vintage_full_production_v1/PRODUCTION_BLOCK_MANIFEST_V3.csv"),
    ("04D1E_v5_LANDFIRE_schema_repair_and_finalize", "LANDFIRE finalization", "Final schema repair applied after v3 extraction; does not replace extraction code.", "outputs/landfire_resolved_vintage_full_production_v1"),
    ("04D1F_v2_LANDFIRE_archive_inventory_and_provenance", "LANDFIRE archive inventory", "LF2020 inventory and candidate LF2019L archive inputs used by later acquisition.", "outputs/landfire_archive_inventory_v2/LANDFIRE_ARCHIVE_PROVENANCE_MANIFEST_V2.csv"),
    ("04D1F_v3_LANDFIRE_LF2019L_candidate_disambiguation", "LANDFIRE archive inventory", "Resolves LF2019L archive candidates; complements v2 LF2020 inventory.", "outputs/landfire_archive_inventory_v3"),
    ("04D1G_v7_LANDFIRE_archive_acquisition_and_validation", "LANDFIRE archive acquisition", "Final acquisition/validation implementation; source archives are not redistributed.", "outputs/landfire_archive_acquisition_v7/LANDFIRE_ARCHIVE_PROVENANCE_MANIFEST_VALIDATED_V7.csv"),
    ("04D1I_v2_LANDFIRE_archived_vintage_full_production", "LANDFIRE archived production", "Final full archived-vintage extraction; pilot implementation is inlined.", "outputs/landfire_archived_vintage_production_v1"),
    ("04D1J_LANDFIRE_five_vintage_consolidation", "LANDFIRE consolidation", "Final five-vintage feature table consumed by 05A.", "outputs/landfire_five_vintage_consolidation_v1/FIVE_VINTAGE_EXPECTED_SHARD_MANIFEST_V1.csv"),
    ("05A_modeling_table_assembly_and_feature_manifest", "model table", "Assembles the frozen 304143-unit modeling master from feature products.", "outputs/modeling_table_assembly_v1/MODELING_COLUMN_MANIFEST_V1.csv"),
    ("05B_feature_sets_and_incident_split_design", "design freeze", "Frozen incident folds, feature sets, and training weights.", "outputs/modeling_design_v1/FEATURE_SET_MANIFEST_V1.csv"),
    ("05C_incident_held_out_baseline_modeling", "primary OOF", "Fixed LightGBM experiments; E_FULL_EXTENDED row-weighted fit supplies paper primary OOF predictions.", "outputs/baseline_modeling_v1/SOFTWARE_VERSIONS_V1.csv"),
    ("05C1_baseline_calibration_and_interpretation_audit", "primary audit", "Postprocesses fixed baseline predictions and robust calibration metrics.", "outputs/baseline_calibration_audit_v1"),
    ("05D_nested_tuning_and_calibration_finalists", "model comparison", "Nested tuning/calibration comparison considered before primary freeze.", "outputs/nested_tuning_calibration_v1/SELECTED_CONFIGS_BY_OUTER_FOLD_V1.csv"),
    ("05E_primary_model_freeze_and_incident_uncertainty", "primary freeze", "Primary decision and whole-fire bootstrap uncertainty.", "outputs/primary_model_freeze_v1/PRIMARY_MODEL_FREEZE_REPORT_V1.md"),
    ("05E1_fixed_primary_nested_calibration_audit", "calibration audit", "Fixed-primary leakage-safe nested recalibration audit.", "outputs/fixed_primary_nested_calibration_v1"),
    ("05E2_primary_table_bootstrap_completion", "Table II completion", "Completes three intervals from fixed predictions without fitting models.", "outputs/table_ii_bootstrap_completion_v1"),
    ("05F_final_full_data_fit_and_model_serialization", "full-data model", "Fits final serialization; model card states this is not a performance estimate.", "models/fireline_hold_primary_v1/fireline_hold_primary_v1_model_card.json"),
    ("05G_observation_process_proxy_sensitivity", "sensitivity", "Observation-process predictor sensitivity.", "outputs/observation_process_proxy_sensitivity_v1"),
    ("05H_forward_temporal_generalization_audit", "temporal evaluation", "Forward-year evaluation with frozen model contract.", "outputs/forward_temporal_generalization_v1/FORWARD_TEMPORAL_MODEL_CONTRACT_V1.json"),
    ("05I_frozen_model_interpretation_and_publication_figures", "interpretation", "Frozen model interpretation and saved publication summaries.", "outputs/frozen_model_interpretation_v1"),
    ("05I_held_vs_burned_over_input_regimes", "condition precursor", "Legacy input-regime analyses read by 08A; distinct from the other 05I notebook.", "outputs/input_regimes_v1/INPUT_REGIME_FEATURE_CONTRACT_V1.csv"),
    ("05J_manuscript_results_assembly", "results assembly", "Assembles scientific results and traceability manifest, with no fitting.", "outputs/manuscript_assembly_v1/MANUSCRIPT_REPRODUCIBILITY_MANIFEST_V1.csv"),
    ("06A_alternative_tabular_model_benchmark", "alternative models", "Final fixed alternative-model training notebook; primary remains frozen.", "outputs/alternative_model_benchmark_v1/SOFTWARE_VERSIONS_V1.csv"),
    ("06A_v2_alternative_model_benchmark_finalize", "alternative finalization", "Corrects runtime summaries after completed 06A fits; not a replacement for training.", "outputs/alternative_model_benchmark_v1"),
    ("06B_nested_challenger_tuning_calibration_thresholds", "exploratory challengers", "GPU nested challenger follow-up; exploratory and does not replace primary.", "outputs/nested_challenger_gpu_v1/SELECTED_CHALLENGER_CONFIGS_V1.csv"),
    ("06C_lightgbm_temporal_decision_policy", "decision sensitivity", "Scenario-specific temporal threshold audit from frozen predictions.", "outputs/lightgbm_temporal_decision_policy_v1"),
    ("08A_fireline_characteristics_and_condition_outcomes", "08A conditions", "Final non-smoke recorded run.", "outputs/08_condition_outcomes/08A_20260930T220658_104767Z_614ae3/08A_run_manifest.json"),
    ("08B_original_firelines_scale_and_selection", "08B scale and selection", "Final non-smoke recorded run.", "outputs/08_condition_outcomes/08B_20260930T224636_898345Z_38d03c/08B_run_manifest.json"),
    ("08C_interpretable_condition_rules", "08C rules", "Final non-smoke recorded run; direct-outcome rules are exploratory.", "outputs/08_condition_outcomes/08C_20260930T234354_724489Z_3a31ea/08C_run_manifest.json"),
    ("08D_baseline_and_condition_robustness", "08D robustness", "Final non-smoke recorded run; designed after inspection of 08C.", "outputs/08_condition_outcomes/08D_20261001T002458_892164Z_f3e697/08D_run_manifest.json"),
    ("08E_reviewer_diagnostics", "08E diagnostics", "Final complete non-smoke run; smoke runs excluded.", "outputs/08_condition_outcomes/08E_20261105T211309_533108Z_9ff65f/08E_run_manifest.json"),
    ("08_series_paper_figure_refresh", "saved-result figures", "Replots saved 08-series results without new training.", "overleaf_revision_08_series_20261001/revision_figures_08"),
    ("08_series_condition_figure_publication", "saved-result figures", "Publication condition figure from completed 08D results.", "overleaf_revision_08_series_20261001/revision_figures_08"),
]
SCRIPTS = {
    "complete_table_ii_bootstrap.py": "Same fixed-prediction Table II completion as 05E2.",
    "build_zenodo_core_v1.py": "Original construction and validation of the two retained core release tables.",
}


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def source_hash(doc):
    return hashlib.sha256(json.dumps([c["source"] for c in doc["cells"]], ensure_ascii=False).encode()).hexdigest()


def fingerprint_08e(doc):
    normalized = []
    for cell in doc["cells"]:
        text = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        if cell["cell_type"] == "code":
            tree = ast.parse(text)
            for node in tree.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "RESUME_RUN_DIR":
                    node.value = ast.Constant(value="__OPERATIONAL_RESUME_PATH__")
            normalized.append(["code", ast.dump(tree, include_attributes=False)])
        else:
            normalized.append([cell["cell_type"], text])
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False).encode()).hexdigest()


def secret_candidates(text):
    findings = []
    patterns = {
        "private_key_marker": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "aws_access_key_literal": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
        "github_token_literal": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b",
        "provider_token_literal": r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{30,}|hf_[A-Za-z0-9]{30,})\b",
        "credential_url": r"https?://[^\s/:]+:[^\s/@]+@",
    }
    for kind, pattern in patterns.items():
        for m in re.finditer(pattern, text):
            findings.append((kind, text[:m.start()].count("\n") + 1))
    # Never emit matching values. This scanner does not prove the absence of secrets.
    assignment = re.compile(r'''(?im)^\s*(?:[A-Za-z_]*?(?:api_key|access_token|auth_token|password|secret)[A-Za-z_]*)\s*=\s*[rubf]*["']([^"'\n]{12,})["']''')
    for m in assignment.finditer(text):
        value = m.group(1)
        if not re.search(r"example|placeholder|your_|your |none|change|https?://|\{|\}|environ", value, re.I):
            findings.append(("credential_named_literal_assignment", text[:m.start()].count("\n") + 1))
    return findings


def relative_path(value):
    value = value.replace("\\", "/")
    prefix = ROOT.as_posix()
    if value.lower().startswith(prefix.lower()): return value[len(prefix):].lstrip("/")
    return value.removeprefix("__PROJECT_ROOT__/")


def availability(value):
    rel = relative_path(value)
    dynamic = any(c in rel for c in "{}*?")
    try:
        workspace = (ROOT / rel).exists() if not dynamic else None
        candidate = (STAGE / "evidence" / rel)
        if rel.startswith(("notebooks/", "scripts/")): candidate = CODE / rel
        release = candidate.exists() if not dynamic else None
    except OSError:
        workspace = release = None
        candidate = Path("unresolved")
    return rel, workspace, str(candidate.relative_to(STAGE)) if candidate.is_relative_to(STAGE) else str(candidate), release


def eval_static(node, env):
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, type(None))): return node.value
    if isinstance(node, ast.Name): return env.get(node.id)
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else ""
        if name in ("find_root", "find_project_root"): return "__PROJECT_ROOT__"
        if name in ("Path", "str") and node.args: return eval_static(node.args[0], env)
    if isinstance(node, ast.BinOp):
        left, right = eval_static(node.left, env), eval_static(node.right, env)
        if isinstance(left, str) and isinstance(right, str):
            if isinstance(node.op, ast.Div): return left.rstrip("/\\") + "/" + right
            if isinstance(node.op, ast.Add): return left + right
    if isinstance(node, ast.JoinedStr):
        out = ""
        for v in node.values:
            if isinstance(v, ast.Constant): out += str(v.value)
            else:
                known = eval_static(v.value, env)
                out += str(known) if known is not None else "{" + ast.unparse(v.value) + "}"
        return out
    return None


def analyze_source(source_file, cells):
    imports, paths, absolutes, parsing = [], [], [], []
    env = {"PROJECT_ROOT": "__PROJECT_ROOT__", "ROOT": "__PROJECT_ROOT__"}
    seen = set()
    for cell_number, source in cells:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            parsing.append({"source_file": source_file, "cell": cell_number, "status": "syntax_not_parsed", "line": exc.lineno, "note": "May be IPython magic; code was not altered."})
            tree = None
        if tree:
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    value = eval_static(node.value, env)
                    for target in node.targets:
                        if isinstance(target, ast.Name) and value is not None:
                            env[target.id] = value
                            if isinstance(value, str) and ("__PROJECT_ROOT__" in value or re.match(r"^[A-Za-z]:[/\\]", value)):
                                rel, exists, lookup, released = availability(value)
                                key = (cell_number, target.id, rel)
                                if key not in seen:
                                    seen.add(key)
                                    paths.append({"source_file": source_file, "cell": cell_number, "line": node.lineno, "variable": target.id, "path": rel, "evidence": "static_path_assignment_input_or_output", "exists_in_original_workspace": exists, "release_lookup": lookup, "present_at_audit_time": released})
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import): modules = [x.name for x in node.names]
                if isinstance(node, ast.ImportFrom): modules = [node.module or ""]
                for module in modules:
                    top = module.split(".")[0]
                    imports.append({"source_file": source_file, "cell": cell_number, "line": node.lineno, "module": module, "top_level_module": top, "standard_library": top in sys.stdlib_module_names})
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    value = node.value
                    if re.match(r"^[A-Za-z]:[/\\]", value) and "\n" not in value:
                        absolutes.append({"source_file": source_file, "cell": cell_number, "line": node.lineno, "absolute_path": value, "action": "Retained verbatim for archival source fidelity; adapt a separate working copy before execution."})
                    if re.match(r"^(?:data|outputs|models|Fireline_QAQC_2017_2024|NIROPS_2020_2024)[/\\]", value) and "\n" not in value and len(value) < 500:
                        rel, exists, lookup, released = availability(value)
                        key = (cell_number, "literal", rel)
                        if key not in seen:
                            seen.add(key)
                            paths.append({"source_file": source_file, "cell": cell_number, "line": node.lineno, "variable": "", "path": rel, "evidence": "path_literal_input_or_output", "exists_in_original_workspace": exists, "release_lookup": lookup, "present_at_audit_time": released})
    return imports, paths, absolutes, parsing


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    selection = {name + ".ipynb": (stage, reason, evidence) for name, stage, reason, evidence in SELECTION}
    rows, hashes, findings, import_rows, path_rows, absolute_rows, parse_rows, mapping = [], [], [], [], [], [], [], []
    original_hashes = {}
    for source in sorted((ROOT / "notebooks").glob("*.ipynb")):
        if source.name not in selection:
            reason = "Superseded, exploratory pilot, acquisition prototype, or editorial manuscript-building iteration; not part of selected archival chain."
            if source.name == "02_fireline_deduplication_audit.ipynb": reason = "Superseded by 02b; 02b explicitly prohibits use of the previous current-row-only canonical file."
            rows.append(dict(source_file=source.relative_to(ROOT).as_posix(), stage="excluded", archival_status="excluded", reason=reason, evidence_path="", evidence_exists="", saved_source_hash_status="", archive_path=""))
            continue
        stage, reason, evidence = selection[source.name]
        doc = json.loads(source.read_text(encoding="utf-8-sig"))
        cells = [(i, "".join(c.get("source", []))) for i, c in enumerate(doc["cells"], 1)]
        detected = [(i, kind, line) for i, text in cells for kind, line in secret_candidates(text)]
        if detected:
            for cell, kind, line in detected: findings.append(dict(source_file=source.relative_to(ROOT).as_posix(), cell=cell, line=line, pattern=kind, action="excluded_pending_review_values_not_recorded"))
            rows.append(dict(source_file=source.relative_to(ROOT).as_posix(), stage=stage, archival_status="excluded_secret_candidate", reason="Credential-like source detected; matching values intentionally not recorded.", evidence_path=evidence, evidence_exists=(ROOT / evidence).exists(), saved_source_hash_status="", archive_path=""))
            continue
        before = sha(source)
        original_hashes[source] = before
        clean = copy.deepcopy(doc)
        cleared_outputs = cleared_counts = 0
        removed_metadata = []
        for key in ("widgets", "execution"):
            if key in clean.get("metadata", {}): clean["metadata"].pop(key); removed_metadata.append("notebook." + key)
        for i, cell in enumerate(clean["cells"], 1):
            if cell.get("cell_type") == "code":
                cleared_outputs += len(cell.get("outputs", []))
                cleared_counts += cell.get("execution_count") is not None
                cell["outputs"] = []
                cell["execution_count"] = None
            for key in ("execution", "ExecuteTime", "executionInfo"):
                if key in cell.get("metadata", {}): cell["metadata"].pop(key); removed_metadata.append(f"cell_{i}.{key}")
        dest = CODE / "notebooks" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(clean, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        roundtrip = json.loads(dest.read_text(encoding="utf-8"))
        assert [(c["cell_type"], c["source"]) for c in doc["cells"]] == [(c["cell_type"], c["source"]) for c in roundtrip["cells"]]
        saved_status = "no_saved_notebook_source_hash; artifact_link_only"
        if source.name.startswith(tuple("08" + c for c in "ABCDE")):
            manifest = json.loads((ROOT / evidence).read_text(encoding="utf-8-sig"))
            saved = manifest.get("notebook_source_hash", manifest.get("configuration", {}).get("source_sha256"))
            actual = fingerprint_08e(doc) if source.name.startswith("08E") else source_hash(doc)
            saved_status = "matches_saved_source_hash" if saved == actual else "MISMATCH_saved_source_hash"
            mapping.append(dict(source_file=source.relative_to(ROOT).as_posix(), manifest=evidence, saved_source_hash=saved, current_source_hash=actual, algorithm="08E AST-normalized except resume path" if source.name.startswith("08E") else "sha256 JSON list of all cell source values", status=saved_status))
        rows.append(dict(source_file=source.relative_to(ROOT).as_posix(), stage=stage, archival_status="selected_archival_source_not_portable_pipeline", reason=reason, evidence_path=evidence, evidence_exists=(ROOT / evidence).exists(), saved_source_hash_status=saved_status, archive_path=dest.relative_to(STAGE).as_posix()))
        hashes.append(dict(source_path=source.relative_to(ROOT).as_posix(), archive_path=dest.relative_to(STAGE).as_posix(), original_sha256=before, archive_sha256=sha(dest), source_cells_sha256=source_hash(doc), archive_source_cells_sha256=source_hash(roundtrip), source_preserved=True, outputs_removed=cleared_outputs, execution_counts_cleared=cleared_counts, metadata_keys_removed=";".join(sorted(set(removed_metadata)))))
        analyses = analyze_source(source.relative_to(ROOT).as_posix(), [(i, "".join(c["source"])) for i, c in enumerate(doc["cells"], 1) if c["cell_type"] == "code"])
        for target, extra in zip((import_rows, path_rows, absolute_rows, parse_rows), analyses): target.extend(extra)
    script_index = []
    for source in sorted((ROOT / "scripts").glob("*.py")):
        selected = source.name in SCRIPTS
        script_index.append(dict(source_file=source.relative_to(ROOT).as_posix(), archival_status="selected_unchanged" if selected else "excluded", reason=SCRIPTS.get(source.name, "Manuscript/editorial assembly or exploratory GPU/preflight utility outside selected release computation.")))
        if not selected: continue
        content = source.read_text(encoding="utf-8-sig")
        detected = secret_candidates(content)
        if detected: raise RuntimeError(f"Secret-pattern candidate in selected script {source.name}; copy withheld")
        dest = CODE / "scripts" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        before = sha(source); original_hashes[source] = before
        shutil.copy2(source, dest)
        hashes.append(dict(source_path=source.relative_to(ROOT).as_posix(), archive_path=dest.relative_to(STAGE).as_posix(), original_sha256=before, archive_sha256=sha(dest), source_cells_sha256="", archive_source_cells_sha256="", source_preserved=before == sha(dest), outputs_removed=0, execution_counts_cleared=0, metadata_keys_removed=""))
        analyses = analyze_source(source.relative_to(ROOT).as_posix(), [(1, content)])
        for target, extra in zip((import_rows, path_rows, absolute_rows, parse_rows), analyses): target.extend(extra)
    write_csv(CODE / "NOTEBOOK_INDEX.csv", rows)
    write_csv(CODE / "SCRIPT_INDEX.csv", script_index)
    write_csv(AUDIT / "SOURCE_SHA256.csv", hashes)
    write_csv(AUDIT / "NOTEBOOK_MANIFEST_MATCHES.csv", mapping)
    write_csv(AUDIT / "SECRET_PATTERN_SCAN.csv", findings, ["source_file", "cell", "line", "pattern", "action"])
    write_csv(AUDIT / "IMPORT_INVENTORY.csv", import_rows)
    write_csv(AUDIT / "LOCAL_PATH_INVENTORY.csv", path_rows)
    write_csv(AUDIT / "ABSOLUTE_PATHS.csv", absolute_rows, ["source_file", "cell", "line", "absolute_path", "action"])
    write_csv(AUDIT / "STATIC_PARSE_LIMITATIONS.csv", parse_rows, ["source_file", "cell", "status", "line", "note"])
    envdir = CODE / "environment"; envdir.mkdir(exist_ok=True)
    candidates = [ROOT / "outputs/baseline_modeling_v1/SOFTWARE_VERSIONS_V1.csv", ROOT / "outputs/alternative_model_benchmark_v1/SOFTWARE_VERSIONS_V1.csv"]
    candidates += [ROOT / x[3] for x in SELECTION if x[0].startswith(tuple("08" + c for c in "ABCDE"))]
    version_rows, candidate_rows, manifest_inputs = [], [], []
    for path in candidates:
        rel = path.relative_to(ROOT).as_posix()
        candidate_rows.append(dict(source_path=rel, sha256=sha(path), role="saved run environment evidence; not inferred from current pip freeze"))
        if path.suffix == ".csv":
            versions = {r["package"]: r["version"] for r in csv.DictReader(path.open(encoding="utf-8-sig"))}
        else:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
            versions = manifest.get("package_versions", manifest.get("configuration", {}).get("packages", {})).copy()
            if manifest.get("python"): versions["python"] = manifest["python"]
            inputs = manifest.get("input_files", manifest.get("configuration", {}).get("inputs", {}))
            if isinstance(inputs, dict):
                for value in inputs:
                    relinput, exists, lookup, released = availability(value)
                    manifest_inputs.append(dict(manifest=rel, input_path=relinput, exists_in_original_workspace=exists, release_lookup=lookup, present_at_audit_time=released, status="present" if released else "not_at_original_relative_path_in_release_at_audit_time"))
            elif isinstance(inputs, list):
                for item in inputs:
                    value = item.get("path", "") if isinstance(item, dict) else item
                    if value:
                        relinput, exists, lookup, released = availability(value)
                        manifest_inputs.append(dict(manifest=rel, input_path=relinput, exists_in_original_workspace=exists, release_lookup=lookup, present_at_audit_time=released, status="present" if released else "not_at_original_relative_path_in_release_at_audit_time"))
        for package, version in versions.items(): version_rows.append(dict(evidence_file=rel, package=package, saved_version=version))
    write_csv(envdir / "SAVED_VERSION_EVIDENCE.csv", candidate_rows)
    write_csv(envdir / "RECORDED_RUN_VERSIONS.csv", version_rows)
    write_csv(AUDIT / "MANIFEST_INPUTS.csv", manifest_inputs)
    distributions = {"sklearn": "scikit-learn", "PIL": "Pillow", "osgeo": "GDAL", "IPython": "ipython", "mpl_toolkits": "matplotlib", "bs4": "beautifulsoup4"}
    current = []
    for module in sorted({r["top_level_module"] for r in import_rows if not r["standard_library"]}):
        dist = distributions.get(module, module)
        try: version = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError: version = "not_found_as_distribution"
        current.append(dict(module=module, distribution=dist, observed_version=version, observed_utc=NOW, role="current archive-audit interpreter; not proof of historical fit environment"))
    current.append(dict(module="python", distribution="python", observed_version=platform.python_version(), observed_utc=NOW, role="current archive-audit interpreter; not proof of historical fit environment"))
    write_csv(envdir / "CURRENT_IMPORTED_PACKAGE_VERSIONS.csv", current)
    assert all(sha(path) == initial for path, initial in original_hashes.items()), "Original source changed during archival copy"
    summary = {"created_utc": NOW, "selected_notebooks": sum(r["archival_status"].startswith("selected") for r in rows), "excluded_notebooks": sum(not r["archival_status"].startswith("selected") for r in rows), "selected_scripts": len(SCRIPTS), "source_preservation_passed": True, "original_files_unchanged": True, "notebooks_executed": False, "secret_pattern_candidates": len(findings), "manifest_source_matches": mapping, "static_path_references": len(path_rows), "absolute_path_references": len(absolute_rows), "manifest_input_references": len(manifest_inputs), "static_parse_limitations": len(parse_rows), "portable_end_to_end_pipeline": False}
    (AUDIT / "ARCHIVE_AUDIT_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "manifest_source_matches"}, indent=2))


if __name__ == "__main__":
    main()
