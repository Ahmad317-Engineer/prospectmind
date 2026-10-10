"""
Orchestration pipeline: CSV in → scrape → personalize → CSV out.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
from pathlib import Path
from typing import AsyncIterator, List, Optional

from .models import CompanyContext, PersonalizationResult, Prospect, RunConfig
from .personalizer import personalize_prospect
from .providers.base import BaseLLMProvider
from .scraper import scrape_company

logger = logging.getLogger(__name__)


def load_prospects_from_csv(path: Path) -> List[Prospect]:
    """
    Load prospects from a CSV file.

    Required columns: first_name, last_name, title, company
    Optional columns: domain, email, linkedin_url, notes
    """
    prospects = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no headers")

        # Normalize headers
        headers = [h.strip().lower().replace(" ", "_") for h in reader.fieldnames]

        required = {"first_name", "last_name", "title", "company"}
        missing = required - set(headers)
        if missing:
            raise ValueError(
                f"CSV missing required columns: {missing}. "
                f"Got: {headers}"
            )

        for i, raw_row in enumerate(reader, start=2):
            row = {h: v.strip() for h, v in zip(headers, raw_row.values())}
            try:
                prospect = Prospect(
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    title=row["title"],
                    company=row["company"],
                    domain=row.get("domain") or None,
                    email=row.get("email") or None,
                    linkedin_url=row.get("linkedin_url") or None,
                    notes=row.get("notes") or None,
                )
                prospects.append(prospect)
            except Exception as e:
                logger.warning(f"Row {i}: Skipping invalid prospect: {e}")

    return prospects


def results_to_csv(results: List[PersonalizationResult]) -> str:
    """Serialize results to CSV string."""
    if not results:
        return ""

    fieldnames = list(results[0].to_csv_row().keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for r in results:
        writer.writerow(r.to_csv_row())
    return output.getvalue()


def _make_provider(config: RunConfig) -> BaseLLMProvider:
    """Factory: instantiate the right LLM provider from config."""
    from .models import LLMProvider
    from .providers.anthropic_provider import AnthropicProvider
    from .providers.ollama_provider import OllamaProvider
    from .providers.openai_provider import OpenAIProvider

    model = config.default_model()
    if config.provider == LLMProvider.OPENAI:
        return OpenAIProvider(api_key=config.api_key, model=model)
    elif config.provider == LLMProvider.ANTHROPIC:
        return AnthropicProvider(api_key=config.api_key, model=model)
    elif config.provider == LLMProvider.OLLAMA:
        return OllamaProvider(
            model=model,
            base_url=config.ollama_base_url,
        )
    else:
        raise ValueError(f"Unknown provider: {config.provider}")


async def _process_one(
    prospect: Prospect,
    provider: BaseLLMProvider,
    config: RunConfig,
    semaphore: asyncio.Semaphore,
) -> PersonalizationResult:
    async with semaphore:
        context: Optional[CompanyContext] = None

        if not config.skip_scraping and prospect.domain:
            try:
                context = await scrape_company(
                    domain=prospect.domain,
                    company_name=prospect.company,
                    timeout=config.timeout_seconds,
                )
            except Exception as e:
                logger.warning(f"Scraping failed for {prospect.domain}: {e}")

        if config.dry_run:
            return PersonalizationResult(
                prospect=prospect,
                company_context=context,
                subject_lines=["[DRY RUN — no LLM called]"],
                openers=["[DRY RUN — no LLM called]"],
                value_prop="[DRY RUN]",
                personalization_score=0,
            )

        return await personalize_prospect(
            prospect=prospect,
            context=context,
            provider=provider,
            config=config,
        )


async def run_pipeline(
    prospects: List[Prospect],
    config: RunConfig,
) -> AsyncIterator[PersonalizationResult]:
    """
    Run the full pipeline: scrape + personalize for every prospect.

    Yields results as they complete (not necessarily in input order).
    """
    provider = _make_provider(config)
    semaphore = asyncio.Semaphore(config.concurrency)

    tasks = [
        asyncio.create_task(
            _process_one(prospect, provider, config, semaphore)
        )
        for prospect in prospects
    ]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        yield result
