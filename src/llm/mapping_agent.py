from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Protocol


@dataclass(frozen=True)
class ColumnMapping:
    target_table: str
    target_column: str
    source_table: str | None
    source_column: str | None
    source_expression: str | None
    evidence: str | None = None

    @property
    def mapping_status(self) -> str:
        if self.source_table and self.source_column:
            return "MAPPED"
        if self.source_expression:
            return "DERIVED"
        return "UNRESOLVED"


class MappingModel(Protocol):
    def infer(self, prompt: str) -> dict[str, str | None]: ...


class MappingAgent:
    """LLM adapter intentionally receives one target-column context at a time."""

    def __init__(self, model: MappingModel):
        self.model = model

    def map_column(self, target_table: str, target_column: str, context: str) -> ColumnMapping:
        prompt = (
            "You analyze a Spring Boot DB migration program. Infer lineage only from the supplied evidence. "
            "Trace the target write backward through SQL parameters, entity/DTO fields, assignments, method calls, "
            "batch processor transformations, and source reads. Return source_table, source_column, "
            "source_expression, and concise evidence. Use null when evidence cannot establish a field. "
            "For constants or generated values, source_table/source_column may be null and source_expression must explain it. "
            "Never return a confidence field.\n"
            f"Target: {target_table}.{target_column}\nContext:\n{context}"
        )
        value = self.model.infer(prompt)
        return ColumnMapping(target_table, target_column, value.get("source_table"), value.get("source_column"), value.get("source_expression"), value.get("evidence"))


class OpenAIResponsesMappingModel:
    """OpenAI Responses API adapter with strict JSON-schema output."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("LLM 실행에 openai 패키지가 필요합니다. `pip install -e .`를 실행하세요.") from exc
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다. 정적 분석만 실행하려면 --no-llm을 사용하세요.")
        self.client = OpenAI(api_key=key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    def infer(self, prompt: str) -> dict[str, str | None]:
        schema = {
            "type": "object",
            "properties": {
                "source_table": {"type": ["string", "null"]},
                "source_column": {"type": ["string", "null"]},
                "source_expression": {"type": ["string", "null"]},
                "evidence": {"type": ["string", "null"]},
            },
            "required": ["source_table", "source_column", "source_expression", "evidence"],
            "additionalProperties": False,
        }
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            text={"format": {"type": "json_schema", "name": "column_lineage", "strict": True, "schema": schema}},
        )
        return json.loads(response.output_text)


class EvidenceMappingModel:
    """Deterministic fallback for lineage explicitly present in INSERT ... SELECT SQL."""

    INSERT_SELECT = re.compile(
        r"insert\s+into\s+([\w.$]+)\s*\((.*?)\)\s*select\s+(.*?)\s+from\s+([\w.$]+)",
        re.I | re.S,
    )

    def infer(self, prompt: str) -> dict[str, str | None]:
        target = re.search(r"Target:\s*([\w.$]+)\.([\w$]+)", prompt)
        if not target:
            return self._empty()
        target_table, target_column = target.groups()
        for match in self.INSERT_SELECT.finditer(prompt):
            if match.group(1).lower() != target_table.lower():
                continue
            target_columns = [self._identifier(value) for value in self._split_csv(match.group(2))]
            expressions = self._split_csv(match.group(3))
            try:
                position = [value.lower() for value in target_columns].index(target_column.lower())
            except ValueError:
                continue
            if position >= len(expressions):
                continue
            expression = expressions[position].strip()
            source_column = self._source_column(expression)
            return {
                "source_table": match.group(4),
                "source_column": source_column,
                "source_expression": expression,
                "evidence": "INSERT ... SELECT positional mapping",
            }
        return self._empty()

    @staticmethod
    def _source_column(expression: str) -> str | None:
        without_alias = re.split(r"\s+as\s+", expression, flags=re.I)[0].strip()
        match = re.fullmatch(r"(?:[\w$]+\.)?([\w$]+)", without_alias)
        return match.group(1) if match else None

    @staticmethod
    def _identifier(value: str) -> str:
        return value.strip().strip('`"[]')

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        result: list[str] = []
        current: list[str] = []
        depth = 0
        for char in value:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            if char == "," and depth == 0:
                result.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        result.append("".join(current).strip())
        return result

    @staticmethod
    def _empty() -> dict[str, None]:
        return {"source_table": None, "source_column": None, "source_expression": None, "evidence": None}
