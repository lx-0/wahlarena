"""
Integration test: full ask_llm.py pipeline using the fixture provider.
No real API keys required — fixture provider is deterministic via md5 hash.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / 'scripts'
ASK_LLM = str(SCRIPTS_DIR / 'ask_llm.py')
DATA_DIR = Path(__file__).parent.parent / 'data'


def _run_fixture(model: str = 'fixture-test', variant: str = 'original', out_dir: str = None) -> dict:
    result = subprocess.run(
        [sys.executable, ASK_LLM,
         '--model', model,
         '--provider', 'fixture',
         '--out', out_dir,
         '--variant', variant],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f'ask_llm.py failed:\n{result.stderr}'
    return result


class TestFixturePipeline:
    def test_produces_38_answers(self, tmp_path):
        _run_fixture(out_dir=str(tmp_path))
        answers = json.loads((tmp_path / 'answers.json').read_text())
        assert len(answers) == 38

    def test_answers_valid_range(self, tmp_path):
        _run_fixture(out_dir=str(tmp_path))
        answers = json.loads((tmp_path / 'answers.json').read_text())
        assert all(a in (-1, 0, 1) for a in answers), f'Out-of-range values: {set(answers) - {-1, 0, 1}}'

    def test_prompts_log_written(self, tmp_path):
        _run_fixture(out_dir=str(tmp_path))
        log = json.loads((tmp_path / 'prompts.json').read_text())
        assert log['model'] == 'fixture-test'
        assert log['variant'] == 'original'
        assert len(log['log']) == 38

    def test_prompts_log_fields(self, tmp_path):
        _run_fixture(out_dir=str(tmp_path))
        log = json.loads((tmp_path / 'prompts.json').read_text())
        for entry in log['log']:
            assert 'thesis_index' in entry
            assert 'raw_response' in entry
            assert 'choice' in entry
            assert entry['raw_response'] in ('AGREE', 'NEUTRAL', 'DISAGREE')

    def test_deterministic_across_runs(self, tmp_path):
        out_a = tmp_path / 'run_a'
        out_b = tmp_path / 'run_b'
        _run_fixture(model='fixture-det', out_dir=str(out_a))
        _run_fixture(model='fixture-det', out_dir=str(out_b))
        answers_a = json.loads((out_a / 'answers.json').read_text())
        answers_b = json.loads((out_b / 'answers.json').read_text())
        assert answers_a == answers_b

    def test_different_models_produce_different_answers(self, tmp_path):
        out_x = tmp_path / 'model_x'
        out_y = tmp_path / 'model_y'
        _run_fixture(model='fixture-model-x', out_dir=str(out_x))
        _run_fixture(model='fixture-model-y', out_dir=str(out_y))
        answers_x = json.loads((out_x / 'answers.json').read_text())
        answers_y = json.loads((out_y / 'answers.json').read_text())
        # Different seeds → different answers (extremely unlikely to be identical)
        assert answers_x != answers_y

    def test_variant_en(self, tmp_path):
        """English variant should produce 38 valid answers using theses_en.json."""
        if not (DATA_DIR / 'theses_en.json').exists():
            import pytest
            pytest.skip('theses_en.json not present')
        _run_fixture(variant='en', out_dir=str(tmp_path))
        answers = json.loads((tmp_path / 'answers.json').read_text())
        assert len(answers) == 38

    def test_variant_reordered(self, tmp_path):
        """Reordered variant should produce 38 valid answers."""
        _run_fixture(variant='reordered', out_dir=str(tmp_path))
        answers = json.loads((tmp_path / 'answers.json').read_text())
        assert len(answers) == 38
        assert all(a in (-1, 0, 1) for a in answers)
