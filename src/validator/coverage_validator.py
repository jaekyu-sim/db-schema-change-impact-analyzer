from __future__ import annotations

from dataclasses import dataclass

from src.llm.mapping_agent import ColumnMapping


@dataclass(frozen=True)
class CoverageResult:
    complete: bool
    missing: list[tuple[str, str]]


class CoverageValidator:
    def validate(self, expected: list[tuple[str, str]], mappings: list[ColumnMapping]) -> CoverageResult:
        mapped = {(item.target_table, item.target_column) for item in mappings}
        missing = [item for item in expected if item not in mapped]
        return CoverageResult(not missing, missing)

