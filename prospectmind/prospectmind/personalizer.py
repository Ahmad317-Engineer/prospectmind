"""
Core personalization engine.

Takes a Prospect + CompanyContext and calls the LLM to generate
personalized subject lines, openers, and value prop framing.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Tuple

from .models import CompanyContext, PersonalizationResult, Prospect, RunConfig
from .providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert B2B sales copywriter and personalization specialist.
Your job is to generate hyper-personalized cold email components that feel genuinely researched,
not templated. You write like a sharp human who actually read the company's website and understands
their business — not like an AI filling slots.

Rules:
- Be specific. Generic praise ("Congrats on your growth!") is BANNED.
- Reference real signals from the context provided.
- Keep subject lines under 60 characters.
- Keep openers under 2 sentences (max 40 words each).
- Do NOT mention that you "noticed" or "came across" their company — too salesy.
- Output ONLY valid JSON. No markdown, no preamble."""

PERSONALIZATION_PROMPT_TEMPLATE = """Generate personalized cold email components for this B2B prospect.

PROSPECT:
- Name: {full_name}
- Title: {title}
- Company: {company}

COMPANY CONTEXT:
{context_block}

{product_block}

Generate exactly this JSON (no other text):
{{
  "subject_lines": ["<line1>", "<line2>", "<line3>"],
  "openers": ["<opener1>", "<opener2>", "<opener3>"],
  "value_prop": "<one sentence tailored value proposition for this specific prospect>"
}}

Each opener should reference a DIFFERENT signal from the context.
Make subject lines A/B testable (vary angle: curiosity, benefit, question).
"""

FALLBACK_PROMPT_TEMPLATE = """Generate personalized cold email components for:

Name: {full_name}, {title} at {company}.

{product_block}

Output ONLY this JSON:
{{
  "subject_lines": ["<line1>", "<line2>", "<line3>"],
  "openers": ["<opener1>", "<opener2>", "<opener3>"],
  "value_prop": "<tailored value proposition>"
}}"""


def _build_context_block(ctx: Optional[CompanyContext]) -> str:
    if ctx is None:
        return "No company context available."

    parts = []
    if ctx.tagline:
        parts.append(f"Page title: {ctx.tagline}")
    if ctx.description:
        parts.append(f"Meta description: {ctx.description}")
    if ctx.hiring_signals:
        parts.append("Hiring for: " + ", ".join(ctx.hiring_signals[:5]))
    if ctx.tech_stack_hints:
        parts.append("Tech stack signals: " + ", ".join(ctx.tech_stack_hints[:6]))
    if ctx.raw_homepage_snippet:
        snippet = ctx.raw_homepage_snippet[:1500]
        parts.append(f"Homepage excerpt: {snippet}")

    return "\n".join(parts) if parts else "Domain found but no extractable context."


def _build_product_block(config: RunConfig) -> str:
    if not config.your_product and not config.your_value_prop:
        return ""
    lines = ["YOUR PRODUCT (what you're selling):"]
    if config.your_product:
        lines.append(f"Product: {config.your_product}")
    if config.your_value_prop:
        lines.append(f"Value prop: {config.your_value_prop}")
    return "\n".join(lines)


def _score_personalization(ctx: Optional[CompanyContext], result_json: dict) -> int:
    """Heuristic: how personalized is the output, 0–100."""
    if ctx is None:
        return 10  # generic fallback
    score = 0
    if ctx.description:
        score += 20
    if ctx.hiring_signals:
        score += 20
    if ctx.tech_stack_hints:
        score += 15
    if ctx.raw_homepage_snippet and len(ctx.raw_homepage_snippet) > 200:
        score += 15
    # Check if openers reference any company-specific term
    company_words = set(ctx.company_name.lower().split())
    if ctx.tagline:
        company_words.update(ctx.tagline.lower().split()[:5])
    openers_text = " ".join(result_json.get("openers", [])).lower()
    if any(w in openers_text for w in company_words if len(w) > 4):
        score += 30
    return min(score, 100)


def _parse_llm_json(raw: str) -> Optional[dict]:
    """Robustly parse JSON from LLM output, handling markdown fences."""
    raw = raw.strip()
    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    # Find first { ... } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


async def personalize_prospect(
    prospect: Prospect,
    context: Optional[CompanyContext],
    provider: BaseLLMProvider,
    config: RunConfig,
) -> PersonalizationResult:
    """
    Generate personalized outreach content for a single prospect.
    """
    context_block = _build_context_block(context)
    product_block = _build_product_block(config)

    has_context = context is not None and context.raw_homepage_snippet

    if has_context:
        user_prompt = PERSONALIZATION_PROMPT_TEMPLATE.format(
            full_name=prospect.full_name,
            title=prospect.title,
            company=prospect.company,
            context_block=context_block,
            product_block=product_block,
        )
    else:
        user_prompt = FALLBACK_PROMPT_TEMPLATE.format(
            full_name=prospect.full_name,
            title=prospect.title,
            company=prospect.company,
            product_block=product_block,
        )

    last_error = None
    for attempt in range(config.max_retries):
        try:
            response = await provider.complete(SYSTEM_PROMPT, user_prompt)
            parsed = _parse_llm_json(response.content)

            if parsed is None:
                raise ValueError(f"Could not parse JSON from LLM output: {response.content[:200]}")

            subject_lines: List[str] = parsed.get("subject_lines", [])
            openers: List[str] = parsed.get("openers", [])
            value_prop: Optional[str] = parsed.get("value_prop")

            # Validate we got something
            if not subject_lines or not openers:
                raise ValueError("LLM returned empty subject_lines or openers")

            score = _score_personalization(context, parsed)

            return PersonalizationResult(
                prospect=prospect,
                company_context=context,
                subject_lines=subject_lines[:3],
                openers=openers[:3],
                value_prop=value_prop,
                personalization_score=score,
            )

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt + 1}/{config.max_retries} failed for {prospect.full_name}: {e}")

    return PersonalizationResult(
        prospect=prospect,
        company_context=context,
        error=f"Failed after {config.max_retries} attempts: {last_error}",
        personalization_score=0,
    )
