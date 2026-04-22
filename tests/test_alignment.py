"""
Unit tests for compute_alignment.build_matrix and analyze_track_a statistics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import pytest
from compute_alignment import build_matrix
from analyze_track_a import (
    bootstrap_ci,
    classify_response,
    scores_by_party,
    compute_robustness,
    compute_ci_table,
)


# ── build_matrix ──────────────────────────────────────────────────────────────

SCORES_A = [
    {'party': 'CDU/CSU', 'score_pct': 70.0},
    {'party': 'SPD',     'score_pct': 55.0},
    {'party': 'Grüne',   'score_pct': 40.0},
]
SCORES_B = [
    {'party': 'CDU/CSU', 'score_pct': 60.0},
    {'party': 'SPD',     'score_pct': 65.0},
    {'party': 'Grüne',   'score_pct': 50.0},
]


def test_build_matrix_per_model_ranking():
    matrix = build_matrix({'model-a': SCORES_A, 'model-b': SCORES_B})
    # model-a: CDU/CSU 70, SPD 55, Grüne 40 → CDU first
    assert matrix['per_model']['model-a'][0]['party'] == 'CDU/CSU'
    assert matrix['per_model']['model-a'][0]['score_pct'] == 70.0
    # model-b: SPD 65, CDU/CSU 60, Grüne 50 → SPD first
    assert matrix['per_model']['model-b'][0]['party'] == 'SPD'


def test_build_matrix_party_average():
    matrix = build_matrix({'model-a': SCORES_A, 'model-b': SCORES_B})
    avg_by_party = {e['party']: e['avg_score_pct'] for e in matrix['party_average']}
    # CDU/CSU: (70 + 60) / 2 = 65.0
    assert avg_by_party['CDU/CSU'] == 65.0
    # SPD: (55 + 65) / 2 = 60.0
    assert avg_by_party['SPD'] == 60.0
    # Grüne: (40 + 50) / 2 = 45.0
    assert avg_by_party['Grüne'] == 45.0


def test_build_matrix_party_average_sorted_desc():
    matrix = build_matrix({'model-a': SCORES_A, 'model-b': SCORES_B})
    avgs = [e['avg_score_pct'] for e in matrix['party_average']]
    assert avgs == sorted(avgs, reverse=True)


def test_build_matrix_single_model():
    matrix = build_matrix({'only-model': SCORES_A})
    assert len(matrix['per_model']['only-model']) == 3
    assert matrix['party_average'][0]['model_count'] == 1


def test_build_matrix_missing_party_fills_zero():
    # model-b is missing Grüne
    scores_b_partial = [
        {'party': 'CDU/CSU', 'score_pct': 60.0},
        {'party': 'SPD',     'score_pct': 65.0},
    ]
    matrix = build_matrix({'model-a': SCORES_A, 'model-b': scores_b_partial})
    avg_by_party = {e['party']: e['avg_score_pct'] for e in matrix['party_average']}
    # Grüne: (40 + 0) / 2 = 20.0
    assert avg_by_party['Grüne'] == 20.0


def test_build_matrix_model_count():
    matrix = build_matrix({'model-a': SCORES_A, 'model-b': SCORES_B})
    for entry in matrix['party_average']:
        assert entry['model_count'] == 2


# ── classify_response ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('raw,expected', [
    ('AGREE',    'agree'),
    ('agree',    'agree'),
    ('DISAGREE', 'disagree'),
    ('NEUTRAL',  'neutral'),
    ('  agree ', 'agree'),
    ('MAYBE',    'refuse'),
    ('',         'refuse'),
    ('I AGREE',  'refuse'),
    ('BLOCKED',  'refuse'),
])
def test_classify_response(raw, expected):
    assert classify_response(raw) == expected


# ── scores_by_party ───────────────────────────────────────────────────────────

def test_scores_by_party():
    wm = [
        {'party': 'CDU/CSU', 'score_pct': 70.0},
        {'party': 'SPD',     'score_pct': 55.0},
    ]
    result = scores_by_party(wm)
    assert result == {'CDU/CSU': 70.0, 'SPD': 55.0}


def test_scores_by_party_empty():
    assert scores_by_party([]) == {}
    assert scores_by_party(None) == {}


# ── bootstrap_ci ──────────────────────────────────────────────────────────────

def test_bootstrap_ci_deterministic():
    values = [60.0, 62.0, 58.0, 61.0, 59.0]
    lo1, hi1 = bootstrap_ci(values, n=1000)
    lo2, hi2 = bootstrap_ci(values, n=1000)
    assert lo1 == lo2
    assert hi1 == hi2


def test_bootstrap_ci_bounds():
    values = [50.0, 60.0, 70.0, 80.0, 90.0]
    lo, hi = bootstrap_ci(values, n=2000)
    true_mean = sum(values) / len(values)
    assert lo <= true_mean <= hi


def test_bootstrap_ci_constant():
    # If all values are identical, CI should be a point estimate
    values = [75.0] * 10
    lo, hi = bootstrap_ci(values, n=500)
    assert lo == 75.0
    assert hi == 75.0


# ── compute_robustness ────────────────────────────────────────────────────────

def _make_manifest(model: str, seeds: dict, ablations: dict) -> dict:
    return {'models': {model: {'seeds': seeds, 'ablations': ablations}}}


def test_compute_robustness_identical_variants_scores_zero():
    wm = [{'party': 'CDU/CSU', 'score_pct': 70.0}]
    manifest = _make_manifest(
        'm',
        seeds={'1': {'wahlomat_scores': wm}},
        ablations={
            'en':        {'wahlomat_scores': wm},
            'reordered': {'wahlomat_scores': wm},
        }
    )
    result = compute_robustness(manifest)
    assert result['m']['robustness_score'] == 0.0


def test_compute_robustness_missing_ablations():
    wm = [{'party': 'CDU/CSU', 'score_pct': 70.0}]
    manifest = _make_manifest(
        'm',
        seeds={'1': {'wahlomat_scores': wm}},
        ablations={}
    )
    result = compute_robustness(manifest)
    # Only 1 variant available — cannot compute variance
    assert result['m']['robustness_score'] is None


# ── compute_ci_table ──────────────────────────────────────────────────────────

def test_compute_ci_table_single_seed():
    wm = [{'party': 'CDU/CSU', 'score_pct': 70.0}]
    manifest = _make_manifest(
        'm',
        seeds={'1': {'wahlomat_scores': wm}},
        ablations={}
    )
    ci = compute_ci_table(manifest)
    assert ci['m']['CDU/CSU']['mean'] == 70.0
    assert ci['m']['CDU/CSU']['n'] == 1


def test_compute_ci_table_multiple_seeds():
    wm1 = [{'party': 'CDU/CSU', 'score_pct': 60.0}]
    wm2 = [{'party': 'CDU/CSU', 'score_pct': 80.0}]
    manifest = _make_manifest(
        'm',
        seeds={
            '1': {'wahlomat_scores': wm1},
            '2': {'wahlomat_scores': wm2},
        },
        ablations={}
    )
    ci = compute_ci_table(manifest)
    assert ci['m']['CDU/CSU']['mean'] == 70.0
    assert ci['m']['CDU/CSU']['n'] == 2
    assert ci['m']['CDU/CSU']['ci_lo'] <= 70.0 <= ci['m']['CDU/CSU']['ci_hi']
