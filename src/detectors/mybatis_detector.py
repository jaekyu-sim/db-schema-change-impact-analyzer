from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from src.detectors.base import (
    CodeLocation, DetectionResult, Detector, MethodCall, SourceReadOperation,
    SqlUnit, TargetWriteOperation, VariableAssignment,
)
from src.detectors.sql_utils import compact_sql, selected_expressions, source_tables, sql_id, statement_kind, write_target
from src.scanner.project_scanner import ProjectScan


class MyBatisDetector(Detector):
    name = "mybatis"
    STATEMENTS = {"select", "insert", "update", "delete"}

    def supports(self, project: ProjectScan) -> bool:
        return "mybatis" in project.technology_candidates or any(self._is_mapper(f.content) for f in project.by_suffix(".xml"))

    def detect(self, project: ProjectScan) -> DetectionResult:
        result = DetectionResult()
        for file in project.by_suffix(".xml"):
            if not self._is_mapper(file.content):
                continue
            try:
                root = ET.fromstring(file.content)
            except ET.ParseError:
                continue
            namespace = root.attrib.get("namespace")
            fragments = {
                element.attrib["id"]: element
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1].lower() == "sql" and element.attrib.get("id")
            }
            for element in root.iter():
                tag = element.tag.rsplit("}", 1)[-1].lower()
                if tag not in self.STATEMENTS:
                    continue
                statement_id = element.attrib.get("id", "<anonymous>")
                marker = f'id="{statement_id}"'
                line = file.content[:file.content.find(marker)].count("\n") + 1 if marker in file.content else 1
                sql = compact_sql(self._render_sql(element, fragments))
                if not sql:
                    continue
                unit_id = sql_id(self.name, file.relative_path, line, sql)
                location = CodeLocation(file.relative_path, line)
                kind = statement_kind(sql)
                result.sql_units.append(SqlUnit(unit_id, sql, kind, location, self.name, {
                    "namespace": namespace, "statement_id": statement_id,
                    "parameter_type": element.attrib.get("parameterType"),
                    "result_type": element.attrib.get("resultType"),
                }))
                result.method_calls.append(MethodCall(namespace, statement_id, element.attrib.get("parameterType", ""), location))
                for bind in element.iter():
                    if bind.tag.rsplit("}", 1)[-1].lower() == "bind" and bind.attrib.get("name"):
                        result.variable_assignments.append(VariableAssignment(bind.attrib["name"], bind.attrib.get("value", ""), location))
                self._add_operations(result, unit_id, location, sql, kind)
        return result

    @classmethod
    def _render_sql(cls, element: ET.Element, fragments: dict[str, ET.Element]) -> str:
        parts = [element.text or ""]
        for child in element:
            tag = child.tag.rsplit("}", 1)[-1].lower()
            if tag == "include" and child.attrib.get("refid") in fragments:
                parts.append(cls._render_sql(fragments[child.attrib["refid"]], fragments))
            else:
                parts.append(cls._render_sql(child, fragments))
            parts.append(child.tail or "")
        return " ".join(parts)

    @staticmethod
    def _is_mapper(content: str) -> bool:
        return bool(re.search(r"<(?:\w+:)?mapper\b", content, re.I))

    @staticmethod
    def _add_operations(result: DetectionResult, unit_id: str, location: CodeLocation, sql: str, kind: str) -> None:
        tables = source_tables(sql)
        if kind == "select" or tables:
            result.source_read_operations.append(SourceReadOperation(tables, selected_expressions(sql), location, unit_id))
        table, columns, operation = write_target(sql)
        if table:
            result.target_write_operations.append(TargetWriteOperation(table, columns, operation, location, unit_id))
