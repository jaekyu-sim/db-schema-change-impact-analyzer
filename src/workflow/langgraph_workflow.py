from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, TypedDict

from src.context.context_builder import ContextBuilder
from src.index.project_index import ProjectIndex
from src.llm.mapping_agent import ColumnMapping, MappingAgent
from src.scanner.project_scanner import ProjectScan
from src.validator.coverage_validator import CoverageValidator


logger = logging.getLogger(__name__)


class ColumnState(TypedDict, total=False):
    project: ProjectScan
    index: ProjectIndex
    target_table: str
    target_column: str
    radius: int
    attempt: int
    context: str
    mapping: ColumnMapping


class MappingWorkflow:
    """Runs one isolated LangGraph state machine per target column."""

    def __init__(self, agent: MappingAgent, context_builder: ContextBuilder | None = None):
        self.agent = agent
        self.context_builder = context_builder or ContextBuilder()
        self.validator = CoverageValidator()
        self.graph = self._compile_graph()

    def run(self, project: ProjectScan, index: ProjectIndex) -> list[ColumnMapping]:
        expected = index.target_columns()
        logger.info("컬럼 매핑 시작: 총 %d개 Target 컬럼", len(expected))
        mappings: list[ColumnMapping] = []
        for position, (table, column) in enumerate(expected, start=1):
            started = perf_counter()
            logger.info("컬럼 매핑 [%d/%d] 시작: %s.%s", position, len(expected), table, column)
            mapping = self._run_column(project, index, table, column)
            mappings.append(mapping)
            logger.info(
                "컬럼 매핑 [%d/%d] 완료: %s.%s -> %s.%s | %s | %.2f초",
                position, len(expected), table, column,
                mapping.source_table or "-", mapping.source_column or "-", mapping.mapping_status,
                perf_counter() - started,
            )
        coverage = self.validator.validate(expected, mappings)
        if not coverage.complete:
            existing = {(item.target_table, item.target_column) for item in mappings}
            mappings.extend(self._run_column(project, index, table, column, radius=120) for table, column in coverage.missing if (table, column) not in existing)
        unresolved = sum(item.mapping_status == "UNRESOLVED" for item in mappings)
        logger.info("컬럼 매핑 완료: 전체=%d, 미해결=%d", len(mappings), unresolved)
        return mappings

    def _run_column(self, project: ProjectScan, index: ProjectIndex, table: str, column: str, radius: int = 24) -> ColumnMapping:
        initial: ColumnState = {"project": project, "index": index, "target_table": table, "target_column": column, "radius": radius, "attempt": 0}
        if self.graph is not None:
            return self.graph.invoke(initial)["mapping"]
        state = self._build_context(initial)
        while True:
            state = self._infer(state)
            if self._route(state) == "done":
                return state["mapping"]
            state = self._expand(state)
            state = self._build_context(state)

    def _compile_graph(self) -> Any | None:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None
        builder = StateGraph(ColumnState)
        builder.add_node("build_context", self._build_context)
        builder.add_node("infer", self._infer)
        builder.add_node("expand_context", self._expand)
        builder.add_edge(START, "build_context")
        builder.add_edge("build_context", "infer")
        builder.add_conditional_edges("infer", self._route, {"retry": "expand_context", "done": END})
        builder.add_edge("expand_context", "build_context")
        return builder.compile()

    def _build_context(self, state: ColumnState) -> ColumnState:
        context = self.context_builder.build(state["project"], state["index"], state["target_table"], state["target_column"], state["radius"])
        return {**state, "context": context}

    def _infer(self, state: ColumnState) -> ColumnState:
        attempt = state.get("attempt", 0) + 1
        logger.debug(
            "매핑 추론 호출: %s.%s, 시도=%d, context=%d자",
            state["target_table"], state["target_column"], attempt, len(state.get("context", "")),
        )
        mapping = self.agent.map_column(state["target_table"], state["target_column"], state.get("context", ""))
        return {**state, "mapping": mapping, "attempt": attempt}

    @staticmethod
    def _route(state: ColumnState) -> str:
        mapping = state["mapping"]
        resolved = bool(mapping.source_expression or mapping.source_table or mapping.source_column)
        return "done" if resolved or state.get("attempt", 0) >= 2 else "retry"

    @staticmethod
    def _expand(state: ColumnState) -> ColumnState:
        radius = max(state.get("radius", 24) * 4, 96)
        logger.info(
            "미해결 컬럼 컨텍스트 확장 재시도: %s.%s, radius=%d",
            state["target_table"], state["target_column"], radius,
        )
        return {**state, "radius": radius}
