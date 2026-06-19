from __future__ import annotations

import re

from src.index.project_index import ProjectIndex
from src.scanner.project_scanner import ProjectScan


class ContextBuilder:
    def build(self, project: ProjectScan, index: ProjectIndex, table: str, column: str, radius: int = 20) -> str:
        chunks: list[str] = []
        by_path = {file.relative_path: file for file in project.files}
        sql_by_id = {unit.id: unit for unit in index.result.sql_units}
        for write in index.writes_for(table, column):
            file = by_path.get(write.location.path)
            if not file:
                continue
            lines = file.content.splitlines()
            start, end = max(0, write.location.line - radius - 1), min(len(lines), write.location.line + radius)
            excerpt = "\n".join(f"{number + 1}: {lines[number]}" for number in range(start, end))
            sql_unit = sql_by_id.get(write.sql_unit_id or "")
            sql_evidence = f"\nSQL_UNIT: {sql_unit.sql}" if sql_unit else ""
            chunks.append(f"FILE: {file.relative_path}\nTARGET: {table}.{column}{sql_evidence}\n{excerpt}")
        chunks.extend(self._structured_evidence(index, table, column))
        chunks.extend(self._related_code(project, chunks, radius))
        return "\n\n".join(chunks)[:60_000]

    @staticmethod
    def _structured_evidence(index: ProjectIndex, table: str, column: str) -> list[str]:
        values: list[str] = []
        for read in index.result.source_read_operations:
            values.append(f"SOURCE_READ: tables={read.tables}; columns={read.columns}; file={read.location.path}:{read.location.line}")
        for mapping in index.result.entity_mappings:
            if mapping.table == table or column in mapping.fields.values():
                values.append(f"ENTITY_MAPPING: entity={mapping.entity}; table={mapping.table}; fields={mapping.fields}")
        for mapping in index.result.dto_mappings:
            values.append(f"DTO_MAPPING: {mapping.source} -> {mapping.target}; fields={mapping.field_mappings}")
        return values[:80]

    @staticmethod
    def _related_code(project: ProjectScan, seed_chunks: list[str], radius: int) -> list[str]:
        seed = "\n".join(seed_chunks)
        tokens = {
            token for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b", seed)
            if token.lower() not in {"target", "source", "table", "column", "select", "insert", "update", "values", "where", "from", "file", "sql_unit"}
        }
        ranked: list[tuple[int, str, str]] = []
        existing_paths = {match.group(1) for match in re.finditer(r"FILE:\s*([^\n]+)", seed)}
        for file in project.by_suffix(".java", ".kt", ".xml", ".sql"):
            if file.relative_path in existing_paths:
                continue
            score = sum(min(file.content.count(token), 3) for token in tokens)
            if score:
                ranked.append((score, file.relative_path, file.content))
        related: list[str] = []
        for _, path, content in sorted(ranked, reverse=True)[:5]:
            lines = content.splitlines()
            matching = next((i for i, line in enumerate(lines) if any(token in line for token in tokens)), 0)
            local_radius = min(radius, 40)
            start, end = max(0, matching - local_radius), min(len(lines), matching + local_radius + 1)
            excerpt = "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))
            related.append(f"RELATED_FILE: {path}\n{excerpt}")
        return related
