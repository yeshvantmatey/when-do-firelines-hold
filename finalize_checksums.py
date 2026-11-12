"""Regenerate this code repository's manifests after metadata edits; never publish.

The root is the directory containing this script, regardless of the current
working directory. Local environments, secrets, bulk outputs and Git internals
are excluded. Packaged figure inputs and reference assets remain included.
This inventory is deterministic and is not a replacement for a privacy review.
"""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
EXCLUDE = {'release_manifest.json', 'checksums.sha256',
           'validation/release_file_manifest.json'}
LOCAL_NAMES = {'.git', '.venv', 'venv', 'env', '__pycache__',
               '.ipynb_checkpoints', '.pytest_cache', '.mypy_cache',
               '.ruff_cache', '.aws', '.ssh', '.codex', '.agents',
               '.idea', '.vscode', '.ds_store', 'thumbs.db'}
ROOT_OUTPUTS = {'data', 'dataset', 'evidence', 'models', 'outputs', 'output',
                'results', 'reproduced_results', 'verification_results',
                'redrawn_figures', 'analysis_archive', 'zenodo',
                '_preparation', 'build', 'dist', 'tmp', 'temp'}
PRIVATE_SUFFIXES = {'.pem', '.key', '.p12', '.pfx'}
BULK_SUFFIXES = {'.parquet', '.feather', '.arrow', '.pkl', '.pickle',
                 '.joblib', '.npz', '.zip', '.tif', '.tiff'}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def excluded(relative):
    """Apply the public-code scope while retaining small scientific inputs."""
    parts = tuple(part.lower() for part in relative.parts)
    name = parts[-1]
    rel = relative.as_posix()
    if rel in EXCLUDE or any(part in LOCAL_NAMES for part in parts):
        return True
    if parts[0] in ROOT_OUTPUTS or parts[:2] == ('validation', 'integrity_check'):
        return True
    if name == '.env' or (name.startswith('.env.') and name != '.env.example'):
        return True
    suffix = relative.suffix.lower()
    if suffix in PRIVATE_SUFFIXES or suffix in {'.pyc', '.pyo', '.pyd', '.log'}:
        return True
    packaged_figure_asset = parts[:2] in {
        ('figures', 'inputs'), ('figures', 'reference_outputs')}
    if not packaged_figure_asset:
        return (suffix in BULK_SUFFIXES or suffix.startswith('.grib')
                or any(part.endswith('.zarr') for part in parts))
    return False


def linked(path):
    # A Windows junction must not make the inventory escape the repository.
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def release_files():
    files = []
    for directory, subdirs, names in os.walk(ROOT, followlinks=False):
        directory = Path(directory)
        kept = []
        for name in sorted(subdirs):
            path = directory / name
            relative = path.relative_to(ROOT)
            if excluded(relative):
                continue
            if linked(path):
                raise ValueError('Linked directory is not allowed: '+relative.as_posix())
            kept.append(name)
        subdirs[:] = kept
        for name in names:
            path = directory / name
            relative = path.relative_to(ROOT)
            if excluded(relative):
                continue
            if linked(path):
                raise ValueError('Linked file is not allowed: '+relative.as_posix())
            if path.is_file():
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def run():
    entries = [{'path': path.relative_to(ROOT).as_posix(),
                'bytes': path.stat().st_size, 'sha256': sha256(path)}
               for path in release_files()]
    manifest = {
        'status': 'LOCAL_RELEASE_CANDIDATE', 'algorithm': 'SHA-256',
        'scope': 'Code repository rooted at the directory containing this script',
        'excluded_generated_files': sorted(EXCLUDE),
        'excluded_local_names': sorted(LOCAL_NAMES),
        'excluded_root_directories': sorted(ROOT_OUTPUTS),
        'additional_exclusions': 'Local credentials, bytecode, logs and bulk files outside packaged figure assets; see finalize_checksums.py.',
        'files': entries, 'file_count': len(entries),
        'bytes': sum(entry['bytes'] for entry in entries),
    }
    target = ROOT / 'release_manifest.json'
    target.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    # The JSON excludes itself and this checksum file. The checksum file adds
    # the JSON hash, but never its own hash, avoiding circular references.
    lines = [entry['sha256']+'  '+entry['path'] for entry in entries]
    lines.append(sha256(target)+'  release_manifest.json')
    (ROOT / 'checksums.sha256').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'files': len(entries), 'bytes': manifest['bytes']}))


if __name__ == '__main__':
    run()
