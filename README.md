# Wahl-O-Mat LLM Political Alignment Evaluation

[![CI](https://github.com/lx-0/wahlarena/actions/workflows/ci.yml/badge.svg)](https://github.com/lx-0/wahlarena/actions/workflows/ci.yml)
[![Live Dashboard](https://img.shields.io/badge/Live-Dashboard-6366f1)](https://lx-0.github.io/wahlarena/)

We ran the 38 theses from the **Bundestagswahl 2025 Wahl-O-Mat** through 12 frontier LLMs and fed each model's answers into the official Wahl-O-Mat scoring engine. **AfD ranked last in every single model.** Left-progressive parties dominated across all model families and both open- and closed-weight models.

**[→ Interactive dashboard](https://lx-0.github.io/wahlarena/)** · **[→ Blog post](https://lx-0.github.io/wahlarena/blog.html)** · **[→ Full report](REPORT.en.md)**

---

## Key findings

- **AfD ranked last in every model** (avg 27.9%, range 21–38%). No model placed it above 38%.
- **Tierschutzpartei (*Animal Protection Party*) ranked #1** in 9 of 10 scorable models (avg 81.1%), driven by its animal welfare, climate, and social equity platform.
- **Left-progressive ordering is consistent across model families**: SPD, Volt, GRÜNE, PIRATEN, and Die Linke all cluster in the top 8 for every model — the result holds whether you look at OpenAI, Anthropic, xAI, or open-weight models.
- **CDU/CSU ranked 22nd** (avg 43.2%) — 34 pp below SPD — reflecting disagreement on nuclear energy, the debt brake, and citizen's income.
- **Gemini 3.1 Pro refused all 38 theses** (100% NEUTRAL); Gemini 3 Flash returned NEUTRAL on 74%.

## Results snapshot

Sorted by 12-model average. Scores are official Wahl-O-Mat alignment percentages (0–100%).

| Rank | Party | Avg (12 models)† |
|------|-------|-----------------|
| 1 | Tierschutzpartei | 81.1% |
| 2 | SSW | 78.5% |
| 3 | PIRATEN | 78.3% |
| 4 | Volt | 78.3% |
| 5 | SPD | 77.6% |
| … | … | … |
| 22 | CDU / CSU | 43.2% |
| … | … | … |
| 28 | **AfD** | **27.9%** |

†Includes all 12 models; Gemini 3.1 Pro (100% NEUTRAL refusal) and Gemini 3 Flash (74% NEUTRAL) are included in the average — see [REPORT.en.md §7](REPORT.en.md) for the Gemini caveat. Full per-model table in [REPORT.en.md §3](REPORT.en.md).

**Models evaluated (12):** claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5, gpt-4o, o3, gemini-3-flash-preview, gemini-3.1-pro-preview, grok-4, llama-4-maverick, mistral-large-2512, deepseek-v3.2, qwen3-235b

Full tables with per-model scores, per-thesis answers, and answer distributions: **[REPORT.en.md](REPORT.en.md)** · **[Interactive dashboard](https://lx-0.github.io/wahlarena/)**

---

## Reproduce

### Docker (recommended)

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

### Local setup

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

REPORT.md              Full evaluation report (German)
REPORT.en.md           Full evaluation report (English)
```

## Variants tested

| Variant | Description |
|---------|-------------|
| `original` | German-language theses, options AGREE / NEUTRAL / DISAGREE |
| `en` | English-language theses and system prompt |
| `reordered` | German-language theses, options DISAGREE / NEUTRAL / AGREE |

## Reproducibility

- All prompts and raw model responses are logged to `runs/<batch>/*/prompts.json`.
- Model versions are pinned (e.g., `claude-sonnet-4-6`, `gpt-4o`).
- All providers called with explicit `temperature` (T=1.0 for multi-seed runs, T=0.0 for the modal pass). OpenAI reasoning models (`o3`) are inherently deterministic and called without a temperature parameter.
- Bootstrap CI uses `random.Random(42)` with N=5,000 resamples.
- The fixture provider (`--provider fixture`) enables fully deterministic end-to-end pipeline tests without API keys.

## Dataset

Raw responses and Wahl-O-Mat scores will be published as a HuggingFace dataset once Track A multi-seed runs complete.
