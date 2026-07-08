from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class StatementKind(str, Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REPLACE = "REPLACE"
    DDL = "DDL"
    OTHER = "OTHER"


@dataclass
class ParsedStatement:
    sql: str
    kind: StatementKind
    is_multi: bool


_DANGEROUS_KEYWORDS = {
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


_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_RE = re.compile(r"'(?:''|\\'|[^'])*'")


def strip_comments(sql: str) -> str:
    sql = _COMMENT_BLOCK_RE.sub(" ", sql)
    sql = _COMMENT_LINE_RE.sub(" ", sql)
    return sql


def split_statements(sql: str) -> List[str]:
    cleaned = strip_comments(sql)
    statements: List[str] = []
    buf: List[str] = []
    in_string = False
    i = 0
    n = len(cleaned)
    while i < n:
        ch = cleaned[i]
        if ch == "'":
            if in_string and i + 1 < n and cleaned[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_string = not in_string
            buf.append(ch)
            i += 1
            continue
        if not in_string and ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _first_keyword(sql: str) -> str:
    cleaned = strip_comments(sql).lstrip("(").strip()
    m = re.match(r"[A-Za-z]+", cleaned)
    return m.group(0).upper() if m else ""


def _uppercase_letters(sql: str) -> str:
    return re.sub(r"[^A-Za-z]", "", sql).upper()


def classify(stmt: str) -> StatementKind:
    kw = _first_keyword(stmt)
    if kw in ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH"):
        return StatementKind.SELECT
    if kw in ("INSERT",):
        return StatementKind.INSERT
    if kw in ("UPDATE",):
        return StatementKind.UPDATE
    if kw in ("DELETE",):
        return StatementKind.DELETE
    if kw in ("REPLACE",):
        return StatementKind.REPLACE
    if kw in ("CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"):
        return StatementKind.DDL
    return StatementKind.OTHER


def is_dangerous_ddl(stmt: str) -> Optional[str]:
    kw = _first_keyword(stmt)
    if kw in _DANGEROUS_KEYWORDS:
        return kw
    return None


def parse(sql: str) -> List[ParsedStatement]:
    raw_statements = split_statements(sql)
    parsed: List[ParsedStatement] = []
    for s in raw_statements:
        parsed.append(
            ParsedStatement(sql=s, kind=classify(s), is_multi=len(raw_statements) > 1)
        )
    return parsed


def parse_safe(sql: str) -> List[ParsedStatement]:
    return parse(sql)


def _contains_subquery_update_delete(stmt: str, kind: StatementKind) -> bool:
    if kind not in (StatementKind.UPDATE, StatementKind.DELETE):
        return False
    upper = _uppercase_letters(stmt)
    return "SELECT" in upper


_DML_ROW_LIMIT_DEFAULT = 20


def estimate_affected_rows_limit(allowed_max: int = _DML_ROW_LIMIT_DEFAULT) -> int:
    return max(1, allowed_max)


def check_non_admin_constraints(
    stmt: ParsedStatement, allowed_max_rows: int
) -> Optional[str]:
    if stmt.kind in (StatementKind.UPDATE, StatementKind.DELETE):
        if _contains_subquery_update_delete(stmt.sql, stmt.kind):
            return f"非管理员禁止执行带子查询的 {stmt.kind.value} 语句"
    return None
