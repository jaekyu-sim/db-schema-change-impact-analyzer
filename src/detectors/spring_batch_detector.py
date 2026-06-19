from __future__ import annotations

import re

from src.detectors.base import CodeLocation, DetectionResult, Detector, MethodCall, SourceReadOperation, SqlUnit, TargetWriteOperation
from src.detectors.java_sql import decode_java_strings, java_assignments
from src.detectors.sql_utils import compact_sql, selected_expressions, source_tables, sql_id, statement_kind, write_target
from src.scanner.project_scanner import ProjectScan


class SpringBatchDetector(Detector):
    name = "spring_batch"

    def supports(self, project: ProjectScan) -> bool:
        return "spring_batch" in project.technology_candidates

    def detect(self, project: ProjectScan) -> DetectionResult:
        result = DetectionResult()
        for file in project.by_suffix(".java", ".kt"):
            assignments = java_assignments(file.content)
            if not re.search(r"ItemReader|ItemWriter|JdbcCursorItemReader|JdbcBatchItemWriter|springframework\.batch", file.content):
                continue
            for match in re.finditer(r"\.sql\s*\(\s*(\"(?:\\.|[^\"\\])*\"|\w+)\s*\)", file.content, re.S):
                argument = match.group(1)
                expression = assignments.get(argument, (argument, 1))[0]
                sql = compact_sql(decode_java_strings(expression))
                if not re.search(r"\b(select|insert|update|delete|merge|with)\b", sql, re.I):
                    continue
                line = file.content[:match.start()].count("\n") + 1
                location = CodeLocation(file.relative_path, line)
                unit_id = sql_id(self.name, file.relative_path, line, sql)
                kind = statement_kind(sql)
                result.sql_units.append(SqlUnit(unit_id, sql, kind, location, self.name, {"builder_method": "sql"}))
                result.method_calls.append(MethodCall(None, "sql", argument, location))
                tables = source_tables(sql)
                if kind == "select" or tables:
                    result.source_read_operations.append(SourceReadOperation(tables, selected_expressions(sql), location, unit_id, "sql"))
                table, columns, operation = write_target(sql)
                if table:
                    result.target_write_operations.append(TargetWriteOperation(table, columns, operation, location, unit_id, "sql"))
        return result
