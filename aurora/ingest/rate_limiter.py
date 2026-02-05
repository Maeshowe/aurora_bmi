"""
Token bucket rate limiter for API requests.

Implements a leaky bucket algorithm to control request rates.
"""

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucketLimiter:
    """
    Token bucket rate limiter.

    Tokens are added at a fixed rate up to a maximum (burst) capacity.
    Each request consumes one token. If no tokens are available,
    the request waits until a token becomes available.

    Args:
        rate_per_second: Token refill rate (tokens/second)
        burst_size: Maximum token capacity
    """

    rate_per_second: float
    burst_size: int
    _tokens: float = field(init=False)
    _last_update: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        """Initialize token bucket."""
        self._tokens = float(self.burst_size)
        self._last_update = time.monotonic()

    @classmethod
    def from_rpm(cls, requests_per_minute: int, burst_size: int = 5) -> "TokenBucketLimiter":
        """
        Create limiter from requests-per-minute.

        Args:
            requests_per_minute: Maximum requests per minute
            burst_size: Maximum burst capacity

        Returns:
            Configured TokenBucketLimiter
        """
        rate_per_second = requests_per_minute / 60.0
        return cls(rate_per_second=rate_per_second, burst_size=burst_size)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(
            self.burst_size,
            self._tokens + elapsed * self.rate_per_second,
        )
        self._last_update = now

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default 1)
        """
        async with self._lock:
            while True:
                self._refill()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                # Calculate wait time for sufficient tokens
                deficit = tokens - self._tokens
                wait_time = deficit / self.rate_per_second
                await asyncio.sleep(wait_time)

    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire (default 1)

        Returns:
            True if tokens acquired, False otherwise
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True

            return False

    @property
    def available_tokens(self) -> float:
        """Current available tokens (approximate)."""
        self._refill()
        return self._tokens
