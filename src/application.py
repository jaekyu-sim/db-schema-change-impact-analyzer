from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from time import perf_counter

from src.detectors.jdbc_template_detector import JdbcTemplateDetector
from src.detectors.jpa_detector import JpaDetector
from src.detectors.mybatis_detector import MyBatisDetector
from src.detectors.querydsl_detector import QueryDslDetector
from src.detectors.spring_batch_detector import SpringBatchDetector
from src.detectors.string_sql_detector import StringSqlDetector
from src.index.project_index import ProjectIndex
from src.llm.mapping_agent import EvidenceMappingModel, MappingAgent, MappingModel
from src.output.report_writer import ReportWriter
from src.scanner.project_scanner import ProjectScanner
from src.workflow.langgraph_workflow import MappingWorkflow


PROJECT_MARKERS = {"pom.xml", "build.gradle", "build.gradle.kts"}
logger = logging.getLogger(__name__)


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
        logger.info("분석 프로젝트 발견: %s", root.name)
        return [root]
    projects = [
        child for child in sorted(root.iterdir())
        if child.is_dir() and any((child / marker).is_file() for marker in PROJECT_MARKERS)
    ]
    if not projects:
        raise ValueError(f"{root} 안에서 pom.xml 또는 build.gradle을 가진 Spring Boot 프로젝트를 찾지 못했습니다.")
    logger.info("분석 프로젝트 %d개 발견: %s", len(projects), ", ".join(project.name for project in projects))
    return projects


def analyze(input_directory: str | Path, output_directory: str | Path, model: MappingModel | None = None) -> list[AnalysisResult]:
    total_started = perf_counter()
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    writer = ReportWriter()
    results: list[AnalysisResult] = []
    detectors = [MyBatisDetector(), JpaDetector(), QueryDslDetector(), JdbcTemplateDetector(), StringSqlDetector(), SpringBatchDetector()]
    workflow = MappingWorkflow(MappingAgent(model or EvidenceMappingModel()))

    projects = discover_projects(input_directory)
    for project_number, project_path in enumerate(projects, start=1):
        project_started = perf_counter()
        logger.info("프로젝트 분석 [%d/%d] 시작: %s", project_number, len(projects), project_path.name)
        project = ProjectScanner().scan(project_path)
        index = ProjectIndex.build(project, detectors)
        if not index.target_columns():
            frameworks = ", ".join(sorted(project.technology_candidates)) or "없음"
            raise ValueError(
                f"{project_path.name}: Target write column을 찾지 못했습니다. "
                f"기술 후보={frameworks}, SQL units={len(index.result.sql_units)}, "
                f"write operations={len(index.result.target_write_operations)}. "
                "지원되지 않는 write 패턴이므로 빈 보고서를 생성하지 않습니다."
            )
        mappings = workflow.run(project, index)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", project_path.name)
        base = output / f"{safe_name}_gap_mapping"
        markdown, csv_path, excel = base.with_suffix(".md"), base.with_suffix(".csv"), base.with_suffix(".xlsx")
        logger.info("Markdown 보고서 저장: %s", markdown)
        writer.write_markdown(markdown, mappings)
        logger.info("CSV 보고서 저장: %s", csv_path)
        writer.write_csv(csv_path, mappings)
        logger.info("Excel 보고서 저장: %s", excel)
        writer.write_excel(excel, mappings)
        results.append(AnalysisResult(project_path, len(index.target_columns()), (markdown, csv_path, excel)))
        logger.info("프로젝트 분석 [%d/%d] 완료: %s | %.2f초", project_number, len(projects), project_path.name, perf_counter() - project_started)
    logger.info("전체 분석 파이프라인 완료: 프로젝트=%d | %.2f초", len(results), perf_counter() - total_started)
    return results
