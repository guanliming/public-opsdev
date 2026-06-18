from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginAttempt, User


MAX_FAILED_ATTEMPTS = 5
FAIL_WINDOW_MINUTES = 30
LOCK_DURATION_MINUTES = 30


@dataclass
class LoginLockStatus:
    locked: bool
    failed_count: int
    locked_until: Optional[datetime]
    remaining_seconds: int


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_lock_status(record: Optional[LoginAttempt]) -> LoginLockStatus:
    if record is None:
        return LoginLockStatus(False, 0, None, 0)
    locked_until = record.locked_until
    now = _now_utc()
    if locked_until and locked_until.tzinfo is not None:
        locked_until = locked_until.replace(tzinfo=None)
    if locked_until and locked_until > now:
        remaining = int((locked_until - now).total_seconds())
        return LoginLockStatus(True, record.failed_count, locked_until, max(remaining, 0))
    return LoginLockStatus(False, record.failed_count, None, 0)


def is_window_expired(record: LoginAttempt) -> bool:
    if record.last_failed_at is None:
        return True
    last = record.last_failed_at
    if last.tzinfo is not None:
        last = last.replace(tzinfo=None)
    return _now_utc() - last > timedelta(minutes=FAIL_WINDOW_MINUTES)


async def get_attempt(db: AsyncSession, username: str) -> Optional[LoginAttempt]:
    result = await db.execute(select(LoginAttempt).where(LoginAttempt.username == username))
    return result.scalar_one_or_none()


async def get_lock_status(db: AsyncSession, username: str) -> LoginLockStatus:
    record = await get_attempt(db, username)
    if record is None:
        return LoginLockStatus(False, 0, None, 0)
    if is_window_expired(record):
        record.failed_count = 0
        record.locked_until = None
        record.last_failed_at = None
        await db.commit()
        return LoginLockStatus(False, 0, None, 0)
    return build_lock_status(record)


async def reset_attempts(db: AsyncSession, username: str) -> bool:
    record = await get_attempt(db, username)
    if record is None:
        return False
    record.failed_count = 0
    record.locked_until = None
    record.last_failed_at = None
    await db.commit()
    return True


async def register_failure(db: AsyncSession, username: str) -> LoginLockStatus:
    record = await get_attempt(db, username)
    now = _now_utc()
    if record is None:
        record = LoginAttempt(
            username=username,
            failed_count=1,
            last_failed_at=now,
            locked_until=None,
        )
        db.add(record)
    else:
        if is_window_expired(record):
            record.failed_count = 1
            record.locked_until = None
        else:
            record.failed_count = (record.failed_count or 0) + 1
        record.last_failed_at = now
        if record.failed_count >= MAX_FAILED_ATTEMPTS:
            record.locked_until = now + timedelta(minutes=LOCK_DURATION_MINUTES)
    await db.commit()
    await db.refresh(record)
    return build_lock_status(record)


async def clear_attempts(db: AsyncSession, username: str) -> None:
    record = await get_attempt(db, username)
    if record is None:
        return
    if record.failed_count == 0 and record.locked_until is None and record.last_failed_at is None:
        return
    record.failed_count = 0
    record.locked_until = None
    record.last_failed_at = None
    await db.commit()


async def user_exists(db: AsyncSession, username: str) -> bool:
    result = await db.execute(select(User.id).where(User.username == username))
    return result.scalar_one_or_none() is not None

