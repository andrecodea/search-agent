import pytest
from pydantic import ValidationError

from app.schemas import Category, NewsRequest, NewsResponse


def test_news_request_accepts_supported_category() -> None:
    request = NewsRequest(category=Category.tech)

    assert request.category is Category.tech


def test_news_request_allows_missing_category() -> None:
    request = NewsRequest()

    assert request.category is None


def test_news_request_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        NewsRequest(category="sports")


def test_news_response_limits_sources_to_five_https_links() -> None:
    response = NewsResponse(
        summary="First paragraph.\n\nSecond paragraph.",
        sources=[
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
            "https://example.com/4",
            "https://example.com/5",
        ],
    )

    assert len(response.sources) == 5


def test_news_response_rejects_more_than_five_sources() -> None:
    with pytest.raises(ValidationError):
        NewsResponse(
            summary="First paragraph.\n\nSecond paragraph.",
            sources=[
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3",
                "https://example.com/4",
                "https://example.com/5",
                "https://example.com/6",
            ],
        )


def test_news_response_rejects_non_https_sources() -> None:
    with pytest.raises(ValidationError):
        NewsResponse(summary="First paragraph.\n\nSecond paragraph.", sources=["http://example.com"])
