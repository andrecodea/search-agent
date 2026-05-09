from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

from app.schemas import NewsResponse
from app.settings import Settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class NewsAgentProtocol(Protocol):
    """Interface for the newspaper agent, enabling dependency injection in tests."""

    async def get_news(self, category: str | None, topic: str | None, utc_offset_minutes: int = 0) -> NewsResponse:
        """Fetch and summarise the latest news for the given category and optional topic."""
        ...


class NewspaperAgent:
    """LangChain agent that searches for recent news via Tavily and returns a structured summary."""

    def __init__(self, settings: Settings) -> None:
        """Build and cache the primary and fallback LLMs from settings."""
        self._settings = settings
        self._system_prompt = _load_system_prompt()
        self._primary_llm = self._build_llm(settings.openrouter_model)
        self._fallback_llm = self._build_llm(settings.openrouter_fallback_model)

    async def get_news(self, category: str | None, topic: str | None, utc_offset_minutes: int = 0) -> NewsResponse:
        """Run the agent for the given category and optional topic, returning a structured news response."""
        tavily_start, tavily_end, now_local = _compute_date_range(utc_offset_minutes)
        earliest_local = now_local - timedelta(days=2)

        if topic and category:
            search_topic = f"{topic} — {category}"
        elif topic:
            search_topic = topic
        elif category:
            search_topic = category
        else:
            search_topic = "general top news"

        agent = self._build_agent(
            start_date=tavily_start,
            end_date=tavily_end,
        )

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Find the latest and most important {search_topic} from the last "
                            f"2 days only. The user's local date and time is "
                            f"{now_local.isoformat()}. Do not use stories published "
                            f"before {earliest_local.date().isoformat()}."
                        ),
                    }
                ]
            }
        )

        structured_response = result.get("structured_response")
        if isinstance(structured_response, NewsResponse):
            return structured_response
        return NewsResponse.model_validate(structured_response)

    def _build_llm(self, model: str) -> ChatOpenAI:
        """Instantiate a ChatOpenAI client pointed at OpenRouter for the given model."""
        return ChatOpenAI(
            model=model,
            api_key=self._settings.openrouter_api_key,
            base_url=self._settings.openrouter_base_url,
            temperature=0.2,
            max_tokens=self._settings.max_tokens,
            max_retries=2,
            model_kwargs={"parallel_tool_calls": True},
            default_headers={
                "HTTP-Referer": "https://alphacorp.ai",
                "X-Title": "AlphaCorp AI Newspaper Delivery Agent",
            },
        )

    def _build_agent(self, start_date: str, end_date: str) -> Runnable:
        """Build the agent graph with a date-bounded Tavily tool and a primary/fallback chain."""
        tools = [
            TavilySearch(
                api_key=self._settings.tavily_api_key,
                topic="news",
                start_date=start_date,
                end_date=end_date,
                search_depth="basic",
                max_results=3,
            )
        ]
        primary = create_agent(
            model=self._primary_llm,
            tools=tools,
            response_format=NewsResponse,
            system_prompt=self._system_prompt,
        )
        fallback = create_agent(
            model=self._fallback_llm,
            tools=tools,
            response_format=NewsResponse,
            system_prompt=self._system_prompt,
        )

        return primary.with_fallbacks([fallback])


def _compute_date_range(
    utc_offset_minutes: int,
    now: datetime | None = None,
) -> tuple[str, str, datetime]:
    """Return (tavily_start, tavily_end, now_local) for the given UTC offset.

    Accepting an optional `now` makes the function deterministic in tests.
    """
    utc_now = now if now is not None else datetime.now(UTC)
    user_tz = timezone(timedelta(minutes=utc_offset_minutes))
    now_local = utc_now.astimezone(user_tz)
    return (
        (now_local - timedelta(days=2)).date().isoformat(),
        now_local.date().isoformat(),
        now_local,
    )


def _load_system_prompt() -> str:
    """Read the agent system prompt from prompts/system.md."""
    with open(PROMPTS_DIR / "system.md", encoding="utf-8") as f:
        return f.read()
