import logging

from app.logging_config import configure_logging


def test_configure_logging_sets_debug_level() -> None:
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_sets_warning_level() -> None:
    configure_logging("WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_defaults_to_info() -> None:
    configure_logging()
    assert logging.getLogger().level == logging.INFO
