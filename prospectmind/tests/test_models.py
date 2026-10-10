"""Tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from prospectmind.models import (
    CompanyContext,
    LLMProvider,
    PersonalizationResult,
    Prospect,
    RunConfig,
)


class TestProspect:
    def test_basic_creation(self):
        p = Prospect(
            first_name="Alice",
            last_name="Smith",
            title="CEO",
            company="TechCo",
        )
        assert p.full_name == "Alice Smith"
        assert p.domain is None

    def test_domain_normalization(self):
        cases = [
            ("https://acme.com", "acme.com"),
            ("http://www.acme.com/", "acme.com"),
            ("WWW.ACME.COM", "acme.com"),
            ("acme.com", "acme.com"),
        ]
        for raw, expected in cases:
            p = Prospect(
                first_name="X",
                last_name="Y",
                title="Z",
                company="C",
                domain=raw,
            )
            assert p.domain == expected, f"Failed for {raw!r}"

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            Prospect(first_name="Alice")  # missing required fields

    def test_optional_fields_default_to_none(self):
        p = Prospect(
            first_name="Bob",
            last_name="Jones",
            title="CTO",
            company="Startup",
        )
        assert p.email is None
        assert p.linkedin_url is None
        assert p.notes is None


class TestCompanyContext:
    def test_creation(self, sample_context):
        assert sample_context.domain == "acme.com"
        assert len(sample_context.hiring_signals) == 2
        assert "React" in sample_context.tech_stack_hints

    def test_empty_context(self):
        ctx = CompanyContext(domain="example.com", company_name="Example")
        assert ctx.hiring_signals == []
        assert ctx.tech_stack_hints == []
        assert ctx.description is None


class TestPersonalizationResult:
    def test_to_csv_row_complete(self, sample_prospect, sample_context):
        result = PersonalizationResult(
            prospect=sample_prospect,
            company_context=sample_context,
            subject_lines=["Subject A", "Subject B", "Subject C"],
            openers=["Opener 1", "Opener 2", "Opener 3"],
            value_prop="Save 10 hours/week on automation.",
            personalization_score=75,
        )
        row = result.to_csv_row()
        assert row["subject_line_1"] == "Subject A"
        assert row["opener_2"] == "Opener 2"
        assert row["personalization_score"] == 75
        assert row["error"] == ""

    def test_to_csv_row_with_error(self, sample_prospect):
        result = PersonalizationResult(
            prospect=sample_prospect,
            error="API timeout",
        )
        row = result.to_csv_row()
        assert row["error"] == "API timeout"
        assert row["subject_line_1"] == ""

    def test_to_csv_row_partial_lists(self, sample_prospect):
        result = PersonalizationResult(
            prospect=sample_prospect,
            subject_lines=["Only one subject"],
            openers=["Only one opener"],
        )
        row = result.to_csv_row()
        assert row["subject_line_1"] == "Only one subject"
        assert row["subject_line_2"] == ""
        assert row["subject_line_3"] == ""


class TestRunConfig:
    def test_defaults(self):
        config = RunConfig()
        assert config.provider == LLMProvider.OPENAI
        assert config.concurrency == 3
        assert config.dry_run is False

    def test_default_model_openai(self):
        config = RunConfig(provider=LLMProvider.OPENAI)
        assert config.default_model() == "gpt-4o-mini"

    def test_default_model_anthropic(self):
        config = RunConfig(provider=LLMProvider.ANTHROPIC)
        assert config.default_model() == "claude-3-5-haiku-20241022"

    def test_default_model_override(self):
        config = RunConfig(provider=LLMProvider.OPENAI, model="gpt-4o")
        assert config.default_model() == "gpt-4o"

    def test_concurrency_bounds(self):
        with pytest.raises(ValidationError):
            RunConfig(concurrency=0)
        with pytest.raises(ValidationError):
            RunConfig(concurrency=21)
