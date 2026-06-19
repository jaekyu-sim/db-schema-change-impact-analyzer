from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ColumnMapping:
    target_table: str
    target_column: str
    source_table: str | None
    source_column: str | None
    source_expression: str | None
    evidence: str | None = None


class MappingModel(Protocol):
    def infer(self, prompt: str) -> dict[str, str | None]: ...


class MappingAgent:
    """LLM adapter intentionally receives one target-column context at a time."""

    def __init__(self, model: MappingModel):
        self.model = model

    def map_column(self, target_table: str, target_column: str, context: str) -> ColumnMapping:
        prompt = (
            "Infer data lineage only from the supplied evidence. Return source_table, "
            "source_column, source_expression, and evidence. Do not return confidence.\n"
            f"Target: {target_table}.{target_column}\nContext:\n{context}"
        )
        value = self.model.infer(prompt)
        return ColumnMapping(target_table, target_column, value.get("source_table"), value.get("source_column"), value.get("source_expression"), value.get("evidence"))

