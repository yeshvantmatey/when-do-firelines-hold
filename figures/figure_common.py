"""Output safety for standalone saved-data figure scripts."""
import argparse
from pathlib import Path

FIGURE_ROOT = Path(__file__).resolve().parent
CODE_ROOT = FIGURE_ROOT.parent

def prepare_output(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--output', type=Path, required=True,
                        help='New output directory outside released code, dataset, and analysis archive.')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    protected = [CODE_ROOT, CODE_ROOT.parent/'dataset', CODE_ROOT.parent/'analysis_archive']
    if any(output == p or p in output.parents for p in protected):
        parser.error('Choose an output directory outside the three released input folders.')
    if output.exists():
        parser.error('Output directory already exists; choose a new directory.')
    output.mkdir(parents=True)
    return output
