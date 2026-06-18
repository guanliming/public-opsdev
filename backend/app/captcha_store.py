import os
import time
from threading import Lock
from typing import Optional


CAPTCHA_TTL_SECONDS = 300


def is_debug_bypass() -> bool:
    return os.environ.get("OPSDEV_CAPTCHA_DEBUG", "") == "1"


class _Entry:
    __slots__ = ("code", "expires_at")

    def __init__(self, code: str, expires_at: float):
        self.code = code
        self.expires_at = expires_at


class CaptchaStore:
    def __init__(self, ttl: int = CAPTCHA_TTL_SECONDS):
        self.ttl = ttl
        self._lock = Lock()
        self._store: dict[str, _Entry] = {}

    def put(self, token: str, code: str) -> None:
        with self._lock:
            self._purge_locked()
            self._store[token] = _Entry(code, time.time() + self.ttl)

    def consume(self, token: str, code: str) -> bool:
        if not token or not code:
            return False
        with self._lock:
            self._purge_locked()
            entry = self._store.pop(token, None)
        if entry is None:
            return False
        if entry.expires_at < time.time():
            return False
        return entry.code == code

    def peek(self, token: str) -> Optional[str]:
        if not token:
            return None
        with self._lock:
            self._purge_locked()
            entry = self._store.get(token)
        return entry.code if entry else None

    def _purge_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if v.expires_at < now]
        for k in expired:
            self._store.pop(k, None)


captcha_store = CaptchaStore()
