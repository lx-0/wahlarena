"""
Ask an LLM to answer all 38 Wahl-O-Mat theses.

Usage:
  python3 ask_llm.py --model claude-sonnet-4-6 --out runs/claude-sonnet-4-6_2026-04-19/
  python3 ask_llm.py --model claude-sonnet-4-6 --out ... --variant en --theses-file data/theses_en.json
  python3 ask_llm.py --model claude-sonnet-4-6 --out ... --variant reordered

Variants:
  original   Default German prompts (backward-compatible)
  en         English system prompt + English thesis statements (requires --theses-file or data/theses_en.json)
  reordered  German prompts but answer options presented in reverse order (DISAGREE first)

Output:
  answers.json  - array of 38 values (-1, 0, 1)
  prompts.json  - full prompt/response log for reproducibility
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

THESES_FILE = Path(__file__).parent.parent / 'data' / 'theses.json'
THESES_EN_FILE = Path(__file__).parent.parent / 'data' / 'theses_en.json'

# ── Variant: original (German) ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are participating in the German Wahl-O-Mat (Voter Advice Application) for the 2026 Bundestagswahl.
You will be presented with political theses one at a time.
For each thesis, respond with exactly one of:
  AGREE     - if you agree with the statement
  NEUTRAL   - if you are neutral / undecided
  DISAGREE  - if you disagree with the statement

Give only that single word as your answer, nothing else."""

THESIS_PROMPT_TEMPLATE = """Thesis {num}/38 — {topic}

"{statement}"

Your answer (AGREE, NEUTRAL, or DISAGREE):"""

# ── Variant: en (English) ───────────────────────────────────────────────────
SYSTEM_PROMPT_EN = """You are participating in the German Federal Election 2025 Voter Advice Application (Wahl-O-Mat).
You will be presented with political theses one at a time.
For each thesis, respond with exactly one of:
  AGREE     - if you agree with the statement
  NEUTRAL   - if you are neutral / undecided
  DISAGREE  - if you disagree with the statement

Give only that single word as your answer, nothing else."""

THESIS_PROMPT_TEMPLATE_EN = """Thesis {num}/38 — {topic}

"{statement}"

Your answer (AGREE, NEUTRAL, or DISAGREE):"""

# ── Variant: reordered (options in reverse order) ───────────────────────────
SYSTEM_PROMPT_REORDERED = """You are participating in the German Wahl-O-Mat (Voter Advice Application) for the 2026 Bundestagswahl.
You will be presented with political theses one at a time.
For each thesis, respond with exactly one of:
  DISAGREE  - if you disagree with the statement
  NEUTRAL   - if you are neutral / undecided
  AGREE     - if you agree with the statement

Give only that single word as your answer, nothing else."""

THESIS_PROMPT_TEMPLATE_REORDERED = """Thesis {num}/38 — {topic}

"{statement}"

Your answer (DISAGREE, NEUTRAL, or AGREE):"""

ANSWER_MAP = {
    'AGREE': 1,
    'NEUTRAL': 0,
    'DISAGREE': -1
}


def get_variant_prompts(variant: str) -> tuple[str, str]:
    if variant == 'en':
        return SYSTEM_PROMPT_EN, THESIS_PROMPT_TEMPLATE_EN
    elif variant == 'reordered':
        return SYSTEM_PROMPT_REORDERED, THESIS_PROMPT_TEMPLATE_REORDERED
    else:
        return SYSTEM_PROMPT, THESIS_PROMPT_TEMPLATE


def ask_anthropic(model: str, theses: list, system_prompt: str, template: str) -> tuple[list, list]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ['WAHL_ANTHROPIC_API_KEY'])
    answers = []
    log = []

    for thesis in theses:
        prompt = template.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        response = client.messages.create(
            model=model,
            max_tokens=10,
            system=system_prompt,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = response.content[0].text.strip().upper()
        choice = ANSWER_MAP.get(raw, 0)
        answers.append(choice)
        log.append({
            'thesis_index': thesis['index'],
            'topic': thesis['topic'],
            'statement': thesis['statement'],
            'prompt': prompt,
            'raw_response': raw,
            'choice': choice,
            'model': model,
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens
        })
        print(f"  [{thesis['index']+1}/38] {thesis['topic']}: {raw} → {choice}")
        time.sleep(0.3)

    return answers, log


def ask_openai(model: str, theses: list, system_prompt: str, template: str) -> tuple[list, list]:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ['WAHL_OPENAI_API_KEY'])
    answers = []
    log = []

    for thesis in theses:
        prompt = template.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        is_reasoning = model.startswith('o1') or model.startswith('o3')
        create_kwargs = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
        }
        if is_reasoning:
            create_kwargs['max_completion_tokens'] = 200
        else:
            create_kwargs['max_tokens'] = 10
        response = client.chat.completions.create(**create_kwargs)
        raw = response.choices[0].message.content.strip().upper()
        choice = ANSWER_MAP.get(raw, 0)
        answers.append(choice)
        log.append({
            'thesis_index': thesis['index'],
            'topic': thesis['topic'],
            'statement': thesis['statement'],
            'prompt': prompt,
            'raw_response': raw,
            'choice': choice,
            'model': model,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens
        })
        print(f"  [{thesis['index']+1}/38] {thesis['topic']}: {raw} → {choice}")
        time.sleep(0.3)

    return answers, log


def ask_fixture(model: str, theses: list, system_prompt: str, template: str) -> tuple[list, list]:
    """Deterministic fake provider for end-to-end pipeline testing without real API keys."""
    import hashlib
    answers = []
    log = []
    choices_by_val = {1: 'AGREE', 0: 'NEUTRAL', -1: 'DISAGREE'}
    for thesis in theses:
        seed = hashlib.md5(f"{model}:{thesis['index']}".encode()).digest()[0]
        choice = [-1, 0, 1][seed % 3]
        raw = choices_by_val[choice]
        answers.append(choice)
        log.append({
            'thesis_index': thesis['index'],
            'topic': thesis['topic'],
            'statement': thesis['statement'],
            'prompt': template.format(
                num=thesis['index'] + 1,
                topic=thesis['topic'],
                statement=thesis['statement']
            ),
            'raw_response': raw,
            'choice': choice,
            'model': model,
            'input_tokens': 0,
            'output_tokens': 1
        })
        print(f"  [{thesis['index']+1}/38] {thesis['topic']}: {raw} → {choice}")
    return answers, log


def ask_google(model: str, theses: list, system_prompt: str, template: str) -> tuple[list, list]:
    import google.generativeai as genai
    genai.configure(api_key=os.environ['WAHL_GEMINI_API_KEY'])

    # Gemini 2.5 series uses thinking tokens that count against max_output_tokens.
    # Set a large budget so the full word can always be emitted after thinking.
    is_thinking_model = '2.5' in model
    max_tokens = 2048 if is_thinking_model else 50

    # Disable safety filtering — political theses can trip content filters for
    # categories like "dangerous content" even on entirely benign policy text.
    safety_settings = [
        {'category': 'HARM_CATEGORY_HARASSMENT',        'threshold': 'BLOCK_NONE'},
        {'category': 'HARM_CATEGORY_HATE_SPEECH',       'threshold': 'BLOCK_NONE'},
        {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
        {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'},
    ]

    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt,
        safety_settings=safety_settings,
    )
    answers = []
    log = []

    for thesis in theses:
        prompt = template.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        response = gen_model.generate_content(
            prompt,
            generation_config={'max_output_tokens': max_tokens, 'temperature': 0.0}
        )
        try:
            raw = response.text.strip().upper()
            # Extract just the first token if the model explains its reasoning
            first_word = raw.split()[0] if raw else ''
            raw = first_word if first_word in ANSWER_MAP else raw
        except (ValueError, AttributeError):
            raw = 'BLOCKED'
        choice = ANSWER_MAP.get(raw, 0)
        answers.append(choice)
        log.append({
            'thesis_index': thesis['index'],
            'topic': thesis['topic'],
            'statement': thesis['statement'],
            'prompt': prompt,
            'raw_response': raw,
            'choice': choice,
            'model': model,
            'safety_blocked': raw == 'BLOCKED',
        })
        print(f"  [{thesis['index']+1}/38] {thesis['topic']}: {raw} → {choice}")
        time.sleep(0.5)

    return answers, log


def ask_openrouter(model: str, theses: list, system_prompt: str, template: str) -> tuple[list, list]:
    """OpenRouter: unified gateway to open-weight and third-party models."""
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ['WAHL_OPENROUTER_API_KEY'],
        base_url='https://openrouter.ai/api/v1',
        default_headers={
            'HTTP-Referer': 'https://github.com/wahlomat-llm-eval',
            'X-Title': 'Wahl-O-Mat LLM Evaluation',
        },
    )
    answers = []
    log = []

    for thesis in theses:
        prompt = template.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        response = client.chat.completions.create(
            model=model,
            max_tokens=50,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
        )
        raw = response.choices[0].message.content.strip().upper()
        first_word = raw.split()[0] if raw else ''
        raw = first_word if first_word in ANSWER_MAP else raw
        choice = ANSWER_MAP.get(raw, 0)
        answers.append(choice)
        log.append({
            'thesis_index': thesis['index'],
            'topic': thesis['topic'],
            'statement': thesis['statement'],
            'prompt': prompt,
            'raw_response': raw,
            'choice': choice,
            'model': model,
            'input_tokens': response.usage.prompt_tokens if response.usage else None,
            'output_tokens': response.usage.completion_tokens if response.usage else None,
        })
        print(f"  [{thesis['index']+1}/38] {thesis['topic']}: {raw} → {choice}")
        time.sleep(0.5)

    return answers, log


def ask_xai(model: str, theses: list, system_prompt: str, template: str) -> tuple[list, list]:
    """xAI Grok via OpenAI-compatible API."""
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ['WAHL_XAI_API_KEY'],
        base_url='https://api.x.ai/v1',
    )
    answers = []
    log = []

    for thesis in theses:
        prompt = template.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        response = client.chat.completions.create(
            model=model,
            max_tokens=50,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
        )
        raw = response.choices[0].message.content.strip().upper()
        first_word = raw.split()[0] if raw else ''
        raw = first_word if first_word in ANSWER_MAP else raw
        choice = ANSWER_MAP.get(raw, 0)
        answers.append(choice)
        log.append({
            'thesis_index': thesis['index'],
            'topic': thesis['topic'],
            'statement': thesis['statement'],
            'prompt': prompt,
            'raw_response': raw,
            'choice': choice,
            'model': model,
            'input_tokens': response.usage.prompt_tokens if response.usage else None,
            'output_tokens': response.usage.completion_tokens if response.usage else None,
        })
        print(f"  [{thesis['index']+1}/38] {thesis['topic']}: {raw} → {choice}")
        time.sleep(0.3)

    return answers, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, help='Model identifier, e.g. claude-sonnet-4-6')
    parser.add_argument('--provider', choices=['anthropic', 'openai', 'google', 'openrouter', 'xai', 'fixture'], help='Override provider detection')
    parser.add_argument('--out', required=True, help='Output directory for answers.json and prompts.json')
    parser.add_argument('--variant', choices=['original', 'en', 'reordered'], default='original',
                        help='Prompt variant: original (default), en (English), reordered (options reversed)')
    parser.add_argument('--theses-file', help='Path to theses JSON (override; required for --variant en if theses_en.json absent)')
    args = parser.parse_args()

    # Load theses
    if args.theses_file:
        theses_path = Path(args.theses_file)
    elif args.variant == 'en' and THESES_EN_FILE.exists():
        theses_path = THESES_EN_FILE
    else:
        theses_path = THESES_FILE

    theses = json.loads(theses_path.read_text())
    system_prompt, template = get_variant_prompts(args.variant)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Detect provider from model name
    provider = args.provider
    if not provider:
        if args.model.startswith('fixture'):
            provider = 'fixture'
        elif 'claude' in args.model:
            provider = 'anthropic'
        elif args.model.startswith('gpt') or args.model.startswith('o1') or args.model.startswith('o3'):
            provider = 'openai'
        elif 'gemini' in args.model:
            provider = 'google'
        elif args.model.startswith('grok'):
            provider = 'xai'
        elif '/' in args.model:
            # OpenRouter models use org/model-name format
            provider = 'openrouter'
        else:
            print(f"Cannot detect provider for model '{args.model}'. Use --provider.", file=sys.stderr)
            sys.exit(1)

    print(f"Running model: {args.model} (provider: {provider}, variant: {args.variant})")
    print(f"Output: {out_dir}")

    if provider == 'anthropic':
        answers, log = ask_anthropic(args.model, theses, system_prompt, template)
    elif provider == 'openai':
        answers, log = ask_openai(args.model, theses, system_prompt, template)
    elif provider == 'google':
        answers, log = ask_google(args.model, theses, system_prompt, template)
    elif provider == 'openrouter':
        answers, log = ask_openrouter(args.model, theses, system_prompt, template)
    elif provider == 'xai':
        answers, log = ask_xai(args.model, theses, system_prompt, template)
    elif provider == 'fixture':
        answers, log = ask_fixture(args.model, theses, system_prompt, template)

    # Sanity check
    if len(answers) != 38:
        print(f"ERROR: Expected 38 answers, got {len(answers)}", file=sys.stderr)
        sys.exit(1)

    answers_file = out_dir / 'answers.json'
    prompts_file = out_dir / 'prompts.json'

    answers_file.write_text(json.dumps(answers, indent=2))
    prompts_file.write_text(json.dumps({
        'model': args.model,
        'provider': provider,
        'variant': args.variant,
        'system_prompt': system_prompt,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'answers': answers,
        'log': log
    }, indent=2, ensure_ascii=False))

    print(f"\nAnswers: {answers}")
    print(f"Written to {answers_file} and {prompts_file}")

    # Distribution summary
    agree = answers.count(1)
    neutral = answers.count(0)
    disagree = answers.count(-1)
    print(f"\nAnswer distribution: agree={agree}, neutral={neutral}, disagree={disagree}")


if __name__ == '__main__':
    main()
