"""
Track A: Multi-seed runs (A1) + prompt ablations (A2).

A1: N=5 seeds per (model, thesis). Seed 1 = existing M4/M5 canonical run (copied).
    Seeds 2-5 = fresh API calls. Wahl-O-Mat scored for each seed.
A2: 3 variants per model — original (already done as seed 1), en, reordered.
    Each ablation is a single run; robustness score = variance across variants.
A3: Refusal classification is post-processing done in analyze_track_a.py.

Output: runs/track_a_<timestamp>/
  manifest.json        - all metadata, answers, and Wahl-O-Mat scores
  <model>/seed_N/      - prompts.json + answers.json + wahlomat/results.json
  <model>/ablation_en/ - same
  <model>/ablation_reordered/ - same

Usage:
  python3 run_track_a.py [--models gpt-4o,o3,...] [--seeds 5] [--skip-wahlomat] [--dry-run]
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ignore SIGINT so the process survives heartbeat session teardown when run under nohup.
# The subprocess children (node, python ask_llm) handle their own signals.
signal.signal(signal.SIGINT, signal.SIG_IGN)

SCRIPTS_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPTS_DIR.parent

WAHLOMAT_RUNNER = SCRIPTS_DIR / 'wahlomat_runner.js'
PLAYWRIGHT_DEPS = '/paperclip/.playwright-deps'
CHROMIUM_CANDIDATES = [
    Path.home() / '.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',
    Path.home() / '.cache/ms-playwright/chromium-1208/chrome-linux64/chrome',
    Path('/paperclip/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome'),
]

# Seed 1 = existing canonical M4/M5 data
SEED1_PATHS = {
    'gpt-4o':                  PROJECT_DIR / 'runs/batch_2026-04-21T160944Z/gpt-4o',
    'o3':                      PROJECT_DIR / 'runs/batch_2026-04-21T160944Z/o3',
    'claude-opus-4-7':         PROJECT_DIR / 'runs/batch_2026-04-21T225331Z/claude-opus-4-7',
    'claude-sonnet-4-6':       PROJECT_DIR / 'runs/batch_2026-04-21T225331Z/claude-sonnet-4-6',
    'claude-haiku-4-5-20251001': PROJECT_DIR / 'runs/batch_2026-04-21T225331Z/claude-haiku-4-5-20251001',
}

PROVIDERS = {
    'gpt-4o': 'openai',   # legacy — kept for SEED1_PATHS reference
    'gpt-4.1': 'openai',
    'o3': 'openai',
    'claude-opus-4-7': 'anthropic',
    'claude-sonnet-4-6': 'anthropic',
    'claude-haiku-4-5-20251001': 'anthropic',
}

# Wahlomat scores for seed_1 are already captured in existing wahlomat/ dirs.
# If the wahlomat/ subdir is absent from the original batch, we re-run it.


def find_chromium() -> str:
    for p in CHROMIUM_CANDIDATES:
        if p.exists():
            return str(p)
    raise RuntimeError('Playwright Chromium not found. Run: npx playwright install chromium')


def run_wahlomat(answers: list, out_dir: Path, chromium_path: str, retries: int = 2) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    answers_tmp = out_dir / '_answers_tmp.json'
    answers_tmp.write_text(json.dumps(answers))
    env = os.environ.copy()
    env['PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH'] = chromium_path
    env['LD_LIBRARY_PATH'] = f"{PLAYWRIGHT_DEPS}:{env.get('LD_LIBRARY_PATH', '')}"

    for attempt in range(1, retries + 2):
        result = subprocess.run(
            ['node', str(WAHLOMAT_RUNNER), '--answers', str(answers_tmp), '--out', str(out_dir)],
            env=env, cwd=str(PROJECT_DIR),
        )
        results_file = out_dir / 'results.json'
        if result.returncode == 0 and results_file.exists():
            answers_tmp.unlink(missing_ok=True)
            return {'success': True, 'results': json.loads(results_file.read_text())}
        print(f"  Wahlomat attempt {attempt} failed (exit {result.returncode}), "
              f"{'retrying...' if attempt <= retries else 'giving up.'}")
        time.sleep(3)

    answers_tmp.unlink(missing_ok=True)
    return {'success': False, 'error': f'wahlomat_runner failed after {retries + 1} attempts'}


def run_ask_llm(model: str, provider: str, out_dir: Path, variant: str = 'original',
                theses_file: Path = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(SCRIPTS_DIR / 'ask_llm.py'),
        '--model', model,
        '--provider', provider,
        '--out', str(out_dir),
        '--variant', variant,
    ]
    if theses_file:
        cmd += ['--theses-file', str(theses_file)]

    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    elapsed = round(time.time() - t0, 1)
    success = result.returncode == 0

    answers = None
    if success:
        af = out_dir / 'answers.json'
        if af.exists():
            answers = json.loads(af.read_text())

    return {'success': success, 'elapsed_s': elapsed, 'answers': answers, 'dir': str(out_dir)}


def translate_theses_to_english(theses: list) -> list:
    """Translate all theses to English in one Anthropic call. Caches to data/theses_en.json."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ['WAHL_ANTHROPIC_API_KEY'])

    prompt = (
        "Translate these German political theses to English. "
        "Return a JSON array with the EXACT same structure, translating only the 'topic' and 'statement' fields. "
        "Keep 'index' unchanged. No preamble, just the JSON array.\n\n"
        + json.dumps(theses, ensure_ascii=False)
    )
    print("Translating theses to English via Claude haiku...")
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}]
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    return json.loads(raw)


def get_or_create_theses_en() -> Path:
    theses_en_path = PROJECT_DIR / 'data' / 'theses_en.json'
    if theses_en_path.exists():
        print(f"Using cached English theses: {theses_en_path}")
        return theses_en_path

    theses_de = json.loads((PROJECT_DIR / 'data' / 'theses.json').read_text())
    theses_en = translate_theses_to_english(theses_de)
    theses_en_path.write_text(json.dumps(theses_en, indent=2, ensure_ascii=False))
    print(f"English theses written to {theses_en_path}")
    return theses_en_path


def load_seed1_scores(model: str, seed1_dir: Path) -> list | None:
    """Load existing Wahl-O-Mat scores from the canonical batch if present."""
    wahlomat_dir = seed1_dir / 'wahlomat'
    results_file = wahlomat_dir / 'results.json'
    if results_file.exists():
        data = json.loads(results_file.read_text())
        return data.get('results', [])
    return None


def scores_from_wahlomat_result(wm_result: dict) -> list | None:
    if wm_result.get('success'):
        return wm_result['results'].get('results', [])
    return None


def main():
    parser = argparse.ArgumentParser(description='Track A: multi-seed + ablation runner')
    parser.add_argument('--models', help='Comma-separated model ids (default: all 5)')
    parser.add_argument('--seeds', type=int, default=5, help='Total seeds including seed 1 (default: 5)')
    parser.add_argument('--skip-wahlomat', action='store_true', help='Skip Wahl-O-Mat browser step')
    parser.add_argument('--dry-run', action='store_true', help='Print plan, do not call APIs')
    parser.add_argument('--resume', help='Resume into existing batch dir (skips completed seeds/ablations)')
    args = parser.parse_args()

    all_models = list(SEED1_PATHS.keys())
    models = [m.strip() for m in args.models.split(',')] if args.models else all_models

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
    resume_dir = getattr(args, 'resume', None)
    if resume_dir:
        batch_dir = Path(resume_dir)
        # Extract timestamp from existing dir name
        timestamp = batch_dir.name.replace('track_a_', '')
    else:
        batch_dir = PROJECT_DIR / 'runs' / f'track_a_{timestamp}'
    batch_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Track A Runner — {timestamp}")
    print(f"Models:       {', '.join(models)}")
    print(f"Seeds:        {args.seeds} (seed 1 = canonical M4/M5)")
    print(f"Ablations:    en, reordered")
    print(f"Output:       {batch_dir}")
    print(f"Resume:       {args.resume or 'no'}")
    print(f"Skip browser: {args.skip_wahlomat}")
    print(f"Dry run:      {args.dry_run}")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("Dry run — exiting before any API calls.")
        return

    chromium_path = None
    if not args.skip_wahlomat:
        chromium_path = find_chromium()
        print(f"Chromium: {chromium_path}\n")

    theses_en_path = get_or_create_theses_en()

    manifest = {
        'timestamp': timestamp,
        'track': 'A',
        'n_seeds': args.seeds,
        'variants': ['original', 'en', 'reordered'],
        'models': {}
    }

    for model in models:
        provider = PROVIDERS.get(model, 'anthropic')
        model_dir = batch_dir / model
        model_dir.mkdir(exist_ok=True)
        model_manifest = {'seeds': {}, 'ablations': {}}

        print(f"\n{'='*60}")
        print(f"MODEL: {model}  (provider: {provider})")
        print(f"{'='*60}")

        # ── Seed 1: copy from canonical batch ───────────────────────────────
        seed1_src = SEED1_PATHS.get(model)
        seed1_out = model_dir / 'seed_1'
        if seed1_src and seed1_src.exists():
            if not seed1_out.exists():
                shutil.copytree(str(seed1_src), str(seed1_out))
            answers_1 = json.loads((seed1_out / 'answers.json').read_text())

            # Run Wahl-O-Mat for seed 1 if not already scored
            wm_scores_1 = load_seed1_scores(model, seed1_out)
            if wm_scores_1 is None and not args.skip_wahlomat:
                print(f"  Running Wahl-O-Mat for seed_1...")
                wm_res = run_wahlomat(answers_1, seed1_out / 'wahlomat', chromium_path)
                wm_scores_1 = scores_from_wahlomat_result(wm_res)

            model_manifest['seeds']['1'] = {
                'dir': str(seed1_out),
                'source': 'canonical_m4m5',
                'answers': answers_1,
                'wahlomat_scores': wm_scores_1,
            }
            print(f"  seed_1: OK (canonical, {sum(1 for a in answers_1 if a == 1)} agree, "
                  f"{sum(1 for a in answers_1 if a == 0)} neutral, "
                  f"{sum(1 for a in answers_1 if a == -1)} disagree)")
        else:
            print(f"  WARNING: No seed_1 source for {model}")

        # ── Seeds 2..N: fresh API calls ──────────────────────────────────────
        for seed_n in range(2, args.seeds + 1):
            seed_dir = model_dir / f'seed_{seed_n}'
            # Resume: skip LLM if answers already exist
            if (seed_dir / 'answers.json').exists():
                answers = json.loads((seed_dir / 'answers.json').read_text())
                run_result = {'success': True, 'elapsed_s': 0, 'answers': answers, 'dir': str(seed_dir)}
                print(f"\n  seed_{seed_n}: RESUMED (answers already exist)")
            else:
                print(f"\n  Running seed_{seed_n}...")
                run_result = run_ask_llm(model, provider, seed_dir, variant='original')

            wm_scores = None
            wm_done = (seed_dir / 'wahlomat' / 'results.json').exists()
            if wm_done:
                wm_scores = json.loads((seed_dir / 'wahlomat' / 'results.json').read_text()).get('results', [])
                print(f"  Wahl-O-Mat seed_{seed_n}: RESUMED")
            elif run_result['success'] and not args.skip_wahlomat:
                print(f"  Running Wahl-O-Mat for seed_{seed_n}...")
                wm_res = run_wahlomat(run_result['answers'], seed_dir / 'wahlomat', chromium_path)
                wm_scores = scores_from_wahlomat_result(wm_res)

            model_manifest['seeds'][str(seed_n)] = {
                'dir': str(seed_dir),
                'source': 'api',
                'success': run_result['success'],
                'elapsed_s': run_result['elapsed_s'],
                'answers': run_result['answers'],
                'wahlomat_scores': wm_scores,
            }
            status = 'OK' if run_result['success'] else 'FAIL'
            print(f"  seed_{seed_n}: {status} ({run_result['elapsed_s']}s)")

        # ── Ablation: English ────────────────────────────────────────────────
        en_dir = model_dir / 'ablation_en'
        if (en_dir / 'answers.json').exists():
            run_en = {'success': True, 'elapsed_s': 0,
                      'answers': json.loads((en_dir / 'answers.json').read_text()), 'dir': str(en_dir)}
            print(f"\n  ablation_en: RESUMED")
        else:
            print(f"\n  Running ablation_en...")
            run_en = run_ask_llm(model, provider, en_dir, variant='en', theses_file=theses_en_path)
        wm_scores_en = None
        if (en_dir / 'wahlomat' / 'results.json').exists():
            wm_scores_en = json.loads((en_dir / 'wahlomat' / 'results.json').read_text()).get('results', [])
        elif run_en['success'] and not args.skip_wahlomat:
            print(f"  Running Wahl-O-Mat for ablation_en...")
            wm_res = run_wahlomat(run_en['answers'], en_dir / 'wahlomat', chromium_path)
            wm_scores_en = scores_from_wahlomat_result(wm_res)
        model_manifest['ablations']['en'] = {
            'dir': str(en_dir),
            'success': run_en['success'],
            'elapsed_s': run_en['elapsed_s'],
            'answers': run_en['answers'],
            'wahlomat_scores': wm_scores_en,
        }
        print(f"  ablation_en: {'OK' if run_en['success'] else 'FAIL'} ({run_en['elapsed_s']}s)")

        # ── Ablation: Reordered ──────────────────────────────────────────────
        reo_dir = model_dir / 'ablation_reordered'
        if (reo_dir / 'answers.json').exists():
            run_reo = {'success': True, 'elapsed_s': 0,
                       'answers': json.loads((reo_dir / 'answers.json').read_text()), 'dir': str(reo_dir)}
            print(f"\n  ablation_reordered: RESUMED")
        else:
            print(f"\n  Running ablation_reordered...")
            run_reo = run_ask_llm(model, provider, reo_dir, variant='reordered')
        wm_scores_reo = None
        if (reo_dir / 'wahlomat' / 'results.json').exists():
            wm_scores_reo = json.loads((reo_dir / 'wahlomat' / 'results.json').read_text()).get('results', [])
        elif run_reo['success'] and not args.skip_wahlomat:
            print(f"  Running Wahl-O-Mat for ablation_reordered...")
            wm_res = run_wahlomat(run_reo['answers'], reo_dir / 'wahlomat', chromium_path)
            wm_scores_reo = scores_from_wahlomat_result(wm_res)
        model_manifest['ablations']['reordered'] = {
            'dir': str(reo_dir),
            'success': run_reo['success'],
            'elapsed_s': run_reo['elapsed_s'],
            'answers': run_reo['answers'],
            'wahlomat_scores': wm_scores_reo,
        }
        print(f"  ablation_reordered: {'OK' if run_reo['success'] else 'FAIL'} ({run_reo['elapsed_s']}s)")

        manifest['models'][model] = model_manifest

    manifest_file = batch_dir / 'manifest.json'
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\n{'='*60}")
    print(f"Track A complete. Manifest: {manifest_file}")
    print(f"{'='*60}")
    print(f"\nNext step: python3 scripts/analyze_track_a.py --batch {batch_dir}")


if __name__ == '__main__':
    main()
