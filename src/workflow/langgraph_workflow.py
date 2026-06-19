from __future__ import annotations

from typing import Any, TypedDict

from src.context.context_builder import ContextBuilder
from src.index.project_index import ProjectIndex
from src.llm.mapping_agent import ColumnMapping, MappingAgent
from src.scanner.project_scanner import ProjectScan
from src.validator.coverage_validator import CoverageValidator


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
        mappings = [self._run_column(project, index, table, column) for table, column in expected]
        coverage = self.validator.validate(expected, mappings)
        if not coverage.complete:
            existing = {(item.target_table, item.target_column) for item in mappings}
            mappings.extend(self._run_column(project, index, table, column, radius=120) for table, column in coverage.missing if (table, column) not in existing)
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
        mapping = self.agent.map_column(state["target_table"], state["target_column"], state.get("context", ""))
        return {**state, "mapping": mapping, "attempt": state.get("attempt", 0) + 1}

    @staticmethod
    def _route(state: ColumnState) -> str:
        mapping = state["mapping"]
        resolved = bool(mapping.source_expression or mapping.source_table or mapping.source_column)
        return "done" if resolved or state.get("attempt", 0) >= 2 else "retry"

    @staticmethod
    def _expand(state: ColumnState) -> ColumnState:
        return {**state, "radius": max(state.get("radius", 24) * 4, 96)}
