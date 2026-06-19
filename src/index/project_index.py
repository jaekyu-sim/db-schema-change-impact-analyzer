from __future__ import annotations

from dataclasses import dataclass, field

from src.detectors.base import DetectionResult, Detector, TargetWriteOperation
from src.scanner.project_scanner import ProjectScan


@dataclass
class ProjectIndex:
    result: DetectionResult = field(default_factory=DetectionResult)

    @classmethod
    def build(cls, project: ProjectScan, detectors: list[Detector]) -> "ProjectIndex":
        index = cls()
        for detector in detectors:
            # supports() is a prioritization hint, never a correctness gate. Real projects
            # frequently hide framework dependencies in parent builds or shared modules.
            index.result.merge(detector.detect(project))
        index._deduplicate()
        return index

    def _deduplicate(self) -> None:
        for field_name in self.result.__dataclass_fields__:
            values = getattr(self.result, field_name)
            unique = []
            seen = set()
            for value in values:
                key = repr(value)
                if key not in seen:
                    seen.add(key)
                    unique.append(value)
            setattr(self.result, field_name, unique)

    def target_columns(self) -> list[tuple[str, str]]:
        values = ((op.target_table, column) for op in self.result.target_write_operations for column in op.target_columns)
        return list(dict.fromkeys(values))

    def writes_for(self, table: str, column: str) -> list[TargetWriteOperation]:
        return [op for op in self.result.target_write_operations if op.target_table == table and column in op.target_columns]
