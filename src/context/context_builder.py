from __future__ import annotations

from src.index.project_index import ProjectIndex
from src.scanner.project_scanner import ProjectScan


class ContextBuilder:
    def build(self, project: ProjectScan, index: ProjectIndex, table: str, column: str, radius: int = 20) -> str:
        chunks: list[str] = []
        by_path = {file.relative_path: file for file in project.files}
        for write in index.writes_for(table, column):
            file = by_path.get(write.location.path)
            if not file:
                continue
            lines = file.content.splitlines()
            start, end = max(0, write.location.line - radius - 1), min(len(lines), write.location.line + radius)
            excerpt = "\n".join(f"{number + 1}: {lines[number]}" for number in range(start, end))
            chunks.append(f"FILE: {file.relative_path}\nTARGET: {table}.{column}\n{excerpt}")
        return "\n\n".join(chunks)

