"""Shared fixtures and helpers for ProspectMind tests."""

import pytest
from prospectmind.models import CompanyContext, Prospect, RunConfig, LLMProvider


@pytest.fixture
def sample_prospect():
    return Prospect(
        first_name="Sarah",
        last_name="Chen",
        title="VP of Engineering",
        company="Acme Corp",
        domain="acme.com",
        email="sarah@acme.com",
    )


@pytest.fixture
def sample_context():
    return CompanyContext(
        domain="acme.com",
        company_name="Acme Corp",
        tagline="Acme Corp | The Future of Industrial Automation",
        description="Acme Corp builds AI-powered automation tools for manufacturing teams.",
        hiring_signals=["Senior Backend Engineer", "Lead DevOps Engineer"],
        tech_stack_hints=["React", "AWS"],
        raw_homepage_snippet="We help manufacturing teams automate repetitive processes with AI.",
    )


@pytest.fixture
def run_config():
    return RunConfig(
        provider=LLMProvider.OPENAI,
        dry_run=True,
        skip_scraping=True,
    )
