# ProspectMind

**AI-powered B2B outreach personalization engine.**  
Scrapes live company context → synthesizes research briefs → generates hyper-personalized cold email openers at scale. Self-hosted. Multi-LLM.

[![CI](https://github.com/Ahmad317-Engineer/prospectmind/actions/workflows/ci.yml/badge.svg)](https://github.com/Ahmad317-Engineer/prospectmind/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI version](https://img.shields.io/badge/pypi-coming%20soon-orange)](https://pypi.org/)

---

## The Problem

Cold email reply rates are at an all-time low. The #1 fix is genuine personalization — but manually researching each prospect (company news, hiring signals, product focus, tech stack) takes **10–20 minutes per lead**.

At 100 prospects/week, that's 2+ full working days lost to research. Paid tools like Clay ($149–800/mo), Smartwriter ($49–149/mo), and Quicklines charge a fortune, lock you into their platform, and produce robotic "personalization" that looks like a mail merge.

**ProspectMind** is the open-source answer. Give it a CSV. It does the research. You get personalized emails.

---

## Features

- **Multi-source research pipeline** — scrapes company homepage, About page, careers/jobs page, extracts meta signals, detects tech stack
- **3 personalization outputs per prospect** — subject lines (A/B testable), email openers, value prop framing
- **Multi-LLM support** — OpenAI (GPT-4o/mini), Anthropic (Claude Haiku/Sonnet), Ollama (local, free)
- **Async + concurrent** — processes multiple prospects in parallel; configurable rate limiting
- **Retry logic** — automatic retries with exponential backoff on LLM failures
- **Personalization scoring** — each result gets a 0–100 score based on research depth
- **CSV in, CSV out** — drops into any existing outreach workflow (Apollo, Instantly, Smartlead, Lemlist)
- **Dry-run mode** — test scraping without burning LLM credits
- **100% self-hostable** — no SaaS lock-in, no data leaves your machine

---

## Quickstart

### Install

```bash
pip install prospectmind

# With your LLM provider:
pip install prospectmind[openai]      # OpenAI
pip install prospectmind[anthropic]   # Anthropic Claude
pip install prospectmind              # Ollama (local, no extra dep needed)
```

Or from source:

```bash
git clone https://github.com/Ahmad317-Engineer/prospectmind.git
cd prospectmind
pip install -e ".[all]"
```

### Generate a sample CSV

```bash
prospectmind sample
# Creates prospects_sample.csv
```

### Run personalization

```bash
# With OpenAI (fastest, cheapest)
export OPENAI_API_KEY=sk-...
prospectmind run prospects.csv --provider openai

# With Anthropic Claude
export ANTHROPIC_API_KEY=sk-ant-...
prospectmind run prospects.csv --provider anthropic

# With Ollama (free, local, private)
ollama pull llama3.1
prospectmind run prospects.csv --provider ollama

# Tell it what you're selling for sharper value props
prospectmind run prospects.csv \
  --provider openai \
  --product "Acme Analytics" \
  --value-prop "Reduces reporting time by 80% for RevOps teams"
```

---

## Input CSV Format

| Column | Required | Description |
|--------|----------|-------------|
| `first_name` | ✅ | Prospect's first name |
| `last_name` | ✅ | Prospect's last name |
| `title` | ✅ | Job title |
| `company` | ✅ | Company name |
| `domain` | optional | Company domain (enables web scraping) |
| `email` | optional | Passed through to output |
| `linkedin_url` | optional | Passed through |
| `notes` | optional | Extra context |

**Example:**

```csv
first_name,last_name,title,company,domain,email
Sarah,Chen,VP of Engineering,Acme Corp,acme.com,sarah@acme.com
James,Park,Head of Marketing,BetaStartup,betastartup.io,james@betastartup.io
```

---

## Output CSV

ProspectMind adds these columns to your CSV:

| Column | Description |
|--------|-------------|
| `subject_line_1/2/3` | 3 A/B-testable subject line options |
| `opener_1/2/3` | 3 personalized first-line options |
| `value_prop` | Tailored one-sentence value proposition |
| `personalization_score` | 0–100 (higher = more specific signals found) |
| `error` | Non-empty if processing failed for this row |

---

## CLI Reference

```
prospectmind run [OPTIONS] INPUT_FILE

Options:
  --output, -o PATH         Output CSV path (default: <input>_personalized.csv)
  --provider, -p ENUM       LLM provider: openai | anthropic | ollama
  --model, -m TEXT          Override model (e.g. gpt-4o, claude-3-5-sonnet)
  --api-key TEXT            API key (or use env var)
  --concurrency, -c INT     Parallel prospects [1–20, default: 3]
  --product TEXT            Your product name
  --value-prop TEXT         Your core value proposition
  --skip-scraping           Skip web scraping (faster, less personalized)
  --dry-run                 Scrape but skip LLM (test mode)
  --retries INT             Max LLM retries per prospect [0–10, default: 3]
  --timeout INT             Scraping timeout in seconds [5–120, default: 30]

prospectmind sample [OPTIONS]
  --output, -o PATH         Output path (default: prospects_sample.csv)

prospectmind --version
```

---

## How It Works

```
Input CSV
    │
    ▼
┌─────────────────────────────────────────┐
│  1. SCRAPE (async, concurrent)          │
│     • Company homepage (meta, tagline)  │
│     • Careers / jobs page               │
│     • Tech stack detection              │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│  2. SYNTHESIZE                          │
│     • Build company context brief       │
│     • Extract hiring signals            │
│     • Score data completeness           │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│  3. PERSONALIZE (LLM)                   │
│     • 3× Subject lines (A/B testable)   │
│     • 3× Email openers (distinct angles)│
│     • 1× Tailored value proposition     │
└────────────────────┬────────────────────┘
                     │
                     ▼
               Output CSV
```

---

## LLM Cost Estimates

For 100 prospects (with scraping):

| Provider | Model | Estimated Cost |
|----------|-------|----------------|
| OpenAI | gpt-4o-mini | ~$0.05–0.15 |
| OpenAI | gpt-4o | ~$0.50–1.50 |
| Anthropic | claude-3-5-haiku | ~$0.08–0.20 |
| Ollama | llama3.1 (local) | **$0.00** |

---

## Python API

```python
import asyncio
from pathlib import Path
from prospectmind.models import Prospect, RunConfig, LLMProvider
from prospectmind.pipeline import run_pipeline

prospects = [
    Prospect(
        first_name="Sarah",
        last_name="Chen",
        title="VP of Engineering",
        company="Acme Corp",
        domain="acme.com",
    )
]

config = RunConfig(
    provider=LLMProvider.OPENAI,
    your_product="My SaaS Tool",
    your_value_prop="Saves 5 hours/week for eng teams",
)

async def main():
    async for result in run_pipeline(prospects, config):
        print(result.prospect.full_name)
        print(result.subject_lines)
        print(result.openers)

asyncio.run(main())
```

---

## Configuration via Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Extending ProspectMind

### Add a new LLM provider

```python
# prospectmind/providers/my_provider.py
from .base import BaseLLMProvider, LLMResponse

class MyProvider(BaseLLMProvider):
    @property
    def name(self) -> str:
        return "My LLM"

    async def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        # Call your API here
        text = await my_api.generate(system_prompt, user_prompt)
        return LLMResponse(content=text, model=self.model)
```

Then register it in `providers/__init__.py` and `models.py`.

---

## Why Not Just Use [Clay / Smartwriter / Quicklines]?

| | ProspectMind | Clay | Smartwriter | Quicklines |
|--|---|---|---|---|
| Cost | **Free** | $149–800/mo | $49–149/mo | Discontinued |
| Self-hosted | ✅ | ❌ | ❌ | N/A |
| Multi-LLM | ✅ | ❌ | ❌ | N/A |
| Batch CSV | ✅ | ✅ | ✅ | ✅ |
| No rate limits | ✅ | ❌ | ❌ | N/A |
| Open source | ✅ | ❌ | ❌ | ❌ |
| Offline/local | ✅ (Ollama) | ❌ | ❌ | N/A |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome — especially:
- New LLM providers
- Better scraping (Playwright support, LinkedIn, news feeds)
- Prompt improvements (with A/B evidence)
- Export formats (JSON, Airtable, Notion)

---

## License

MIT © [Ahmad317-Engineer](https://github.com/Ahmad317-Engineer)
