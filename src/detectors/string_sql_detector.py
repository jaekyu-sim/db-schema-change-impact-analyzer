from __future__ import annotations

import re

from src.detectors.base import CodeLocation, DetectionResult, Detector, SourceReadOperation, SqlUnit, TargetWriteOperation, VariableAssignment
from src.detectors.java_sql import decode_java_strings, java_assignments
from src.detectors.sql_utils import compact_sql, selected_expressions, source_tables, sql_id, statement_kind, write_target
from src.scanner.project_scanner import ProjectScan


class StringSqlDetector(Detector):
    name = "string_sql"
    BUILDER = re.compile(r"(?:StringBuilder|StringBuffer)\s+(\w+)\s*=\s*new\s+(?:StringBuilder|StringBuffer)\s*\((.*?)\)\s*;", re.S)

    def supports(self, project: ProjectScan) -> bool:
        return any(re.search(r"String(?:Builder|Buffer)|\bString\s+\w+\s*=.*\b(?:SELECT|INSERT|UPDATE|DELETE|MERGE)\b", f.content, re.I | re.S) for f in project.by_suffix(".java", ".kt"))

    def detect(self, project: ProjectScan) -> DetectionResult:
        result = DetectionResult()
        for file in project.by_suffix(".java", ".kt"):
            candidates: list[tuple[str, str, int, str]] = []
            for match in self.BUILDER.finditer(file.content):
                variable = match.group(1)
                fragments = [match.group(2)]
                tail = file.content[match.end():]
                for append in re.finditer(rf"\b{re.escape(variable)}\s*\.\s*append\s*\((.*?)\)\s*;", tail, re.S):
                    fragments.append(append.group(1))
                expression = " + ".join(fragments)
                candidates.append((variable, expression, file.content[:match.start()].count("\n") + 1, "string_builder"))
            for variable, (expression, line) in java_assignments(file.content).items():
                if "+" in expression:
                    candidates.append((variable, expression, line, "string_concatenation"))
            for variable, expression, line, construction in candidates:
                sql = compact_sql(decode_java_strings(expression))
                if not re.search(r"\b(select|insert|update|delete|merge|with)\b", sql, re.I):
                    continue
                location = CodeLocation(file.relative_path, line)
                result.variable_assignments.append(VariableAssignment(variable, expression, location))
                unit_id = sql_id(self.name, file.relative_path, line, sql)
                kind = statement_kind(sql)
                result.sql_units.append(SqlUnit(unit_id, sql, kind, location, self.name, {"variable": variable, "construction": construction, "raw_expression": expression}))
                tables = source_tables(sql)
                if kind == "select" or tables:
                    result.source_read_operations.append(SourceReadOperation(tables, selected_expressions(sql), location, unit_id))
                table, columns, operation = write_target(sql)
                if table:
                    result.target_write_operations.append(TargetWriteOperation(table, columns, operation, location, unit_id))
        return result

