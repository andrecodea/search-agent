from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, get_news_agent
from app.schemas import NewsResponse


class FakeNewsAgent:
    """Test double for NewspaperAgent — returns a deterministic response without API calls."""

    def __init__(self) -> None:
        self.seen_category: str | None = None
        self.seen_topic: str | None = None

    async def get_news(self, category: str | None, topic: str | None, utc_offset_minutes: int = 0) -> NewsResponse:
        """Return a hardcoded response and record the category and topic received."""
        self.seen_category = category
        self.seen_topic = topic
        return NewsResponse(
            summary="Important technology news in simple English.",
            sources=["https://example.com/article"],
        )


@pytest.fixture
def fake_agent() -> FakeNewsAgent:
    """Reusable FakeNewsAgent instance."""
    return FakeNewsAgent()


@pytest.fixture
async def client(fake_agent: FakeNewsAgent) -> AsyncIterator[AsyncClient]:
    """Async test client with FakeNewsAgent injected and save_to_history patched."""
    app.dependency_overrides[get_news_agent] = lambda: fake_agent
    transport = ASGITransport(app=app)

    with patch("app.main.save_to_history"):
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client

    app.dependency_overrides.clear()


# ── Response shape ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_post_news_returns_summary_and_sources(client: AsyncClient) -> None:
    response = await client.post("/news", json={"category": "tech"})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Important technology news in simple English."
    assert body["sources"] == ["https://example.com/article"]


@pytest.mark.anyio
async def test_post_news_accepts_empty_body_for_general_news(client: AsyncClient) -> None:
    response = await client.post("/news", json={})

    assert response.status_code == 200
    assert "summary" in response.json()
    assert "sources" in response.json()


@pytest.mark.anyio
async def test_post_news_rejects_unknown_category(client: AsyncClient) -> None:
    response = await client.post("/news", json={"category": "sports"})

    assert response.status_code == 422


# ── Search routing — correct topic forwarded to agent ────────────────────────

@pytest.mark.anyio
async def test_tech_category_forwards_tech_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"category": "tech"})

    assert fake_agent.seen_category == "tech"


@pytest.mark.anyio
async def test_economics_category_forwards_economics_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"category": "economics"})

    assert fake_agent.seen_category == "economics"


@pytest.mark.anyio
async def test_politics_category_forwards_politics_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"category": "politics"})

    assert fake_agent.seen_category == "politics"


@pytest.mark.anyio
async def test_no_category_forwards_none_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={})

    assert fake_agent.seen_category is None


@pytest.mark.anyio
async def test_topic_is_forwarded_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"topic": "artificial intelligence"})

    assert fake_agent.seen_topic == "artificial intelligence"


@pytest.mark.anyio
async def test_topic_and_category_are_both_forwarded(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"topic": "inflation", "category": "economics"})

    assert fake_agent.seen_topic == "inflation"
    assert fake_agent.seen_category == "economics"


@pytest.mark.anyio
async def test_no_topic_forwards_none_to_agent(
    client: AsyncClient, fake_agent: FakeNewsAgent
) -> None:
    await client.post("/news", json={"category": "tech"})

    assert fake_agent.seen_topic is None


@pytest.mark.anyio
async def test_dummy_query_returns_valid_response_shape(client: AsyncClient) -> None:
    """Smoke test: any valid request produces the expected JSON keys."""
    response = await client.post("/news", json={"category": "tech"})

    body = response.json()
    assert set(body.keys()) == {"summary", "sources"}
    assert isinstance(body["summary"], str)
    assert isinstance(body["sources"], list)


@pytest.mark.anyio
async def test_general_news_query_returns_valid_response_shape(client: AsyncClient) -> None:
    """Smoke test: a request with no topic produces the expected JSON keys."""
    response = await client.post("/news", json={})

    body = response.json()
    assert set(body.keys()) == {"summary", "sources"}
    assert isinstance(body["summary"], str)
    assert isinstance(body["sources"], list)
