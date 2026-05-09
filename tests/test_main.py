from pathlib import Path

import pytest

from app.main import save_to_history
from app.schemas import NewsResponse


def test_save_to_history_creates_markdown_file(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="Tech news summary.\n\nSecond paragraph.",
        sources=["https://example.com/article"],
    )

    save_to_history(response, "tech", history_dir=tmp_path)

    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1


def test_save_to_history_file_contains_frontmatter(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="Tech news summary.\n\nSecond paragraph.",
        sources=["https://example.com/article"],
    )

    save_to_history(response, "tech", history_dir=tmp_path)

    content = next(tmp_path.glob("*.md")).read_text()
    assert "category: tech" in content
    assert "timestamp:" in content


def test_save_to_history_file_contains_summary_and_sources(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="Tech news summary.\n\nSecond paragraph.",
        sources=["https://example.com/article"],
    )

    save_to_history(response, "tech", history_dir=tmp_path)

    content = next(tmp_path.glob("*.md")).read_text()
    assert "Tech news summary." in content
    assert "https://example.com/article" in content


def test_save_to_history_uses_general_for_none_category(tmp_path: Path) -> None:
    response = NewsResponse(
        summary="General news.\n\nSecond paragraph.",
        sources=["https://example.com"],
    )

    save_to_history(response, None, history_dir=tmp_path)

    files = list(tmp_path.glob("*.md"))
    assert "general" in files[0].name


def test_save_to_history_creates_directory_if_missing(tmp_path: Path) -> None:
    history_dir = tmp_path / "nested" / "history"
    response = NewsResponse(
        summary="News.\n\nSecond paragraph.",
        sources=["https://example.com"],
    )

    save_to_history(response, "tech", history_dir=history_dir)

    assert history_dir.exists()
    assert len(list(history_dir.glob("*.md"))) == 1
