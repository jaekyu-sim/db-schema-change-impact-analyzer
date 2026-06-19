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


class LocalChatOpenAIMappingModel:
    """ChatOpenAI adapter for a local OpenAI-compatible sLLM server."""

    METHODS = {"json_mode", "json_schema", "function_calling", "raw"}

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        structured_output_method: str | None = None,
        timeout: float = 120.0,
        chat_model: object | None = None,
    ):
        self.model = model or os.getenv("SLLM_MODEL")
        if not self.model:
            raise RuntimeError("로컬 sLLM 모델명이 필요합니다. SLLM_MODEL 또는 --model을 설정하세요.")
        self.base_url = base_url or os.getenv("SLLM_BASE_URL", "http://localhost:8000/v1")
        self.method = structured_output_method or os.getenv("SLLM_STRUCTURED_OUTPUT_METHOD", "json_mode")
        if self.method not in self.METHODS:
            raise RuntimeError(f"지원하지 않는 structured output 방식입니다: {self.method}")
        if chat_model is None:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise RuntimeError("로컬 LLM 실행에 langchain-openai가 필요합니다. `pip install -e .`를 실행하세요.") from exc
            chat_model = ChatOpenAI(
                model=self.model,
                base_url=self.base_url,
                api_key=api_key or os.getenv("SLLM_API_KEY", "not-needed"),
                temperature=0,
                timeout=timeout,
                max_retries=2,
            )
        self.chat_model = chat_model
        self.structured_model = None if self.method == "raw" else self._structured(chat_model)

    def _structured(self, chat_model: object) -> object:
        try:
            from pydantic import BaseModel, Field
        except ImportError as exc:
            raise RuntimeError("구조화 출력에 pydantic이 필요합니다. `pip install -e .`를 실행하세요.") from exc

        class LineageResponse(BaseModel):
            source_table: str | None = Field(description="Physical source DB table, or null")
            source_column: str | None = Field(description="Physical source DB column, or null")
            source_expression: str | None = Field(description="Transformation, constant, or source expression, or null")
            evidence: str | None = Field(description="Concise code evidence, or null")

        return chat_model.with_structured_output(LineageResponse, method=self.method)

    def infer(self, prompt: str) -> dict[str, str | None]:
        if self.structured_model is not None:
            result = self.structured_model.invoke(prompt)
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            return self._normalize(result)
        response = self.chat_model.invoke(
            prompt + "\nReturn only one JSON object with keys source_table, source_column, source_expression, evidence."
        )
        content = self._message_text(getattr(response, "content", response))
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.I | re.S)
        candidate = fenced.group(1) if fenced else content[content.find("{"):content.rfind("}") + 1]
        try:
            return self._normalize(json.loads(candidate))
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError(f"로컬 sLLM이 유효한 lineage JSON을 반환하지 않았습니다: {content[:300]}") from exc

    @staticmethod
    def _message_text(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                str(block.get("text", "")) if isinstance(block, dict) else str(block)
                for block in content
            )
        return str(content)

    @staticmethod
    def _normalize(value: object) -> dict[str, str | None]:
        if not isinstance(value, dict):
            raise RuntimeError(f"로컬 sLLM 구조화 출력 형식이 dict가 아닙니다: {type(value).__name__}")
        keys = ("source_table", "source_column", "source_expression", "evidence")
        return {key: str(value[key]) if value.get(key) is not None else None for key in keys}


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
