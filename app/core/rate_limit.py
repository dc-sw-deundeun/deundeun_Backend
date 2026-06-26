import time
from dataclasses import dataclass
from threading import Lock

from app.core.exceptions import AppException


class RateLimitExceededException(AppException):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            status_code=429,
            message="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
            error_code="RATE_LIMIT_EXCEEDED",
        )
        self.retry_after_seconds = retry_after_seconds


@dataclass
class _Bucket:
    count: int
    reset_at: float


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        if limit <= 0:
            return

        now = time.monotonic()
        with self._lock:
            self._cleanup(now)
            bucket = self._buckets.get(key)
            if bucket is None or bucket.reset_at <= now:
                self._buckets[key] = _Bucket(count=1, reset_at=now + window_seconds)
                return

            if bucket.count >= limit:
                retry_after = max(1, int(bucket.reset_at - now))
                raise RateLimitExceededException(retry_after)

            bucket.count += 1

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def _cleanup(self, now: float) -> None:
        expired_keys = [key for key, bucket in self._buckets.items() if bucket.reset_at <= now]
        for key in expired_keys:
            self._buckets.pop(key, None)


rate_limiter = FixedWindowRateLimiter()
