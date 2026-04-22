"""
Multi-model prompt runner for the Wahl-O-Mat LLM evaluation.

Runs ask_llm.py for each configured model sequentially.  A failed model is
logged and skipped; others continue.  Results land in runs/<model>_<timestamp>/.

Usage:
  python3 run_all_models.py [--fixture] [--models claude-sonnet-4-6,gpt-4o]

--fixture   Replace all real providers with the deterministic fixture provider.
            Useful for end-to-end pipeline validation without live API keys.
--models    Comma-separated override list. Default: all models in MODELS below.
--skip-browser  Skip the Wahl-O-Mat browser step (ask_llm only).
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPTS_DIR.parent

# Canonical model list — updated 2026-04-22 (WAH-25)
MODELS = [
    # Anthropic (current: Opus 4.7, Sonnet 4.6, Haiku 4.5)
    {'model': 'claude-opus-4-7',    'provider': 'anthropic'},
    {'model': 'claude-sonnet-4-6',  'provider': 'anthropic'},
    {'model': 'claude-haiku-4-5-20251001', 'provider': 'anthropic'},
    # OpenAI — gpt-4.1 replaces gpt-4o (flagship upgrade Apr 2025)
    {'model': 'gpt-4.1',            'provider': 'openai'},
    {'model': 'o3',                 'provider': 'openai'},
    # Google — Gemini 3 generation (preview; 2.5 is stable fallback)
    {'model': 'gemini-3-flash-preview',   'provider': 'google'},
    {'model': 'gemini-3.1-pro-preview',   'provider': 'google'},
    # xAI — Grok 4 (Jul 2025 stable release)
    {'model': 'grok-4-0709',        'provider': 'xai'},
    # OpenRouter open-weight — upgraded to 2025/2026 flagships
    {'model': 'meta-llama/llama-4-maverick',  'provider': 'openrouter'},
    {'model': 'mistralai/mistral-large-2512', 'provider': 'openrouter'},
    {'model': 'deepseek/deepseek-v3.2',       'provider': 'openrouter'},
    {'model': 'qwen/qwen3-235b-a22b',         'provider': 'openrouter'},
]


def run_model(model: str, provider: str, run_dir: Path, fixture: bool) -> dict:
    actual_provider = 'fixture' if fixture else provider
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / 'ask_llm.py'),
        '--model', model,
        '--provider', actual_provider,
        '--out', str(run_dir),
    ]
    print(f"\n{'='*60}")
    print(f"Model:    {model}  (provider: {actual_provider})")
    print(f"Out dir:  {run_dir}")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=False)
    elapsed = time.time() - t0
    success = result.returncode == 0
    answers = None
    if success:
        answers_file = run_dir / 'answers.json'
        if answers_file.exists():
            answers = json.loads(answers_file.read_text())
    return {
        'model': model,
        'provider': actual_provider,
        'run_dir': str(run_dir),
        'success': success,
        'elapsed_s': round(elapsed, 1),
        'answers': answers,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', action='store_true',
                        help='Use fixture provider for all models (no real API keys needed)')
    parser.add_argument('--models', help='Comma-separated model ids to run (overrides default list)')
    parser.add_argument('--skip-browser', action='store_true',
                        help='Skip Wahl-O-Mat browser automation step')
    args = parser.parse_args()

    if args.models:
        model_ids = [m.strip() for m in args.models.split(',')]
        models = [m for m in MODELS if m['model'] in model_ids]
        # Include any not in the default list as anthropic by default
        known = {m['model'] for m in MODELS}
        for mid in model_ids:
            if mid not in known:
                models.append({'model': mid, 'provider': 'anthropic'})
    else:
        models = MODELS

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
    batch_dir = PROJECT_DIR / 'runs' / f'batch_{timestamp}'
    batch_dir.mkdir(parents=True, exist_ok=True)

    print(f"Wahl-O-Mat Multi-Model Runner")
    print(f"Batch:   {batch_dir}")
    print(f"Models:  {len(models)}")
    print(f"Fixture: {args.fixture}")

    results = []
    for entry in models:
        run_dir = batch_dir / entry['model']
        try:
            r = run_model(entry['model'], entry['provider'], run_dir, args.fixture)
        except Exception as e:
            r = {
                'model': entry['model'],
                'provider': entry['provider'],
                'run_dir': str(run_dir),
                'success': False,
                'error': str(e),
                'elapsed_s': 0,
                'answers': None,
            }
        results.append(r)

    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    passed = 0
    for r in results:
        status = 'OK' if r['success'] else 'FAIL'
        dist = ''
        if r.get('answers'):
            a = r['answers']
            dist = f"  agree={a.count(1)} neutral={a.count(0)} disagree={a.count(-1)}"
        print(f"  [{status}] {r['model']} ({r['elapsed_s']}s){dist}")
        if r['success']:
            passed += 1

    print(f"\n{passed}/{len(results)} models succeeded.")

    manifest = {
        'timestamp': timestamp,
        'fixture': args.fixture,
        'models': results,
    }
    manifest_file = batch_dir / 'manifest.json'
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Manifest: {manifest_file}")

    sys.exit(0 if passed == len(results) else 1)


if __name__ == '__main__':
    main()
