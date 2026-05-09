from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(StrEnum):
    """Supported news categories, aligned with Tavily Search topic values."""

    tech = "tech"
    economics = "economics"
    politics = "politics"


class NewsRequest(BaseModel):
    """Request body for the POST /news endpoint."""

    topic: str | None = None
    category: Category | None = None
    utc_offset_minutes: int = Field(default=0, ge=-720, le=840)


class NewsResponse(BaseModel):
    """Structured response returned by the newspaper agent."""

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: Annotated[str, Field(min_length=1)]
    sources: Annotated[list[str], Field(max_length=5)]

    @field_validator("summary")
    @classmethod
    def summary_must_have_paragraphs(cls, summary: str) -> str:
        """Reject summaries that lack paragraph breaks — plain blobs are not valid markdown."""
        if "\n\n" not in summary:
            raise ValueError("summary must contain at least two paragraphs separated by a blank line.")
        return summary

    @field_validator("sources")
    @classmethod
    def sources_must_be_https(cls, sources: list[str]) -> list[str]:
        """Reject any source that does not use an HTTPS URL."""
        for source in sources:
            if not source.startswith("https://"):
                raise ValueError("All sources must be https links.")
        return sources
