"""Tests for the personalization engine."""

import json
import pytest

from prospectmind.personalizer import (
    _build_context_block,
    _parse_llm_json,
    _score_personalization,
)
from prospectmind.models import CompanyContext, PersonalizationResult, Prospect


class TestParserLLMJson:
    def test_parses_clean_json(self):
        raw = json.dumps({
            "subject_lines": ["A", "B", "C"],
            "openers": ["X", "Y", "Z"],
            "value_prop": "Test value.",
        })
        result = _parse_llm_json(raw)
        assert result is not None
        assert result["subject_lines"] == ["A", "B", "C"]

    def test_handles_markdown_fence(self):
        raw = "```json\n{\"subject_lines\": [\"A\"], \"openers\": [\"X\"], \"value_prop\": \"V\"}\n```"
        result = _parse_llm_json(raw)
        assert result is not None
        assert result["subject_lines"] == ["A"]

    def test_handles_preamble_text(self):
        raw = "Here is the JSON:\n{\"subject_lines\": [\"S\"], \"openers\": [\"O\"], \"value_prop\": \"P\"}"
        result = _parse_llm_json(raw)
        assert result is not None

    def test_returns_none_for_invalid_json(self):
        result = _parse_llm_json("This is just plain text with no JSON.")
        assert result is None

    def test_returns_none_for_empty(self):
        result = _parse_llm_json("")
        assert result is None


class TestBuildContextBlock:
    def test_returns_placeholder_when_no_context(self):
        block = _build_context_block(None)
        assert "No company context" in block

    def test_includes_tagline(self, sample_context):
        block = _build_context_block(sample_context)
        assert "The Future of Industrial Automation" in block

    def test_includes_hiring_signals(self, sample_context):
        block = _build_context_block(sample_context)
        assert "Senior Backend Engineer" in block

    def test_includes_tech_hints(self, sample_context):
        block = _build_context_block(sample_context)
        assert "React" in block

    def test_empty_context_placeholder(self):
        ctx = CompanyContext(domain="x.com", company_name="X")
        block = _build_context_block(ctx)
        assert "no extractable context" in block.lower()


class TestScorePersonalization:
    def test_no_context_returns_low_score(self):
        score = _score_personalization(None, {"openers": ["Generic opener."]})
        assert score == 10

    def test_full_context_returns_high_score(self, sample_context):
        result_json = {
            "openers": [
                "I saw Acme Corp is hiring backend engineers — that usually means rapid product velocity.",
            ]
        }
        score = _score_personalization(sample_context, result_json)
        assert score > 30

    def test_score_bounded_at_100(self, sample_context):
        result_json = {
            "openers": ["Acme Corp automation platform very specific opener"]
        }
        score = _score_personalization(sample_context, result_json)
        assert 0 <= score <= 100


class TestPersonalizationResult:
    def test_error_result(self, sample_prospect):
        result = PersonalizationResult(
            prospect=sample_prospect,
            error="LLM timeout",
        )
        assert result.error == "LLM timeout"
        assert result.personalization_score == 0
        assert result.subject_lines == []

    def test_successful_result(self, sample_prospect, sample_context):
        result = PersonalizationResult(
            prospect=sample_prospect,
            company_context=sample_context,
            subject_lines=["Quick Q about Acme's backend scaling", "Saw you're hiring 3 SREs", "Automation + AI → "],
            openers=["Noticed Acme is scaling its engineering team fast — that usually means tooling debt.", "Love the automation angle on your homepage.", "Your DevOps hiring caught my eye."],
            value_prop="Help Acme's eng team ship 40% faster.",
            personalization_score=82,
        )
        assert len(result.subject_lines) == 3
        assert result.personalization_score == 82
        row = result.to_csv_row()
        assert "Quick Q" in row["subject_line_1"]
