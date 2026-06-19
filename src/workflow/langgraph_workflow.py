from __future__ import annotations

from src.context.context_builder import ContextBuilder
from src.index.project_index import ProjectIndex
from src.llm.mapping_agent import ColumnMapping, MappingAgent
from src.scanner.project_scanner import ProjectScan
from src.validator.coverage_validator import CoverageValidator


class MappingWorkflow:
    """Framework-neutral workflow core; it can be wrapped as LangGraph nodes later."""

    def __init__(self, agent: MappingAgent, context_builder: ContextBuilder | None = None):
        self.agent = agent
        self.context_builder = context_builder or ContextBuilder()
        self.validator = CoverageValidator()

    def run(self, project: ProjectScan, index: ProjectIndex) -> list[ColumnMapping]:
        expected = index.target_columns()
        mappings = [self._map(project, index, table, column, 20) for table, column in expected]
        coverage = self.validator.validate(expected, mappings)
        if not coverage.complete:
            mappings.extend(self._map(project, index, table, column, 80) for table, column in coverage.missing)
        return mappings

    def _map(self, project: ProjectScan, index: ProjectIndex, table: str, column: str, radius: int) -> ColumnMapping:
        context = self.context_builder.build(project, index, table, column, radius)
        return self.agent.map_column(table, column, context)

