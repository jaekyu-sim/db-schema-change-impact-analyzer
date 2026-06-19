from __future__ import annotations

import re

from src.detectors.base import CodeLocation, DetectionResult, Detector, MethodCall, SourceReadOperation, TargetWriteOperation
from src.detectors.jpa_detector import JpaDetector
from src.scanner.project_scanner import ProjectScan


class QueryDslDetector(Detector):
    name = "querydsl"

    def supports(self, project: ProjectScan) -> bool:
        return "querydsl" in project.technology_candidates

    def detect(self, project: ProjectScan) -> DetectionResult:
        result = DetectionResult()
        entities = {}
        for file in project.by_suffix(".java", ".kt"):
            entity = JpaDetector._entity_mapping(file.relative_path, file.content)
            if entity:
                entities[entity.entity] = entity

        for file in project.by_suffix(".java", ".kt"):
            q_variables = {
                match.group(2): match.group(1)[1:]
                for match in re.finditer(r"\b(Q\w+)\s+(\w+)\s*=", file.content)
            }
            for match in re.finditer(r"\.(?:update|insert)\s*\(\s*(\w+)\s*\)(.*?)\.execute\s*\(\s*\)", file.content, re.S):
                variable, chain = match.groups()
                entity = entities.get(q_variables.get(variable, ""))
                table = entity.table if entity and entity.table else q_variables.get(variable)
                if not table:
                    continue
                fields = re.findall(rf"\.(?:set|columns?)\s*\(\s*{re.escape(variable)}\.(\w+)", chain)
                columns = [entity.fields.get(field, field) if entity else field for field in fields]
                line = file.content[:match.start()].count("\n") + 1
                location = CodeLocation(file.relative_path, line)
                result.target_write_operations.append(TargetWriteOperation(table, list(dict.fromkeys(columns)), "querydsl_write", location, method="execute"))
                result.method_calls.append(MethodCall("queryFactory", "execute", match.group(0), location))

            for match in re.finditer(r"\.select\s*\((.*?)\)\s*\.from\s*\(\s*(\w+)\s*\)", file.content, re.S):
                expressions, variable = match.groups()
                entity = entities.get(q_variables.get(variable, ""))
                table = entity.table if entity and entity.table else q_variables.get(variable)
                if not table:
                    continue
                columns = [value.strip() for value in expressions.split(",") if value.strip()]
                line = file.content[:match.start()].count("\n") + 1
                location = CodeLocation(file.relative_path, line)
                result.source_read_operations.append(SourceReadOperation([table], columns, location, method="querydsl_select"))
                result.method_calls.append(MethodCall("queryFactory", "select", expressions.strip(), location))
        return result
