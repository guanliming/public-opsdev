from __future__ import annotations

import logging
import time
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.datasource_pool import acquire, data_source_manager
from app.models import DataSource, User
from app.schemas import (
    SqlDatabaseInfo,
    SqlExecuteRequest,
    SqlExecuteResponse,
    SqlStatementResult,
    SqlTableInfo,
)
from app.sql_safety import (
    StatementKind,
    check_non_admin_constraints,
    is_dangerous_ddl,
    parse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sql", tags=["sql"])

DANGEROUS_DDL_KINDS = {
    "DROP",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "RENAME",
    "LOCK",
    "UNLOCK",
    "CALL",
    "HANDLER",
    "LOAD",
    "OUTFILE",
    "DUMPFILE",
    "SHUTDOWN",
    "KILL",
}

DESTRUCTIVE_KINDS = {StatementKind.UPDATE, StatementKind.DELETE, StatementKind.REPLACE}

NON_ADMIN_MAX_ROWS = 20
MAX_RESULT_ROWS = 1000
MAX_STATEMENT_SECONDS = 30


def _serialize_value(v):
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return str(v)
    return v


async def _list_databases(ds: DataSource) -> List[str]:
    async with acquire(ds, None) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SHOW DATABASES")
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def _list_tables(
    ds: DataSource, database: Optional[str] = None
) -> List[SqlTableInfo]:
    db_name = database or ds.database
    if not db_name:
        raise HTTPException(status_code=400, detail="数据源未指定数据库")
    sql = (
        "SELECT TABLE_NAME, IFNULL(TABLE_ROWS, 0), "
        "ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) "
        "FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s "
        "ORDER BY TABLE_NAME"
    )
    async with acquire(ds, db_name) as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (db_name,))
            rows = await cur.fetchall()
    return [
        SqlTableInfo(name=r[0], rows=int(r[1] or 0), size_mb=float(r[2] or 0))
        for r in rows
    ]


async def _ensure_database(
    ds: DataSource, override_database: Optional[str]
) -> DataSource:
    if override_database and override_database != ds.database:
        ds = DataSource(
            id=ds.id,
            name=ds.name,
            db_type=ds.db_type,
            host=ds.host,
            port=ds.port,
            username=ds.username,
            password_encrypted=ds.password_encrypted,
            database=override_database,
            charset=ds.charset,
            description=ds.description,
        )
    return ds


async def _safe_count_with_conn(conn, database: Optional[str], dml_sql: str) -> int:
    import re as _re

    upper = dml_sql.upper().lstrip()
    if not upper.startswith(("UPDATE", "DELETE", "REPLACE")):
        return 0
    cleaned = _re.sub(
        r"^(UPDATE|DELETE|REPLACE)\s+", "", dml_sql, count=1, flags=_re.IGNORECASE
    )
    where_idx = cleaned.upper().find(" WHERE ")
    where_clause = ""
    if where_idx >= 0:
        where_clause = cleaned[where_idx:]
        trailing = _re.search(r"\b(LIMIT|ORDER\s+BY)\b", where_clause.upper())
        if trailing:
            where_clause = where_clause[: trailing.start()]
    count_sql = f"SELECT COUNT(*) AS cnt FROM {cleaned.split(' WHERE ')[0].strip()} {where_clause}".strip()
    if not where_clause:
        count_sql = (
            f"SELECT COUNT(*) AS cnt FROM {cleaned.split(' WHERE ')[0].strip()}".strip()
        )
    async with conn.cursor() as cur:
        await cur.execute(count_sql)
        row = await cur.fetchone()
    return int(row[0]) if row else 0


@router.get("/datasources/{ds_id}/databases", response_model=list[SqlDatabaseInfo])
async def sql_list_databases(
    ds_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    names = await _list_databases(ds)
    return [SqlDatabaseInfo(name=n) for n in names]


@router.get("/datasources/{ds_id}/tables", response_model=list[SqlTableInfo])
async def sql_list_tables(
    ds_id: int,
    database: Optional[str] = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    ds = await _ensure_database(ds, database)
    return await _list_tables(ds, database)


@router.post("/datasources/{ds_id}/execute", response_model=SqlExecuteResponse)
async def sql_execute(
    ds_id: int,
    req: SqlExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    sql_text = (req.sql or "").strip()
    if not sql_text:
        raise HTTPException(status_code=400, detail="SQL 不能为空")

    selected_database = (req.database or ds.database or "").strip()
    if not selected_database:
        raise HTTPException(status_code=400, detail="请先选择数据库")

    is_admin = current_user.role == "admin"
    max_rows = min(max(1, req.max_rows), MAX_RESULT_ROWS)

    statements = parse(sql_text)
    if not statements:
        raise HTTPException(status_code=400, detail="未解析到任何 SQL 语句")

    results: List[SqlStatementResult] = []
    total_affected = 0
    total_time = 0.0
    has_writes = False

    for stmt in statements:
        kind = stmt.kind
        dangerous = is_dangerous_ddl(stmt.sql)
        if dangerous and dangerous in DANGEROUS_DDL_KINDS and not is_admin:
            results.append(
                SqlStatementResult(
                    sql=stmt.sql,
                    kind=kind.value,
                    error=f"非管理员禁止执行危险语句: {dangerous}",
                )
            )
            continue
        if kind == StatementKind.DDL and not is_admin:
            results.append(
                SqlStatementResult(
                    sql=stmt.sql,
                    kind=kind.value,
                    error="非管理员禁止执行 DDL 语句",
                )
            )
            continue
        if not is_admin and kind in DESTRUCTIVE_KINDS:
            constraint_error = check_non_admin_constraints(stmt, NON_ADMIN_MAX_ROWS)
            if constraint_error:
                results.append(
                    SqlStatementResult(
                        sql=stmt.sql,
                        kind=kind.value,
                        error=constraint_error,
                    )
                )
                continue
        results.append(
            SqlStatementResult(
                sql=stmt.sql,
                kind=kind.value,
                skipped=True,
                skip_reason="待执行",
            )
        )

    needs_exec_estimate = any(
        r.skipped
        and r.kind
        in {
            StatementKind.UPDATE.value,
            StatementKind.DELETE.value,
            StatementKind.REPLACE.value,
        }
        for r in results
    )

    estimated_rows = 0
    if needs_exec_estimate and not is_admin:
        try:
            async with acquire(ds, selected_database) as conn:
                for r in results:
                    if r.skipped and r.kind in {
                        StatementKind.UPDATE.value,
                        StatementKind.DELETE.value,
                        StatementKind.REPLACE.value,
                    }:
                        try:
                            cnt = await _safe_count_with_conn(
                                conn, selected_database, r.sql
                            )
                            estimated_rows += cnt
                        except Exception as e:
                            r.error = f"统计受影响行数失败: {e}"
                            r.skipped = False
        except Exception as e:
            return SqlExecuteResponse(
                datasource_id=ds_id,
                is_admin=is_admin,
                statements=[
                    SqlStatementResult(
                        sql=stmt.sql,
                        kind=stmt.kind.value,
                        error=f"连接数据源失败: {e}",
                    )
                    for stmt in statements
                ],
                total_affected_rows=0,
                total_execution_time_ms=0,
            )

    if not is_admin:
        if estimated_rows > NON_ADMIN_MAX_ROWS:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"非管理员执行 UPDATE/DELETE/REPLACE 受影响行数 {estimated_rows} 超过限制 {NON_ADMIN_MAX_ROWS},已拒绝"
                ),
            )

    has_pending = any(r.skipped for r in results)
    if not has_pending:
        return SqlExecuteResponse(
            datasource_id=ds_id,
            is_admin=is_admin,
            statements=results,
            total_affected_rows=0,
            total_execution_time_ms=0.0,
        )

    for r in results:
        if not r.skipped:
            continue
        has_writes = has_writes or r.kind in {
            StatementKind.UPDATE.value,
            StatementKind.DELETE.value,
            StatementKind.REPLACE.value,
            StatementKind.INSERT.value,
            StatementKind.DDL.value,
        }

    if has_writes and not is_admin and not req.confirm_large_change:
        pass

    async with acquire(ds, selected_database) as conn:
        try:
            await conn.begin()
        except Exception:
            pass
        for r in results:
            if not r.skipped:
                continue
            start = time.perf_counter()
            try:
                async with conn.cursor() as cur:
                    await cur.execute(r.sql)
                    elapsed = (time.perf_counter() - start) * 1000
                    r.execution_time_ms = round(elapsed, 2)
                    if r.kind in {StatementKind.SELECT.value}:
                        cols = (
                            [d[0] for d in cur.description] if cur.description else []
                        )
                        r.columns = [{"name": c, "type": ""} for c in cols]
                        fetched = await cur.fetchmany(max_rows + 1)
                        truncated = len(fetched) > max_rows
                        if truncated:
                            fetched = fetched[:max_rows]
                        r.rows = [
                            dict(zip(cols, [_serialize_value(v) for v in row]))
                            for row in fetched
                        ]
                        r.truncated = truncated
                        r.affected_rows = len(r.rows)
                    else:
                        r.affected_rows = cur.rowcount or 0
                        total_affected += r.affected_rows
                r.skipped = False
            except Exception as e:
                r.error = str(e)
                r.skipped = False
        try:
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    for r in results:
        total_time += r.execution_time_ms

    return SqlExecuteResponse(
        datasource_id=ds_id,
        is_admin=is_admin,
        statements=results,
        total_affected_rows=total_affected,
        total_execution_time_ms=round(total_time, 2),
    )
