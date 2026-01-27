"""Retry utilities with exponential backoff for API clients."""

import asyncio
import random
from collections.abc import Awaitable, Callable

import httpx
import structlog

logger = structlog.get_logger()

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2.0
JITTER_FACTOR = 0.5  # Add up to 50% random jitter

# Random delay configuration for rate limiting between paginated requests
MIN_DELAY_SECONDS = 0.5
MAX_DELAY_SECONDS = 2.0


def calculate_backoff(attempt: int) -> float:
    """Calculate backoff delay with exponential increase and jitter."""
    backoff = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER**attempt)
    backoff = min(backoff, MAX_BACKOFF_SECONDS)
    # Add jitter: random value between 0 and JITTER_FACTOR * backoff
    jitter = random.uniform(0, JITTER_FACTOR * backoff)
    return backoff + jitter


def is_retryable_error(exc: Exception) -> bool:
    """Determine if an error is retryable."""
    # Retry on network/connection errors
    if isinstance(exc, httpx.TransportError | httpx.TimeoutException):
        return True
    # Retry on 5xx server errors
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


async def with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    operation_name: str = "request",
    max_retries: int = MAX_RETRIES,
) -> T:
    """
    Execute an async operation with retry and exponential backoff.

    Args:
        operation: The async callable to execute
        operation_name: Name for logging purposes
        max_retries: Maximum number of retry attempts

    Returns:
        The result of the operation

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as exc:
            last_exception = exc
            if not is_retryable_error(exc):
                raise

            backoff = calculate_backoff(attempt)
            logger.warning(
                "Retryable error occurred, backing off",
                operation=operation_name,
                attempt=attempt + 1,
                max_retries=max_retries,
                backoff_seconds=round(backoff, 2),
                error=str(exc),
            )
            await asyncio.sleep(backoff)

    # If we've exhausted all retries, raise the last exception
    assert last_exception is not None
    raise last_exception


async def random_delay() -> None:
    """
    Add a random delay between API requests to avoid overwhelming the API.

    This should be called between paginated requests or when making
    multiple requests in succession.
    """
    delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
    await asyncio.sleep(delay)
