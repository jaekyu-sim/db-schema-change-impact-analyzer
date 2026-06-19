from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from src.scanner.project_scanner import ProjectScan


@dataclass(frozen=True)
class CodeLocation:
    path: str
    line: int = 1


@dataclass
class SqlUnit:
    id: str
    sql: str
    kind: str
    location: CodeLocation
    framework: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceReadOperation:
    tables: list[str]
    columns: list[str]
    location: CodeLocation
    sql_unit_id: str | None = None
    method: str | None = None


@dataclass
class TargetWriteOperation:
    target_table: str
    target_columns: list[str]
    operation: str
    location: CodeLocation
    sql_unit_id: str | None = None
    method: str | None = None


@dataclass
class EntityMapping:
    entity: str
    table: str | None
    fields: dict[str, str]
    location: CodeLocation


@dataclass
class DtoMapping:
    source: str
    target: str
    field_mappings: dict[str, str]
    location: CodeLocation


@dataclass
class MethodCall:
    receiver: str | None
    method: str
    arguments: str
    location: CodeLocation


@dataclass
class VariableAssignment:
    variable: str
    expression: str
    location: CodeLocation


@dataclass
class DetectionResult:
    source_read_operations: list[SourceReadOperation] = field(default_factory=list)
    target_write_operations: list[TargetWriteOperation] = field(default_factory=list)
    sql_units: list[SqlUnit] = field(default_factory=list)
    entity_mappings: list[EntityMapping] = field(default_factory=list)
    dto_mappings: list[DtoMapping] = field(default_factory=list)
    method_calls: list[MethodCall] = field(default_factory=list)
    variable_assignments: list[VariableAssignment] = field(default_factory=list)

    def merge(self, other: "DetectionResult") -> "DetectionResult":
        for field_name in self.__dataclass_fields__:
            getattr(self, field_name).extend(getattr(other, field_name))
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Detector(ABC):
    name: str

    @abstractmethod
    def supports(self, project: ProjectScan) -> bool:
        """Return whether this detector has evidence worth inspecting."""

    @abstractmethod
    def detect(self, project: ProjectScan) -> DetectionResult:
        """Collect evidence. A detector must not infer unsupported lineage."""

