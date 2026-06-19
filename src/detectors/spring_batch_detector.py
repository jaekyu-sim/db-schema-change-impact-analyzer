from src.detectors.base import DetectionResult, Detector
from src.scanner.project_scanner import ProjectScan


class SpringBatchDetector(Detector):
    name = "spring_batch"

    def supports(self, project: ProjectScan) -> bool:
        return "spring_batch" in project.technology_candidates

    def detect(self, project: ProjectScan) -> DetectionResult:
        return DetectionResult()

