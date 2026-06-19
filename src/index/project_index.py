from __future__ import annotations

from dataclasses import dataclass, field
import logging
from time import perf_counter

from src.detectors.base import DetectionResult, Detector, TargetWriteOperation
from src.scanner.project_scanner import ProjectScan


logger = logging.getLogger(__name__)


@dataclass
class ProjectIndex:
    result: DetectionResult = field(default_factory=DetectionResult)

    @classmethod
    def build(cls, project: ProjectScan, detectors: list[Detector]) -> "ProjectIndex":
        index = cls()
        for detector in detectors:
            started = perf_counter()
            logger.info("Detector 실행 시작: %s", detector.name)
            before = (
                len(index.result.source_read_operations),
                len(index.result.target_write_operations),
                len(index.result.sql_units),
            )
            # supports() is a prioritization hint, never a correctness gate. Real projects
            # frequently hide framework dependencies in parent builds or shared modules.
            index.result.merge(detector.detect(project))
            after = (
                len(index.result.source_read_operations),
                len(index.result.target_write_operations),
                len(index.result.sql_units),
            )
            logger.info(
                "Detector 실행 완료: %s | source reads +%d, target writes +%d, SQL units +%d | %.2f초",
                detector.name, after[0] - before[0], after[1] - before[1], after[2] - before[2], perf_counter() - started,
            )
        index._deduplicate()
        logger.info(
            "프로젝트 인덱스 완료: source reads=%d, target writes=%d, target columns=%d, SQL units=%d",
            len(index.result.source_read_operations), len(index.result.target_write_operations),
            len(index.target_columns()), len(index.result.sql_units),
        )
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
