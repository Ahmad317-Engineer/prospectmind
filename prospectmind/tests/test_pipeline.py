"""Tests for CSV loading and pipeline utilities."""

import csv
import io
import textwrap
from pathlib import Path

import pytest

from prospectmind.pipeline import load_prospects_from_csv, results_to_csv
from prospectmind.models import PersonalizationResult, Prospect


def write_temp_csv(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "prospects.csv"
    f.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return f


class TestLoadProspectsFromCSV:
    def test_loads_required_fields(self, tmp_path):
        f = write_temp_csv(
            tmp_path,
            """
            first_name,last_name,title,company
            Alice,Smith,CEO,TechCo
            Bob,Jones,CTO,StartupX
            """,
        )
        prospects = load_prospects_from_csv(f)
        assert len(prospects) == 2
        assert prospects[0].first_name == "Alice"
        assert prospects[1].company == "StartupX"

    def test_loads_optional_fields(self, tmp_path):
        f = write_temp_csv(
            tmp_path,
            """
            first_name,last_name,title,company,domain,email
            Alice,Smith,CEO,TechCo,techco.com,alice@techco.com
            """,
        )
        prospects = load_prospects_from_csv(f)
        assert prospects[0].domain == "techco.com"
        assert prospects[0].email == "alice@techco.com"

    def test_raises_on_missing_required_columns(self, tmp_path):
        f = write_temp_csv(
            tmp_path,
            """
            first_name,last_name
            Alice,Smith
            """,
        )
        with pytest.raises(ValueError, match="missing required columns"):
            load_prospects_from_csv(f)

    def test_skips_invalid_rows(self, tmp_path):
        # Row with missing company should be skipped
        f = write_temp_csv(
            tmp_path,
            """
            first_name,last_name,title,company
            Alice,Smith,CEO,TechCo
            Bob,,CTO,
            Carol,Davis,VP,GoodCo
            """,
        )
        prospects = load_prospects_from_csv(f)
        # Alice and Carol should load; Bob has empty last_name+company
        names = [p.first_name for p in prospects]
        assert "Alice" in names

    def test_normalizes_column_headers(self, tmp_path):
        f = write_temp_csv(
            tmp_path,
            """
            First Name,Last Name,Title,Company
            Alice,Smith,CEO,TechCo
            """,
        )
        prospects = load_prospects_from_csv(f)
        assert len(prospects) == 1

    def test_empty_csv_returns_empty_list(self, tmp_path):
        f = write_temp_csv(
            tmp_path,
            "first_name,last_name,title,company\n",
        )
        prospects = load_prospects_from_csv(f)
        assert prospects == []


class TestResultsToCSV:
    def test_produces_valid_csv(self):
        p = Prospect(
            first_name="Alice", last_name="Smith", title="CEO", company="TechCo"
        )
        result = PersonalizationResult(
            prospect=p,
            subject_lines=["Subject 1"],
            openers=["Opener 1"],
            value_prop="Value prop.",
            personalization_score=60,
        )
        csv_text = results_to_csv([result])
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["first_name"] == "Alice"
        assert rows[0]["subject_line_1"] == "Subject 1"
        assert rows[0]["personalization_score"] == "60"

    def test_empty_results_returns_empty_string(self):
        assert results_to_csv([]) == ""

    def test_multiple_results(self):
        results = []
        for i in range(5):
            p = Prospect(
                first_name=f"Person{i}",
                last_name="Test",
                title="Manager",
                company=f"Company{i}",
            )
            results.append(PersonalizationResult(prospect=p))

        csv_text = results_to_csv(results)
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert len(rows) == 5
