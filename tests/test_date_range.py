"""
Tests for _compute_date_range and NewsResponse source/date invariants.

All tests use a fixed UTC reference so results are deterministic:
  2026-05-09 02:00:00 UTC  =  2026-05-08 23:00 BRT  =  2026-05-09 11:00 JST
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.agent import _compute_date_range
from app.schemas import NewsResponse

_UTC_NOW = datetime(2026, 5, 9, 2, 0, 0, tzinfo=UTC)


# ── Date range — UTC offsets ──────────────────────────────────────────────────

def test_utc_range_is_correct() -> None:
    start, end, _ = _compute_date_range(0, now=_UTC_NOW)
    assert start == "2026-05-07"
    assert end == "2026-05-09"


def test_brt_range_is_correct() -> None:
    """Brazil (UTC-3): 02:00 UTC = 23:00 local on May 8 — end date must be May 8."""
    start, end, _ = _compute_date_range(-180, now=_UTC_NOW)
    assert start == "2026-05-06"
    assert end == "2026-05-08"


def test_jst_range_is_correct() -> None:
    """Japan (UTC+9): 02:00 UTC = 11:00 local on May 9."""
    start, end, _ = _compute_date_range(540, now=_UTC_NOW)
    assert start == "2026-05-07"
    assert end == "2026-05-09"


def test_ist_range_is_correct() -> None:
    """India (UTC+5:30 = +330 min): 02:00 UTC = 07:30 local on May 9."""
    start, end, _ = _compute_date_range(330, now=_UTC_NOW)
    assert start == "2026-05-07"
    assert end == "2026-05-09"


def test_nzst_range_is_correct() -> None:
    """New Zealand (UTC+12): 02:00 UTC = 14:00 local on May 9."""
    start, end, _ = _compute_date_range(720, now=_UTC_NOW)
    assert start == "2026-05-07"
    assert end == "2026-05-09"


def test_midday_utc_range() -> None:
    """Midday UTC: both UTC and BRT should agree on the same end date."""
    midday_utc = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
    start_utc, end_utc, _ = _compute_date_range(0, now=midday_utc)
    start_brt, end_brt, _ = _compute_date_range(-180, now=midday_utc)
    assert end_utc == end_brt == "2026-05-09"
    assert start_utc == start_brt == "2026-05-07"


# ── Date range — structural invariants ───────────────────────────────────────

@pytest.mark.parametrize("offset", [-720, -180, 0, 330, 540, 840])
def test_range_is_always_exactly_two_days(offset: int) -> None:
    start, end, _ = _compute_date_range(offset, now=_UTC_NOW)
    delta = date.fromisoformat(end) - date.fromisoformat(start)
    assert delta == timedelta(days=2)


@pytest.mark.parametrize("offset", [-720, -180, 0, 330, 540, 840])
def test_start_is_before_end(offset: int) -> None:
    start, end, _ = _compute_date_range(offset, now=_UTC_NOW)
    assert date.fromisoformat(start) < date.fromisoformat(end)


@pytest.mark.parametrize("offset", [-720, -180, 0, 330, 540, 840])
def test_now_local_is_within_range(offset: int) -> None:
    start, end, now_local = _compute_date_range(offset, now=_UTC_NOW)
    assert date.fromisoformat(start) <= now_local.date() <= date.fromisoformat(end)


_VALID_SUMMARY = "Important news summary in plain English."

# ── NewsResponse — source invariants ─────────────────────────────────────────

def test_response_accepts_up_to_five_sources() -> None:
    response = NewsResponse(
        summary=_VALID_SUMMARY,
        sources=[f"https://example.com/article-{i}" for i in range(5)],
    )
    assert len(response.sources) == 5


def test_response_rejects_six_sources() -> None:
    with pytest.raises(Exception):
        NewsResponse(
            summary=_VALID_SUMMARY,
            sources=[f"https://example.com/article-{i}" for i in range(6)],
        )


def test_response_rejects_http_source() -> None:
    with pytest.raises(Exception):
        NewsResponse(
            summary=_VALID_SUMMARY,
            sources=["http://example.com/article"],
        )


def test_response_rejects_empty_summary() -> None:
    with pytest.raises(Exception):
        NewsResponse(summary="", sources=["https://example.com"])


def test_response_accepts_one_source() -> None:
    response = NewsResponse(
        summary=_VALID_SUMMARY,
        sources=["https://example.com/article"],
    )
    assert len(response.sources) == 1


def test_response_accepts_zero_sources() -> None:
    response = NewsResponse(summary=_VALID_SUMMARY, sources=[])
    assert response.sources == []


