from __future__ import annotations

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
        return "\n\n".join(chunks)
