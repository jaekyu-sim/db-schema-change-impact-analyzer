from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from src.detectors.jdbc_template_detector import JdbcTemplateDetector
from src.detectors.mybatis_detector import MyBatisDetector
from src.detectors.string_sql_detector import StringSqlDetector
from src.index.project_index import ProjectIndex
from src.llm.mapping_agent import EvidenceMappingModel, MappingAgent
from src.output.report_writer import ReportWriter
from src.scanner.project_scanner import ProjectScanner
from src.workflow.langgraph_workflow import MappingWorkflow


PROJECT_MARKERS = {"pom.xml", "build.gradle", "build.gradle.kts"}


@dataclass(frozen=True)
class AnalysisResult:
    project: Path
    target_column_count: int
    reports: tuple[Path, Path, Path]


def discover_projects(input_directory: str | Path) -> list[Path]:
    root = Path(input_directory).resolve()
    if not root.is_dir():
        raise ValueError(f"분석 대상 폴더가 없습니다: {root}")
    if any((root / marker).is_file() for marker in PROJECT_MARKERS):
        return [root]
    projects = [
        child for child in sorted(root.iterdir())
        if child.is_dir() and any((child / marker).is_file() for marker in PROJECT_MARKERS)
    ]
    if not projects:
        raise ValueError(f"{root} 안에서 pom.xml 또는 build.gradle을 가진 Spring Boot 프로젝트를 찾지 못했습니다.")
    return projects


def analyze(input_directory: str | Path, output_directory: str | Path) -> list[AnalysisResult]:
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    writer = ReportWriter()
    results: list[AnalysisResult] = []
    detectors = [MyBatisDetector(), JdbcTemplateDetector(), StringSqlDetector()]
    workflow = MappingWorkflow(MappingAgent(EvidenceMappingModel()))

    for project_path in discover_projects(input_directory):
        project = ProjectScanner().scan(project_path)
        index = ProjectIndex.build(project, detectors)
        mappings = workflow.run(project, index)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", project_path.name)
        base = output / f"{safe_name}_gap_mapping"
        markdown, csv_path, excel = base.with_suffix(".md"), base.with_suffix(".csv"), base.with_suffix(".xlsx")
        writer.write_markdown(markdown, mappings)
        writer.write_csv(csv_path, mappings)
        writer.write_excel(excel, mappings)
        results.append(AnalysisResult(project_path, len(index.target_columns()), (markdown, csv_path, excel)))
    return results

