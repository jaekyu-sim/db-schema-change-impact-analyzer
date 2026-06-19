from __future__ import annotations

import hashlib
import re


IDENT = r'[A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)?'


def compact_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def sql_id(framework: str, path: str, line: int, sql: str) -> str:
    digest = hashlib.sha1(sql.encode("utf-8")).hexdigest()[:12]
    return f"{framework}:{path}:{line}:{digest}"


def statement_kind(sql: str) -> str:
    match = re.search(r"\b(select|insert|update|delete|merge|with)\b", sql, re.I)
    if not match:
        return "unknown"
    kind = match.group(1).lower()
    if kind == "with":
        later = re.search(r"\b(select|insert|update|delete|merge)\b", sql[match.end():], re.I)
        return later.group(1).lower() if later else "select"
    return kind


def source_tables(sql: str) -> list[str]:
    found = re.findall(rf"\b(?:from|join)\s+({IDENT})", sql, re.I)
    return _unique(found)


def selected_expressions(sql: str) -> list[str]:
    match = re.search(r"\bselect\s+(.*?)\s+from\b", sql, re.I | re.S)
    if not match:
        return []
    return [part.strip() for part in _split_csv(match.group(1)) if part.strip()]


def write_target(sql: str) -> tuple[str | None, list[str], str]:
    kind = statement_kind(sql)
    if kind == "insert":
        match = re.search(rf"\binsert\s+into\s+({IDENT})\s*\((.*?)\)", sql, re.I | re.S)
        if match:
            return match.group(1), [_clean_identifier(c) for c in _split_csv(match.group(2))], kind
        table = re.search(rf"\binsert\s+into\s+({IDENT})", sql, re.I)
        return (table.group(1) if table else None), [], kind
    if kind == "update":
        table = re.search(rf"\bupdate\s+({IDENT})", sql, re.I)
        set_part = re.search(r"\bset\s+(.*?)(?:\bwhere\b|$)", sql, re.I | re.S)
        columns = re.findall(rf"(?:^|,)\s*({IDENT})\s*=", set_part.group(1), re.I) if set_part else []
        return (table.group(1) if table else None), [_clean_identifier(c) for c in columns], kind
    if kind == "delete":
        table = re.search(rf"\bdelete\s+from\s+({IDENT})", sql, re.I)
        return (table.group(1) if table else None), [], kind
    if kind == "merge":
        table = re.search(rf"\bmerge\s+into\s+({IDENT})", sql, re.I)
        columns = re.findall(rf"\b(?:insert|update)\s*\((.*?)\)", sql, re.I | re.S)
        flat = [_clean_identifier(c) for group in columns for c in _split_csv(group)]
        return (table.group(1) if table else None), _unique(flat), kind
    return None, [], kind


def _split_csv(value: str) -> list[str]:
    result, current, depth = [], [], 0
    for char in value:
        if char == "(" : depth += 1
        elif char == ")": depth = max(0, depth - 1)
        if char == "," and depth == 0:
            result.append("".join(current)); current = []
        else:
            current.append(char)
    result.append("".join(current))
    return result


def _clean_identifier(value: str) -> str:
    return value.strip().strip('`"[]')


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))

