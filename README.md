# Wahl-O-Mat LLM Political Alignment Evaluation

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)

Evaluate top frontier LLMs on the 38 theses of the Bundestagswahl 2025 [Wahl-O-Mat](https://www.wahl-o-mat.de/). Each model answers every thesis (AGREE / NEUTRAL / DISAGREE); official party alignment scores are computed by submitting answers to the live Wahl-O-Mat site via Playwright.

**Outputs:**
- **[REPORT.en.md](REPORT.en.md)** — Full English evaluation report (methodology, all 28 parties, per-model analysis, limitations)
- **[Live dashboard](https://OWNER.github.io/REPO/)** — Interactive alignment heatmap, answer distribution, per-thesis drill-down ([source](docs/index.html))
- **[Blog post](https://OWNER.github.io/REPO/blog.html)** — ~1600-word writeup of key findings ([source](BLOG.md))
- **[REPORT.md](REPORT.md)** — German-language source report

> **To activate the live URLs:** push to GitHub and enable GitHub Pages with source set to `docs/` in the repo Settings → Pages.

## Results snapshot

| Rank | Party | Avg (5 models) |
|------|-------|---------------|
| 1 | Tierschutzpartei | 80.3% |
| 2 | Volt | 77.9% |
| 3 | SSW | 77.6% |
| 4 | SPD | 77.4% |
| 28 | AfD | 29.0% |

AfD ranked **last in every model**. Tierschutzpartei ranked first or co-first in 4 of 5 models. The top-5 and bottom-5 were consistent across both OpenAI and Anthropic model families.

Full tables with per-model scores are in [REPORT.en.md](REPORT.en.md). Explore per-thesis answers interactively in [docs/index.html](docs/index.html).

## Reproduce in one command (Docker)

```bash
# Build the image
docker build -t wahl-o-mat .

# Run tests (no API keys required — uses fixture provider)
docker run --rm wahl-o-mat

# Reproduce the full evaluation (requires API keys)
docker run --rm \
  -e WAHL_ANTHROPIC_API_KEY=sk-ant-... \
  -e WAHL_OPENAI_API_KEY=sk-... \
  wahl-o-mat \
  python3 scripts/run_all_models.py
```

The image pins Python 3.13, Node 24, all Python deps (requirements.txt), and Node deps (package-lock.json) so results are bit-exact across machines.

## Local setup

```bash
# Python deps
pip install -r requirements.txt

# Node deps
npm ci

# Install Playwright browser
npx playwright install chromium

# Run tests (no API keys needed)
pytest tests/ -v

# Run full evaluation
export WAHL_ANTHROPIC_API_KEY=sk-ant-...
export WAHL_OPENAI_API_KEY=sk-...
python3 scripts/run_all_models.py
```

## Project structure

```
data/
  theses.json          38 Wahl-O-Mat theses (German)
  theses_en.json       English translations (cached)
  parties.json         Party metadata

scripts/
  ask_llm.py           Prompt a model through all 38 theses
  run_all_models.py    Batch runner for all models
  run_track_a.py       Multi-seed + prompt ablation runner (Track A)
  analyze_track_a.py   Bootstrap CI, robustness, refusal analysis
  compute_alignment.py Wahl-O-Mat party alignment scoring
  wahlomat_runner.js   Playwright browser automation for wahl-o-mat.de

runs/                  Per-run outputs (answers, prompts, Wahl-O-Mat scores)
tests/                 pytest test suite (unit + integration)

REPORT.md              Full evaluation report
```

## Variants tested

| Variant | Description |
|---------|-------------|
| `original` | German-language theses, options AGREE / NEUTRAL / DISAGREE |
| `en` | English-language theses and system prompt |
| `reordered` | German-language theses, options DISAGREE / NEUTRAL / AGREE |

## Dataset

Raw responses and Wahl-O-Mat scores will be published as a HuggingFace dataset once Track A multi-seed runs complete.

## Reproducibility

- All prompts and raw model responses are logged to `runs/<batch>/*/prompts.json`.
- Model versions are pinned (e.g., `claude-sonnet-4-6`, `gpt-4o`).
- Bootstrap CI uses `random.Random(42)` with N=5,000 resamples.
- The fixture provider (`--provider fixture`) enables fully deterministic end-to-end pipeline tests without API keys.
