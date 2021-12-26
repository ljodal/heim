import time
from contextlib import contextmanager
from typing import Any, Iterator

import structlog

logger = structlog.get_logger()


@contextmanager
def timed(name: str, **kwargs: Any) -> Iterator[None]:
    t = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - t) * 1000
        logger.info(name, elapsed_ms=elapsed_ms, **kwargs)
