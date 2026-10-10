# Contributing to ProspectMind

Thank you for your interest in contributing! ProspectMind is open source and welcomes PRs of all sizes.

## Quick Start

```bash
# Clone and install in dev mode
git clone https://github.com/Ahmad317-Engineer/prospectmind.git
cd prospectmind
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Try it out
prospectmind sample
prospectmind run prospects_sample.csv --dry-run
```

## How to Contribute

### Reporting Bugs

Open an [issue](https://github.com/Ahmad317-Engineer/prospectmind/issues) with:
- ProspectMind version (`prospectmind --version`)
- Python version
- Steps to reproduce
- Expected vs actual behavior

### Adding a New LLM Provider

1. Create `prospectmind/providers/<name>_provider.py`
2. Subclass `BaseLLMProvider` and implement `complete()` and `name`
3. Register it in `prospectmind/providers/__init__.py`
4. Add it to `LLMProvider` enum in `models.py`
5. Wire it in `pipeline.py`'s `_make_provider()`
6. Add tests in `tests/`

### Improving Scraping

The `scraper.py` module is the most impactful place to contribute. Ideas:
- Add support for LinkedIn public pages
- Improve job-role extraction with better regex/NLP
- Add RSS news feed detection and scraping
- Support Playwright for JS-rendered pages

### Improving Prompts

Prompt engineering lives in `personalizer.py`. The prompts are deliberately clean and documented — improve them with A/B test evidence. Please include before/after examples in your PR.

## Code Style

- Python 3.10+, type-annotated
- `ruff` for linting (`ruff check prospectmind/ tests/`)
- `pytest` for tests — aim for >80% coverage on new code
- Keep functions small and single-purpose

## Pull Request Checklist

- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Linter passes (`ruff check prospectmind/ tests/`)
- [ ] New features have tests
- [ ] README updated if user-facing behavior changed

## License

By contributing you agree your work is licensed under MIT.
