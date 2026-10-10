"""Data models for ProspectMind."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class Prospect(BaseModel):
    """A single B2B prospect to personalize outreach for."""

    first_name: str = Field(..., description="Prospect's first name")
    last_name: str = Field(..., description="Prospect's last name")
    title: str = Field(..., description="Prospect's job title")
    company: str = Field(..., description="Company name")
    domain: Optional[str] = Field(None, description="Company domain (e.g. acme.com)")
    email: Optional[str] = Field(None, description="Prospect's email address")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    notes: Optional[str] = Field(None, description="Any additional context")

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = str(v).strip().lower()
        for prefix in ("https://", "http://", "www."):
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v.rstrip("/")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class CompanyContext(BaseModel):
    """Live-scraped context about a company."""

    domain: str
    company_name: str
    tagline: Optional[str] = None
    description: Optional[str] = None
    recent_news: List[str] = Field(default_factory=list)
    hiring_signals: List[str] = Field(default_factory=list)
    products_services: List[str] = Field(default_factory=list)
    tech_stack_hints: List[str] = Field(default_factory=list)
    raw_homepage_snippet: Optional[str] = None


class PersonalizationResult(BaseModel):
    """Generated personalization for a single prospect."""

    prospect: Prospect
    company_context: Optional[CompanyContext] = None
    subject_lines: List[str] = Field(default_factory=list, max_length=3)
    openers: List[str] = Field(default_factory=list, max_length=3)
    value_prop: Optional[str] = None
    personalization_score: int = Field(
        0,
        ge=0,
        le=100,
        description="0=generic, 100=highly specific (based on signals found)",
    )
    error: Optional[str] = None

    def to_csv_row(self) -> dict:
        return {
            "first_name": self.prospect.first_name,
            "last_name": self.prospect.last_name,
            "title": self.prospect.title,
            "company": self.prospect.company,
            "domain": self.prospect.domain or "",
            "email": self.prospect.email or "",
            "subject_line_1": self.subject_lines[0] if len(self.subject_lines) > 0 else "",
            "subject_line_2": self.subject_lines[1] if len(self.subject_lines) > 1 else "",
            "subject_line_3": self.subject_lines[2] if len(self.subject_lines) > 2 else "",
            "opener_1": self.openers[0] if len(self.openers) > 0 else "",
            "opener_2": self.openers[1] if len(self.openers) > 1 else "",
            "opener_3": self.openers[2] if len(self.openers) > 2 else "",
            "value_prop": self.value_prop or "",
            "personalization_score": self.personalization_score,
            "error": self.error or "",
        }


class RunConfig(BaseModel):
    """Runtime configuration for a personalization run."""

    provider: LLMProvider = LLMProvider.OPENAI
    model: Optional[str] = None  # auto-selected if None
    api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    concurrency: int = Field(3, ge=1, le=20)
    max_retries: int = Field(3, ge=0, le=10)
    timeout_seconds: int = Field(30, ge=5, le=120)
    dry_run: bool = False
    skip_scraping: bool = False
    your_product: Optional[str] = None
    your_value_prop: Optional[str] = None

    def default_model(self) -> str:
        defaults = {
            LLMProvider.OPENAI: "gpt-4o-mini",
            LLMProvider.ANTHROPIC: "claude-3-5-haiku-20241022",
            LLMProvider.OLLAMA: "llama3.1",
        }
        return self.model or defaults[self.provider]
