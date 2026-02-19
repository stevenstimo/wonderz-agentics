"""Circuit Breaker — protects worker from cascading failures.

When too many consecutive failures occur the breaker *opens* and
rejects new work until the TTL expires or an admin resets it.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Redis-backed circuit breaker for worker protection."""

    def __init__(self, redis_client, failure_threshold: int = 5, ttl_seconds: int = 600):
        self.redis = redis_client
        self.failure_threshold = failure_threshold
        self.ttl_seconds = ttl_seconds
        self.key = "circuit_breaker:worker"

    def record_failure(self) -> int:
        """Record a failure.  Returns current failure count."""
        try:
            count = self.redis.incr(self.key)
            self.redis.expire(self.key, self.ttl_seconds)
            if count >= self.failure_threshold:
                logger.critical(
                    "Circuit breaker OPEN after %d failures (threshold=%d)",
                    count, self.failure_threshold,
                )
            return count
        except Exception as e:
            logger.error("CircuitBreaker.record_failure failed: %s", e)
            return 0

    def record_success(self):
        """Reset on success."""
        try:
            self.redis.delete(self.key)
        except Exception as e:
            logger.error("CircuitBreaker.record_success failed: %s", e)

    def is_open(self) -> bool:
        """True when too many recent failures."""
        try:
            failures = int(self.redis.get(self.key) or 0)
            return failures >= self.failure_threshold
        except Exception as e:
            logger.error("CircuitBreaker.is_open failed: %s", e)
            return False  # fail-closed = allow work

    def reset(self):
        """Manual admin reset."""
        try:
            self.redis.delete(self.key)
            logger.info("Circuit breaker manually reset")
        except Exception as e:
            logger.error("CircuitBreaker.reset failed: %s", e)

    def status(self) -> dict:
        """Return current state for API/dashboard."""
        try:
            failures = int(self.redis.get(self.key) or 0)
            return {
                "state": "open" if failures >= self.failure_threshold else "closed",
                "failures": failures,
                "threshold": self.failure_threshold,
                "ttl_seconds": self.ttl_seconds,
            }
        except Exception:
            return {"state": "unknown", "failures": 0, "threshold": self.failure_threshold}
