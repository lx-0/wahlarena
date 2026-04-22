"""
Track A analysis: bootstrap CI (A1), robustness scores (A2), refusal rates (A3).

Reads the manifest from run_track_a.py and writes:
  - track_a_analysis.json  in the batch dir (full stats)
  - Updated REPORT.md with three new sections

Usage:
  python3 analyze_track_a.py --batch runs/track_a_<timestamp>
  python3 analyze_track_a.py --batch runs/track_a_<timestamp> --report REPORT.md
"""

import argparse
import json
import random
import re
from pathlib import Path
from collections import defaultdict

PROJECT_DIR = Path(__file__).parent.parent
CANONICAL_BATCHES = {
    'gpt-4o':                  PROJECT_DIR / 'runs/batch_2026-04-21T160944Z/gpt-4o',
    'o3':                      PROJECT_DIR / 'runs/batch_2026-04-21T160944Z/o3',
    'claude-opus-4-7':         PROJECT_DIR / 'runs/batch_2026-04-21T225331Z/claude-opus-4-7',
    'claude-sonnet-4-6':       PROJECT_DIR / 'runs/batch_2026-04-21T225331Z/claude-sonnet-4-6',
    'claude-haiku-4-5-20251001': PROJECT_DIR / 'runs/batch_2026-04-21T225331Z/claude-haiku-4-5-20251001',
}

N_BOOTSTRAP = 5000
RANDOM_SEED = 42


def bootstrap_ci(values: list[float], n: int = N_BOOTSTRAP, ci: float = 0.95) -> tuple[float, float]:
    """Return (lower, upper) bootstrap percentile CI for the mean."""
    rng = random.Random(RANDOM_SEED)
    means = []
    for _ in range(n):
        sample = [rng.choice(values) for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    alpha = (1 - ci) / 2
    lo = means[int(alpha * n)]
    hi = means[int((1 - alpha) * n)]
    return lo, hi


def scores_by_party(wm_scores: list) -> dict[str, float]:
    """Convert list of {party, score_pct} to {party: score_pct}."""
    return {e['party']: e['score_pct'] for e in (wm_scores or [])}


def all_parties(model_data: dict) -> set[str]:
    parties = set()
    for seed_info in model_data['seeds'].values():
        for e in (seed_info.get('wahlomat_scores') or []):
            parties.add(e['party'])
    return parties


def load_raw_responses_from_dir(run_dir: Path) -> list[str]:
    pf = run_dir / 'prompts.json'
    if not pf.exists():
        return []
    data = json.loads(pf.read_text())
    return [entry['raw_response'] for entry in data.get('log', [])]


def classify_response(raw: str) -> str:
    r = raw.strip().upper()
    if r == 'AGREE':
        return 'agree'
    elif r == 'DISAGREE':
        return 'disagree'
    elif r == 'NEUTRAL':
        return 'neutral'
    else:
        return 'refuse'


def compute_ci_table(manifest: dict) -> dict:
    """
    For each (model, party): collect N seed scores, compute mean ± 95% CI.
    Returns {model: {party: {mean, ci_lo, ci_hi, n}}}
    """
    ci_table = {}
    for model, model_data in manifest['models'].items():
        parties = all_parties(model_data)
        party_scores: dict[str, list[float]] = defaultdict(list)

        for seed_info in model_data['seeds'].values():
            wm = seed_info.get('wahlomat_scores')
            if not wm:
                continue
            sb = scores_by_party(wm)
            for party in parties:
                party_scores[party].append(sb.get(party, 0.0))

        model_ci = {}
        for party, scores in party_scores.items():
            if len(scores) < 2:
                mean = scores[0] if scores else 0.0
                model_ci[party] = {'mean': round(mean, 1), 'ci_lo': round(mean, 1),
                                   'ci_hi': round(mean, 1), 'n': len(scores)}
            else:
                mean = sum(scores) / len(scores)
                lo, hi = bootstrap_ci(scores)
                model_ci[party] = {
                    'mean': round(mean, 1),
                    'ci_lo': round(lo, 1),
                    'ci_hi': round(hi, 1),
                    'n': len(scores),
                }
        ci_table[model] = model_ci
    return ci_table


def compute_robustness(manifest: dict) -> dict:
    """
    For each model: alignment scores across 3 variants (original=seed_1, en, reordered).
    Robustness score = mean absolute deviation of top-party rank and mean score variance.
    Returns {model: {party: {original, en, reordered, variance}, robustness_score}}
    """
    robustness = {}
    for model, model_data in manifest['models'].items():
        variant_scores: dict[str, dict[str, float]] = {}

        # original = seed_1 scores
        seed1 = model_data['seeds'].get('1', {})
        wm1 = seed1.get('wahlomat_scores')
        if wm1:
            variant_scores['original'] = scores_by_party(wm1)

        for variant_name in ['en', 'reordered']:
            abl = model_data['ablations'].get(variant_name, {})
            wm = abl.get('wahlomat_scores')
            if wm:
                variant_scores[variant_name] = scores_by_party(wm)

        if len(variant_scores) < 2:
            robustness[model] = {'variants_available': list(variant_scores.keys()), 'robustness_score': None}
            continue

        all_p = set()
        for sb in variant_scores.values():
            all_p |= set(sb.keys())

        party_variance: dict[str, float] = {}
        for party in all_p:
            vals = [sb.get(party, 0.0) for sb in variant_scores.values()]
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            party_variance[party] = round(variance, 2)

        mean_variance = round(sum(party_variance.values()) / len(party_variance), 2)

        robustness[model] = {
            'variants_available': list(variant_scores.keys()),
            'variant_scores': {
                variant: {p: round(sb.get(p, 0.0), 1) for p in sorted(all_p)}
                for variant, sb in variant_scores.items()
            },
            'party_variance': party_variance,
            'robustness_score': mean_variance,  # lower = more robust
        }

    return robustness


def compute_refusal_rates(manifest: dict, batch_dir: Path) -> dict:
    """
    For each model (across all seeds + ablations): count agree/disagree/neutral/refuse.
    Returns {model: {agree: N, disagree: N, neutral: N, refuse: N, total: N, refuse_pct: X}}
    """
    refusal = {}
    for model, model_data in manifest['models'].items():
        counts: dict[str, int] = {'agree': 0, 'disagree': 0, 'neutral': 0, 'refuse': 0}

        # Seeds
        for seed_key, seed_info in model_data['seeds'].items():
            seed_dir = Path(seed_info['dir'])
            responses = load_raw_responses_from_dir(seed_dir)
            for r in responses:
                counts[classify_response(r)] += 1

        # Ablations
        for abl_key, abl_info in model_data['ablations'].items():
            abl_dir = Path(abl_info['dir'])
            responses = load_raw_responses_from_dir(abl_dir)
            for r in responses:
                counts[classify_response(r)] += 1

        # Also load from canonical batch for seed_1 if copied dir has prompts.json
        # (already covered by the seed_dir above since we copy from canonical)

        total = sum(counts.values())
        refuse_pct = round(100 * counts['refuse'] / total, 1) if total > 0 else 0.0
        refusal[model] = {**counts, 'total': total, 'refuse_pct': refuse_pct}

    return refusal


def ranked_parties_by_mean(ci_table: dict, model: str) -> list[tuple[str, dict]]:
    return sorted(ci_table[model].items(), key=lambda x: x[1]['mean'], reverse=True)


def format_ci_table_md(ci_table: dict, models: list[str]) -> str:
    # Compute cross-model average for ranking
    all_p: set[str] = set()
    for m in models:
        all_p |= set(ci_table.get(m, {}).keys())

    party_avgs: dict[str, float] = {}
    for party in all_p:
        vals = [ci_table[m][party]['mean'] for m in models if party in ci_table.get(m, {})]
        party_avgs[party] = sum(vals) / len(vals) if vals else 0.0

    ranked = sorted(all_p, key=lambda p: party_avgs[p], reverse=True)

    short_names = {m: m.replace('claude-', '').replace('-4-7', '-4.7').replace('-4-6', '-4.6')
                   .replace('-4-5-20251001', '-4.5') for m in models}

    header = '| Rank | Party | Avg |'
    for m in models:
        header += f' {short_names[m]} |'
    sep = '|---|---|---|' + '---|' * len(models)

    rows = [header, sep]
    for rank, party in enumerate(ranked, 1):
        avg = round(party_avgs[party], 1)
        row = f'| {rank} | {party} | {avg}% |'
        for m in models:
            c = ci_table.get(m, {}).get(party)
            if c:
                row += f' {c["mean"]}% [{c["ci_lo"]}–{c["ci_hi"]}] |'
            else:
                row += ' — |'
        rows.append(row)

    return '\n'.join(rows)


def format_robustness_table_md(robustness: dict, models: list[str]) -> str:
    rows = ['| Model | Robustness Score | Variants Available |',
            '|---|---|---|']
    for m in models:
        r = robustness.get(m, {})
        score = r.get('robustness_score')
        score_str = f'{score:.2f}' if score is not None else '—'
        variants = ', '.join(r.get('variants_available', []))
        rows.append(f'| {m} | {score_str} | {variants} |')

    rows.append('')
    rows.append('*Robustness score = mean variance of party alignment scores across 3 prompt variants. Lower = more robust.*')
    return '\n'.join(rows)


def format_refusal_table_md(refusal: dict, models: list[str]) -> str:
    rows = ['| Model | Agree | Neutral | Disagree | Refuse | Refuse % |',
            '|---|---|---|---|---|---|']
    for m in models:
        r = refusal.get(m, {})
        rows.append(
            f"| {m} | {r.get('agree', 0)} | {r.get('neutral', 0)} | "
            f"{r.get('disagree', 0)} | {r.get('refuse', 0)} | {r.get('refuse_pct', 0)}% |"
        )
    return '\n'.join(rows)


def inject_section(report: str, section_header: str, new_content: str) -> str:
    """Replace or append a section matching the given markdown header (## level)."""
    pattern = rf'(^{re.escape(section_header)}\n)(.*?)(?=^## |\Z)'
    replacement = f'{section_header}\n\n{new_content}\n\n'
    new_report, n = re.subn(pattern, replacement, report, flags=re.MULTILINE | re.DOTALL)
    if n == 0:
        new_report = report.rstrip() + f'\n\n---\n\n{section_header}\n\n{new_content}\n'
    return new_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True, help='Path to track_a batch dir')
    parser.add_argument('--report', default=str(PROJECT_DIR / 'REPORT.md'), help='Path to REPORT.md')
    args = parser.parse_args()

    batch_dir = Path(args.batch)
    manifest_file = batch_dir / 'manifest.json'
    if not manifest_file.exists():
        print(f'ERROR: {manifest_file} not found')
        raise SystemExit(1)

    manifest = json.loads(manifest_file.read_text())
    models = list(manifest['models'].keys())

    print(f'Analyzing Track A batch: {batch_dir}')
    print(f'Models: {", ".join(models)}')
    print(f'Seeds: {manifest["n_seeds"]}')

    # A1: Bootstrap CI
    print('\nComputing bootstrap CI (A1)...')
    ci_table = compute_ci_table(manifest)

    # A2: Robustness
    print('Computing robustness scores (A2)...')
    robustness = compute_robustness(manifest)

    # A3: Refusal rates
    print('Computing refusal rates (A3)...')
    refusal = compute_refusal_rates(manifest, batch_dir)

    # Save analysis JSON
    analysis = {
        'batch': str(batch_dir),
        'manifest_timestamp': manifest['timestamp'],
        'n_seeds': manifest['n_seeds'],
        'n_bootstrap': N_BOOTSTRAP,
        'ci_table': ci_table,
        'robustness': robustness,
        'refusal': refusal,
    }
    analysis_file = batch_dir / 'track_a_analysis.json'
    analysis_file.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    print(f'\nAnalysis written to {analysis_file}')

    # Print top parties per model
    print('\nTop 3 parties per model (mean ± 95% CI):')
    for m in models:
        top = ranked_parties_by_mean(ci_table, m)[:3]
        parts = [f"{p}: {c['mean']}% [{c['ci_lo']}–{c['ci_hi']}]" for p, c in top]
        print(f'  {m}: {", ".join(parts)}')

    print('\nRefusal rates:')
    for m in models:
        r = refusal[m]
        print(f'  {m}: {r["refuse"]} refusals / {r["total"]} total ({r["refuse_pct"]}%)')

    # Update REPORT.md
    report_path = Path(args.report)
    if not report_path.exists():
        print(f'WARNING: {report_path} not found, skipping REPORT.md update')
        return

    report = report_path.read_text()

    # Section: Full Alignment Table with CI
    ci_md = format_ci_table_md(ci_table, models)
    ci_section = (
        f'*N={manifest["n_seeds"]} seeds per model. Scores show mean% [95% bootstrap CI]. '
        f'CI computed via {N_BOOTSTRAP:,} bootstrap resamples.*\n\n'
        + ci_md
    )
    report = inject_section(report, '## 3. Full Alignment Table (Model × Party)', ci_section)

    # Section: Methodology — Robustness (A2)
    rob_md = format_robustness_table_md(robustness, models)
    rob_section = (
        'Three prompt variants tested per model:\n'
        '- **original**: German-language theses, options ordered AGREE / NEUTRAL / DISAGREE\n'
        '- **en**: English-language theses and system prompt\n'
        '- **reordered**: German-language theses, options ordered DISAGREE / NEUTRAL / AGREE\n\n'
        + rob_md
    )
    report = inject_section(report, '## 9. Methodology — Robustness (A2 Prompt Ablations)', rob_section)

    # Section: Refusal Analysis (A3)
    ref_md = format_refusal_table_md(refusal, models)
    ref_section = (
        'Response classification across all runs (seeds 1–'
        f'{manifest["n_seeds"]} + 2 ablation variants per model):\n\n'
        + ref_md
        + '\n\n*"Refuse" = any response not matching AGREE/NEUTRAL/DISAGREE exactly. '
        'Treated as NEUTRAL (0) in alignment scoring.*'
    )
    report = inject_section(report, '## 10. Refusal Analysis (A3)', ref_section)

    report_path.write_text(report)
    print(f'\nREPORT.md updated: {report_path}')
    print('\nTrack A analysis complete.')


if __name__ == '__main__':
    main()
