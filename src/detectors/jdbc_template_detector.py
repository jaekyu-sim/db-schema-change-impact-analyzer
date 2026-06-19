from __future__ import annotations

import re

from src.detectors.base import CodeLocation, DetectionResult, Detector, MethodCall, SourceReadOperation, SqlUnit, TargetWriteOperation, VariableAssignment
from src.detectors.java_sql import decode_java_strings, java_assignments
from src.detectors.sql_utils import compact_sql, selected_expressions, source_tables, sql_id, statement_kind, write_target
from src.scanner.project_scanner import ProjectScan


class JdbcTemplateDetector(Detector):
    name = "jdbc_template"
    CALL = re.compile(r"(?P<receiver>\w*(?:JdbcTemplate|jdbcTemplate))\s*\.\s*(?P<method>queryForObject|queryForList|query|update|batchUpdate|execute)\s*\(\s*(?P<sql>\"(?:\\.|[^\"\\])*\"|[^,;)]+)", re.I)

    def supports(self, project: ProjectScan) -> bool:
        return "jdbc_template" in project.technology_candidates

    def detect(self, project: ProjectScan) -> DetectionResult:
        result = DetectionResult()
        for file in project.by_suffix(".java", ".kt"):
            assignments = java_assignments(file.content)
            for variable, (expression, line) in assignments.items():
                if self._looks_like_sql(expression):
                    result.variable_assignments.append(VariableAssignment(variable, expression, CodeLocation(file.relative_path, line)))
            for match in self.CALL.finditer(file.content):
                line = file.content[:match.start()].count("\n") + 1
                location = CodeLocation(file.relative_path, line)
                sql_arg = match.group("sql").strip()
                expression = assignments.get(sql_arg, (sql_arg, line))[0]
                sql = compact_sql(decode_java_strings(expression))
                result.method_calls.append(MethodCall(match.group("receiver"), match.group("method"), sql_arg, location))
                if not self._looks_like_sql(sql):
                    continue
                unit_id = sql_id(self.name, file.relative_path, line, sql)
                kind = statement_kind(sql)
                result.sql_units.append(SqlUnit(unit_id, sql, kind, location, self.name, {"sql_argument": sql_arg}))
                tables = source_tables(sql)
                if kind == "select" or tables:
                    result.source_read_operations.append(SourceReadOperation(tables, selected_expressions(sql), location, unit_id, match.group("method")))
                table, columns, operation = write_target(sql)
                if table:
                    result.target_write_operations.append(TargetWriteOperation(table, columns, operation, location, unit_id, match.group("method")))
        return result

    @staticmethod
    def _looks_like_sql(value: str) -> bool:
        return bool(re.search(r"\b(select|insert|update|delete|merge|with)\b", value, re.I))
