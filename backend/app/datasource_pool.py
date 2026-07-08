from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Tuple

import aiomysql

from app.crypto import decrypt_value
from app.models import DataSource


logger = logging.getLogger(__name__)


def _database_key(ds_id: int, database: Optional[str]) -> Tuple[int, str]:
    return (ds_id, database or "")


class DataSourceConnection:
    def __init__(self, ds: DataSource, database: Optional[str] = None):
        self.ds = ds
        self.database = database
        self._pool: Optional[aiomysql.Pool] = None
        self._lock = asyncio.Lock()

    async def get_pool(self) -> aiomysql.Pool:
        if self._pool is not None:
            return self._pool
        async with self._lock:
            if self._pool is not None:
                return self._pool
            password = decrypt_value(self.ds.password_encrypted)
            self._pool = await aiomysql.create_pool(
                host=self.ds.host,
                port=self.ds.port,
                user=self.ds.username,
                password=password,
                db=self.database or None,
                charset=self.ds.charset or "utf8mb4",
                autocommit=False,
                minsize=0,
                maxsize=5,
                connect_timeout=5,
            )
            return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


class DataSourceManager:
    def __init__(self):
        self._pools: Dict[Tuple[int, str], DataSourceConnection] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, ds: DataSource, database: Optional[str] = None
    ) -> DataSourceConnection:
        key = _database_key(ds.id, database or ds.database)
        async with self._lock:
            conn = self._pools.get(key)
            if conn is None:
                conn = DataSourceConnection(ds, database or ds.database)
                self._pools[key] = conn
            return conn

    async def drop(self, ds_id: int) -> None:
        async with self._lock:
            keys = [k for k in self._pools if k[0] == ds_id]
            items = [self._pools.pop(k) for k in keys]
        for c in items:
            try:
                await c.close()
            except Exception as e:
                logger.warning("close pool failed for ds=%s: %s", ds_id, e)

    async def reset(self) -> None:
        async with self._lock:
            items = list(self._pools.values())
            self._pools.clear()
        for c in items:
            try:
                await c.close()
            except Exception as e:
                logger.warning("reset pool close failed: %s", e)


data_source_manager = DataSourceManager()


@asynccontextmanager
async def acquire(ds: DataSource, database: Optional[str] = None):
    conn = await data_source_manager.get(ds, database)
    pool = await conn.get_pool()
    db = pool.acquire()
    try:
        raw = await db
    except Exception:
        try:
            pool.release(db)
        except Exception:
            pass
        raise
    try:
        yield raw
    finally:
        try:
            pool.release(raw)
        except Exception:
            pass


async def test_connection(ds: DataSource) -> dict:
    password = decrypt_value(ds.password_encrypted)
    try:
        conn = await aiomysql.connect(
            host=ds.host,
            port=ds.port,
            user=ds.username,
            password=password,
            db=ds.database or None,
            charset=ds.charset or "utf8mb4",
            connect_timeout=5,
            autocommit=True,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT VERSION()")
            row = await cur.fetchone()
            version = row[0] if row else ""
        return {"ok": True, "version": version}
    finally:
        conn.close()
