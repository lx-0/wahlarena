"""
Ask an LLM to answer all 38 Wahl-O-Mat theses.

Usage:
  python3 ask_llm.py --model claude-sonnet-4-6 --out runs/claude-sonnet-4-6_2026-04-19/

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

ANSWER_MAP = {
    'AGREE': 1,
    'NEUTRAL': 0,
    'DISAGREE': -1
}


def ask_anthropic(model: str, theses: list) -> tuple[list, list]:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ['WAHL_ANTHROPIC_API_KEY'])
    answers = []
    log = []

    for thesis in theses:
        prompt = THESIS_PROMPT_TEMPLATE.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        response = client.messages.create(
            model=model,
            max_tokens=10,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = response.content[0].text.strip().upper()
        choice = ANSWER_MAP.get(raw, 0)  # default neutral if unexpected
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
        time.sleep(0.3)  # rate limit buffer

    return answers, log


def ask_openai(model: str, theses: list) -> tuple[list, list]:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ['WAHL_OPENAI_API_KEY'])
    answers = []
    log = []

    for thesis in theses:
        prompt = THESIS_PROMPT_TEMPLATE.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        # o3/o1 reasoning models use max_completion_tokens, not max_tokens
        is_reasoning = model.startswith('o1') or model.startswith('o3')
        create_kwargs = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ],
        }
        if is_reasoning:
            # Reasoning models need headroom; internal chain-of-thought consumes tokens before output
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


def ask_fixture(model: str, theses: list) -> tuple[list, list]:
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
            'prompt': THESIS_PROMPT_TEMPLATE.format(
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


def ask_google(model: str, theses: list) -> tuple[list, list]:
    import google.generativeai as genai
    genai.configure(api_key=os.environ['WAHL_GEMINI_API_KEY'])
    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=SYSTEM_PROMPT
    )
    answers = []
    log = []

    for thesis in theses:
        prompt = THESIS_PROMPT_TEMPLATE.format(
            num=thesis['index'] + 1,
            topic=thesis['topic'],
            statement=thesis['statement']
        )
        response = gen_model.generate_content(
            prompt,
            generation_config={'max_output_tokens': 10, 'temperature': 0.0}
        )
        try:
            raw = response.text.strip().upper()
        except ValueError:
            # Safety filter blocked the response; treat as NEUTRAL
            raw = 'NEUTRAL'
        choice = ANSWER_MAP.get(raw, 0)
        answers.append(choice)
        log.append({
            'thesis_index': thesis['index'],
            'topic': thesis['topic'],
            'statement': thesis['statement'],
            'prompt': prompt,
            'raw_response': raw,
            'choice': choice,
            'model': model
        })
        print(f"  [{thesis['index']+1}/38] {thesis['topic']}: {raw} → {choice}")
        time.sleep(0.5)

    return answers, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True, help='Model identifier, e.g. claude-sonnet-4-6')
    parser.add_argument('--provider', choices=['anthropic', 'openai', 'google', 'fixture'], help='Override provider detection')
    parser.add_argument('--out', required=True, help='Output directory for answers.json and prompts.json')
    args = parser.parse_args()

    theses = json.loads(THESES_FILE.read_text())
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
        else:
            print(f"Cannot detect provider for model '{args.model}'. Use --provider.", file=sys.stderr)
            sys.exit(1)

    print(f"Running model: {args.model} (provider: {provider})")
    print(f"Output: {out_dir}")

    if provider == 'anthropic':
        answers, log = ask_anthropic(args.model, theses)
    elif provider == 'openai':
        answers, log = ask_openai(args.model, theses)
    elif provider == 'google':
        answers, log = ask_google(args.model, theses)
    elif provider == 'fixture':
        answers, log = ask_fixture(args.model, theses)

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
        'system_prompt': SYSTEM_PROMPT,
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
