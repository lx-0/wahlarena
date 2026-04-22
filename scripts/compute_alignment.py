"""
M3: Compute Wahl-O-Mat party-alignment scores for each model in a batch.

For each model in the batch manifest, runs wahlomat_runner.js (Playwright)
against the live Wahl-O-Mat site to get official party alignment percentages.
Aggregates results into alignment_matrix.json in the batch directory.

Usage:
  python3 compute_alignment.py --batch runs/batch_2026-04-20T182928Z
  python3 compute_alignment.py --batch runs/batch_2026-04-20T182928Z --models claude-sonnet-4-6
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPTS_DIR.parent

WAHLOMAT_RUNNER = SCRIPTS_DIR / 'wahlomat_runner.js'

# Playwright chromium — try standard cache paths
CHROMIUM_CANDIDATES = [
    Path.home() / '.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',
    Path.home() / '.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',
    Path('/paperclip/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome'),
]

PLAYWRIGHT_DEPS = '/paperclip/.playwright-deps'


def find_chromium() -> str:
    for p in CHROMIUM_CANDIDATES:
        if p.exists():
            return str(p)
    raise RuntimeError(
        'Playwright Chromium not found. Run: npx playwright install chromium'
    )


def run_wahlomat(answers_file: Path, out_dir: Path, chromium_path: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH'] = chromium_path
    env['LD_LIBRARY_PATH'] = f"{PLAYWRIGHT_DEPS}:{env.get('LD_LIBRARY_PATH', '')}"

    cmd = [
        'node', str(WAHLOMAT_RUNNER),
        '--answers', str(answers_file),
        '--out', str(out_dir),
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=False,
        env=env,
        cwd=str(PROJECT_DIR),
    )
    if result.returncode != 0:
        return {'success': False, 'error': f'wahlomat_runner exited {result.returncode}'}

    results_file = out_dir / 'results.json'
    if not results_file.exists():
        return {'success': False, 'error': 'results.json not written'}

    data = json.loads(results_file.read_text())
    return {'success': True, 'results': data}


def build_matrix(model_scores: dict) -> dict:
    """
    Build a ranked alignment matrix.
    model_scores: { model_name: [ {party, score_pct}, ... ] }
    Returns matrix with per-model ranked lists and cross-model party averages.
    """
    # Collect all parties
    all_parties = set()
    for scores in model_scores.values():
        for entry in scores:
            all_parties.add(entry['party'])

    # Per-model ranked list
    per_model = {}
    for model, scores in model_scores.items():
        per_model[model] = sorted(scores, key=lambda x: x['score_pct'], reverse=True)

    # Per-party average across models
    party_totals: dict[str, list[float]] = {p: [] for p in all_parties}
    for scores in model_scores.values():
        seen = {e['party'] for e in scores}
        for entry in scores:
            party_totals[entry['party']].append(entry['score_pct'])
        # Models that returned no score for a party get 0
        for p in all_parties - seen:
            party_totals[p].append(0.0)

    party_avg = [
        {
            'party': p,
            'avg_score_pct': round(sum(v) / len(v), 1),
            'model_count': len(v),
        }
        for p, v in party_totals.items()
    ]
    party_avg.sort(key=lambda x: x['avg_score_pct'], reverse=True)

    return {
        'per_model': per_model,
        'party_average': party_avg,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True, help='Path to batch directory (contains manifest.json)')
    parser.add_argument('--models', help='Comma-separated model ids to process (default: all)')
    args = parser.parse_args()

    batch_dir = Path(args.batch)
    manifest_file = batch_dir / 'manifest.json'
    if not manifest_file.exists():
        print(f"ERROR: No manifest.json in {batch_dir}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_file.read_text())
    models_in_batch = manifest.get('models', [])

    filter_models = None
    if args.models:
        filter_models = {m.strip() for m in args.models.split(',')}

    chromium_path = find_chromium()
    print(f"Chromium: {chromium_path}")
    print(f"Batch:    {batch_dir}")
    print(f"Models:   {len(models_in_batch)}")

    model_scores: dict[str, list] = {}

    for entry in models_in_batch:
        model = entry['model']
        if filter_models and model not in filter_models:
            print(f"\nSkipping {model} (not in --models filter)")
            continue

        if not entry.get('success'):
            print(f"\nSkipping {model} (M2 run was not successful)")
            continue

        answers = entry.get('answers')
        if not answers:
            print(f"\nSkipping {model} (no answers in manifest)")
            continue

        print(f"\n{'='*60}")
        print(f"Model: {model}")
        print(f"{'='*60}")

        # Write answers to temp file in model run dir
        model_dir = batch_dir / model
        model_dir.mkdir(parents=True, exist_ok=True)
        answers_file = model_dir / 'answers.json'
        answers_file.write_text(json.dumps(answers, indent=2))

        wahlomat_out = model_dir / 'wahlomat'
        result = run_wahlomat(answers_file, wahlomat_out, chromium_path)

        if result['success']:
            scores = result['results'].get('results', [])
            model_scores[model] = scores
            print(f"\nTop 5 for {model}:")
            for r in scores[:5]:
                print(f"  {r['party']}: {r['score_pct']}%")
        else:
            print(f"ERROR for {model}: {result.get('error')}", file=sys.stderr)

    if not model_scores:
        print("ERROR: No models produced scores.", file=sys.stderr)
        sys.exit(1)

    # Build alignment matrix
    matrix = build_matrix(model_scores)

    # Write output
    matrix_file = batch_dir / 'alignment_matrix.json'
    output = {
        'batch': str(batch_dir),
        'manifest_timestamp': manifest.get('timestamp'),
        'models_scored': list(model_scores.keys()),
        'matrix': matrix,
    }
    matrix_file.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nAlignment matrix written to {matrix_file}")

    # Print summary table
    print(f"\n{'='*60}")
    print("Party alignment summary (ranked by average across models)")
    print(f"{'='*60}")
    print(f"{'Party':<40} {'Avg':>6}", end='')
    for m in model_scores:
        short = m.split('-')[0][:10]
        print(f"  {short:>12}", end='')
    print()
    print('-' * (48 + 14 * len(model_scores)))

    # Build per-party per-model lookup
    lookup: dict[str, dict[str, float]] = {}
    for model, scores in model_scores.items():
        for entry in scores:
            lookup.setdefault(entry['party'], {})[model] = entry['score_pct']

    for entry in matrix['party_average']:
        party = entry['party']
        avg = entry['avg_score_pct']
        print(f"{party:<40} {avg:>5.1f}%", end='')
        for m in model_scores:
            pct = lookup.get(party, {}).get(m, 0)
            print(f"  {pct:>11.1f}%", end='')
        print()

    print(f"\nDone. {len(model_scores)} models scored.")


if __name__ == '__main__':
    main()
