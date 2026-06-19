from __future__ import annotations

import re

from src.detectors.base import CodeLocation, DetectionResult, Detector, EntityMapping, MethodCall, SourceReadOperation, SqlUnit, TargetWriteOperation
from src.detectors.java_sql import decode_java_strings
from src.detectors.sql_utils import compact_sql, selected_expressions, source_tables, sql_id, statement_kind, write_target
from src.scanner.project_scanner import ProjectScan


class JpaDetector(Detector):
    name = "jpa"

    def supports(self, project: ProjectScan) -> bool:
        return "jpa" in project.technology_candidates

    def detect(self, project: ProjectScan) -> DetectionResult:
        result = DetectionResult()
        entities: dict[str, EntityMapping] = {}
        repositories: dict[str, str] = {}

        for file in project.by_suffix(".java", ".kt"):
            entity = self._entity_mapping(file.relative_path, file.content)
            if entity:
                entities[entity.entity] = entity
                result.entity_mappings.append(entity)
            for match in re.finditer(r"(?:interface|class)\s+(\w+)\s+extends\s+(?:JpaRepository|CrudRepository|PagingAndSortingRepository)\s*<\s*(\w+)", file.content):
                repositories[match.group(1)] = match.group(2)

        for file in project.by_suffix(".java", ".kt"):
            receiver_types = {match.group(2): match.group(1) for match in re.finditer(r"\b(\w+(?:Repository))\s+(\w+)\b", file.content)}
            for match in re.finditer(r"\b(\w+)\s*\.\s*(saveAll|saveAndFlush|save)\s*\((.*?)\)", file.content, re.S):
                repository_type = receiver_types.get(match.group(1))
                entity_name = repositories.get(repository_type or "")
                entity = entities.get(entity_name or "")
                if not entity or not entity.table:
                    continue
                line = file.content[:match.start()].count("\n") + 1
                location = CodeLocation(file.relative_path, line)
                result.method_calls.append(MethodCall(match.group(1), match.group(2), match.group(3).strip(), location))
                result.target_write_operations.append(TargetWriteOperation(entity.table, list(entity.fields.values()), "jpa_save", location, method=match.group(2)))

            for match in re.finditer(r"@Query\s*\((.*?)\)\s*(?:\r?\n\s*)*(?:@\w+(?:\([^)]*\))?\s*)*(?:public\s+|protected\s+|private\s+)?[\w<>, ?]+\s+(\w+)\s*\(", file.content, re.S):
                annotation = match.group(1)
                sql = compact_sql(decode_java_strings(annotation))
                if not re.search(r"\b(select|insert|update|delete|merge|with)\b", sql, re.I):
                    continue
                line = file.content[:match.start()].count("\n") + 1
                location = CodeLocation(file.relative_path, line)
                unit_id = sql_id(self.name, file.relative_path, line, sql)
                kind = statement_kind(sql)
                result.sql_units.append(SqlUnit(unit_id, sql, kind, location, self.name, {"method": match.group(2), "native_query": "nativeQuery" in annotation}))
                tables = source_tables(sql)
                if kind == "select" or tables:
                    result.source_read_operations.append(SourceReadOperation(tables, selected_expressions(sql), location, unit_id, match.group(2)))
                table, columns, operation = write_target(sql)
                if table:
                    result.target_write_operations.append(TargetWriteOperation(table, columns, operation, location, unit_id, match.group(2)))
        return result

    @staticmethod
    def _entity_mapping(path: str, content: str) -> EntityMapping | None:
        if not re.search(r"@(?:Entity|Table)\b", content):
            return None
        class_match = re.search(r"\bclass\s+(\w+)", content)
        if not class_match:
            return None
        table_match = re.search(r"@Table\s*\([^)]*?name\s*=\s*\"([^\"]+)\"", content, re.S)
        table = table_match.group(1) if table_match else class_match.group(1)
        fields: dict[str, str] = {}
        field_pattern = re.compile(r"(?:@Column\s*\([^)]*?name\s*=\s*\"([^\"]+)\"[^)]*\)\s*)?(?:private|protected|public)\s+[\w<>, ?]+\s+(\w+)\s*[;=]", re.S)
        for column, field in field_pattern.findall(content):
            fields[field] = column or field
        line = content[:class_match.start()].count("\n") + 1
        return EntityMapping(class_match.group(1), table, fields, CodeLocation(path, line))
