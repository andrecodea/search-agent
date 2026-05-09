import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with a standard format and a stdout handler.

    Uses `force=True` to replace any handlers already registered by earlier
    calls or third-party libraries (e.g. uvicorn).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
