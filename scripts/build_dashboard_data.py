#!/usr/bin/env python3
"""Build docs/data.json for the 12-model dashboard.

Answer data comes from the T=0 modal pass manifest
(`runs/modal_T0_2026-04-22T152725Z/manifest.json`). Alignment scores come from
REPORT.md §3 (the canonical 12-model table) — see REPORT.en.md §7 for the
measurement-vintage transparency note.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data.json"
EXISTING = json.loads(OUT.read_text())
MANIFEST = json.loads(
    (ROOT / "runs" / "modal_T0_2026-04-22T152725Z" / "manifest.json").read_text()
)

# T=0 manifest model id -> dashboard key used in this file and in docs/index.html.
T0_TO_KEY = {
    "gpt-4.1": "gpt-4o",
    "o3": "o3",
    "claude-opus-4-7": "claude-opus-4-7",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5",
    "gemini-3-flash-preview": "gemini-3-flash",
    "gemini-3.1-pro-preview": "gemini-3.1-pro",
    "grok-4-0709": "grok-4",
    "meta-llama/llama-4-maverick": "llama-4-maverick",
    "mistralai/mistral-large-2512": "mistral-large-2512",
    "deepseek/deepseek-v3.2": "deepseek-v3.2",
    "qwen/qwen3-235b-a22b": "qwen3-235b",
}

MODEL_ORDER = [
    "gpt-4o",
    "o3",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "gemini-3-flash",
    "gemini-3.1-pro",
    "grok-4",
    "llama-4-maverick",
    "mistral-large-2512",
    "deepseek-v3.2",
    "qwen3-235b",
]

PROVIDER = {
    "gpt-4o": "openai",
    "o3": "openai",
    "claude-opus-4-7": "anthropic",
    "claude-sonnet-4-6": "anthropic",
    "claude-haiku-4-5": "anthropic",
    "gemini-3-flash": "google",
    "gemini-3.1-pro": "google",
    "grok-4": "xai",
    "llama-4-maverick": "openrouter",
    "mistral-large-2512": "openrouter",
    "deepseek-v3.2": "openrouter",
    "qwen3-235b": "openrouter",
}

# Alignment scores transcribed from REPORT.md §3. Per-party ordered by MODEL_ORDER.
ALIGNMENT_ROWS = [
    ("Tierschutzpartei", 81.1, [85.5, 78.9, 80.3, 85.5, 71.1, 77.6, 77.6, 88.2, 82.9, 78.9, 80.3, 86.8]),
    ("SSW", 78.5, [82.9, 76.3, 77.6, 82.9, 68.4, 77.6, 77.6, 82.9, 77.6, 76.3, 80.3, 81.6]),
    ("PIRATEN", 78.3, [81.6, 72.4, 81.6, 84.2, 67.1, 81.6, 78.9, 81.6, 78.9, 75.0, 78.9, 77.6]),
    ("Volt", 78.3, [84.2, 75.0, 78.9, 84.2, 67.1, 76.3, 76.3, 84.2, 78.9, 75.0, 76.3, 82.9]),
    ("SPD", 77.6, [81.6, 75.0, 76.3, 81.6, 72.4, 71.1, 76.3, 76.3, 76.3, 80.3, 84.2, 80.3]),
    ("Die PARTEI", 77.6, [82.9, 76.3, 75.0, 80.3, 65.8, 72.4, 75.0, 85.5, 85.5, 73.7, 75.0, 84.2]),
    ("GRÜNE", 77.0, [78.9, 75.0, 76.3, 78.9, 67.1, 71.1, 78.9, 81.6, 76.3, 80.3, 78.9, 80.3]),
    ("Die Linke", 75.7, [77.6, 73.7, 72.4, 80.3, 68.4, 72.4, 69.7, 82.9, 82.9, 71.1, 77.6, 78.9]),
    ("MERA25", 73.7, [76.3, 72.4, 71.1, 78.9, 67.1, 68.4, 68.4, 81.6, 78.9, 69.7, 73.7, 77.6]),
    ("MLPD", 73.5, [75.0, 71.1, 72.4, 72.4, 65.8, 69.7, 72.4, 80.3, 77.6, 71.1, 75.0, 78.9]),
    ("Die Gerechtigkeitspartei — Team Todenhöfer", 71.5, [73.7, 61.8, 73.7, 71.1, 67.1, 65.8, 71.1, 76.3, 78.9, 75.0, 71.1, 72.4]),
    ("PdF", 70.6, [73.7, 67.1, 78.9, 76.3, 61.8, 71.1, 71.1, 65.8, 71.1, 64.5, 76.3, 69.7]),
    ("ÖDP", 69.5, [72.4, 71.1, 72.4, 67.1, 63.2, 56.6, 69.7, 69.7, 75.0, 65.8, 72.4, 78.9]),
    ("SGP", 69.5, [72.4, 65.8, 69.7, 72.4, 60.5, 64.5, 67.1, 77.6, 75.0, 65.8, 69.7, 73.7]),
    ("PdH", 69.1, [67.1, 73.7, 69.7, 72.4, 68.4, 69.7, 75.0, 69.7, 61.8, 60.5, 72.4, 68.4]),
    ("BSW", 61.2, [67.1, 60.5, 61.8, 61.8, 52.6, 56.6, 59.2, 61.8, 67.1, 60.5, 61.8, 63.2]),
    ("Verjüngungsforschung", 60.5, [56.6, 68.4, 61.8, 56.6, 57.9, 59.2, 72.4, 56.6, 51.3, 55.3, 67.1, 63.2]),
    ("FREIE WÄHLER", 53.3, [53.9, 50.0, 56.6, 53.9, 50.0, 61.8, 51.3, 48.7, 56.6, 52.6, 53.9, 50.0]),
    ("dieBasis", 52.0, [55.3, 51.3, 52.6, 47.4, 51.3, 47.4, 55.3, 47.4, 52.6, 53.9, 55.3, 53.9]),
    ("MENSCHLICHE WELT", 49.6, [48.7, 52.6, 53.9, 48.7, 55.3, 40.8, 53.9, 43.4, 46.1, 50.0, 51.3, 50.0]),
    ("FDP", 48.2, [38.2, 52.6, 53.9, 48.7, 57.9, 51.3, 51.3, 48.7, 40.8, 47.4, 48.7, 39.5]),
    ("CDU / CSU", 43.2, [39.5, 48.7, 42.1, 39.5, 48.7, 42.1, 47.4, 36.8, 39.5, 48.7, 44.7, 40.8]),
    ("BüSo", 42.3, [40.8, 47.4, 43.4, 32.9, 42.1, 32.9, 46.1, 43.4, 46.1, 42.1, 43.4, 47.4]),
    ("Bündnis C", 39.0, [38.2, 39.5, 43.4, 35.5, 47.4, 35.5, 43.4, 32.9, 32.9, 44.7, 38.2, 36.8]),
    ("WerteUnion", 37.3, [27.6, 42.1, 40.8, 35.5, 50.0, 38.2, 38.2, 35.5, 30.3, 39.5, 38.2, 31.6]),
    ("BÜNDNIS DEUTSCHLAND", 36.2, [32.9, 36.8, 40.8, 35.5, 47.4, 35.5, 38.2, 30.3, 25.0, 42.1, 38.2, 31.6]),
    ("BP", 36.2, [30.3, 36.8, 40.8, 35.5, 42.1, 43.4, 38.2, 32.9, 30.3, 39.5, 35.5, 28.9]),
    ("AfD", 27.9, [23.7, 30.3, 28.9, 23.7, 38.2, 28.9, 31.6, 23.7, 21.1, 30.3, 28.9, 25.0]),
]

assert len(ALIGNMENT_ROWS) == 28, "party count mismatch"

parties = []
for name, avg, scores in ALIGNMENT_ROWS:
    assert len(scores) == len(MODEL_ORDER), f"score count mismatch for {name}"
    parties.append(
        {
            "party": name,
            "avg": avg,
            "scores": dict(zip(MODEL_ORDER, scores)),
        }
    )

# Per-thesis: T=0 modal-pass answers for all 12 models.
manifest_by_t0 = {m["model"]: m for m in MANIFEST["models"] if m.get("success")}

theses = []
for existing_thesis in EXISTING["theses"]:
    idx = existing_thesis["index"]
    per_model = {}
    for t0_id, key in T0_TO_KEY.items():
        entry = manifest_by_t0.get(t0_id)
        if not entry:
            continue
        choice = entry["answers"][idx]
        raw = {1: "AGREE", 0: "NEUTRAL", -1: "DISAGREE"}[choice]
        per_model[key] = {"choice": choice, "raw": raw}
    theses.append(
        {
            "index": idx,
            "topic_en": existing_thesis["topic_en"],
            "statement_en": existing_thesis["statement_en"],
            "topic_de": existing_thesis["topic_de"],
            "statement_de": existing_thesis["statement_de"],
            "per_model": per_model,
        }
    )

# Answer distribution: T=0 modal-pass counts for all 12 models.
distribution = {}
for t0_id, key in T0_TO_KEY.items():
    entry = manifest_by_t0.get(t0_id)
    if not entry:
        continue
    a = sum(1 for x in entry["answers"] if x == 1)
    n = sum(1 for x in entry["answers"] if x == 0)
    d = sum(1 for x in entry["answers"] if x == -1)
    distribution[key] = {
        "agree": a,
        "neutral": n,
        "disagree": d,
        "provider": PROVIDER[key],
    }

out = {
    "generated": "2026-04-22",
    "models": MODEL_ORDER,
    "parties": parties,
    "theses": theses,
    "distribution": distribution,
}

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(f"wrote {OUT} — {len(parties)} parties × {len(MODEL_ORDER)} models, {len(theses)} theses, {len(distribution)} distributions")
