from src.detectors.base import DetectionResult, Detector
from src.scanner.project_scanner import ProjectScan


class JpaDetector(Detector):
    name = "jpa"

    def supports(self, project: ProjectScan) -> bool:
        return "jpa" in project.technology_candidates

    def detect(self, project: ProjectScan) -> DetectionResult:
        return DetectionResult()

