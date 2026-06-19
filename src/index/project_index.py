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
            if detector.supports(project):
                index.result.merge(detector.detect(project))
        return index

    def target_columns(self) -> list[tuple[str, str]]:
        values = ((op.target_table, column) for op in self.result.target_write_operations for column in op.target_columns)
        return list(dict.fromkeys(values))

    def writes_for(self, table: str, column: str) -> list[TargetWriteOperation]:
        return [op for op in self.result.target_write_operations if op.target_table == table and column in op.target_columns]

