from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


TEXT_SUFFIXES = {
    ".java", ".kt", ".xml", ".yml", ".yaml", ".properties", ".gradle",
    ".kts", ".sql", ".py", ".md", ".txt",
}
IGNORED_DIRECTORIES = {".git", ".idea", ".gradle", "build", "target", "node_modules", "__pycache__"}


@dataclass(frozen=True)
class ProjectFile:
    path: Path
    relative_path: str
    content: str


@dataclass
class ProjectScan:
    root: Path
    files: list[ProjectFile]
    technology_candidates: set[str] = field(default_factory=set)
    package_names: set[str] = field(default_factory=set)

    def by_suffix(self, *suffixes: str) -> list[ProjectFile]:
        wanted = {suffix.lower() for suffix in suffixes}
        return [item for item in self.files if item.path.suffix.lower() in wanted]


class ProjectScanner:
    """Reads a project once and records coarse technology hints without committing to them."""

    TECH_HINTS = {
        "mybatis": ("mybatis", "@mapper", "sqlsession"),
        "jpa": ("spring-boot-starter-data-jpa", "@entity", "jparepository"),
        "jdbc_template": ("jdbctemplate", "namedparameterjdbctemplate", "spring-jdbc"),
        "spring_batch": ("spring-batch", "itemreader", "itemwriter", "itemprocessor"),
        "querydsl": ("querydsl", "jpaqueryfactory"),
    }

    def scan(self, root: str | Path) -> ProjectScan:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise ValueError(f"Project root is not a directory: {root_path}")

        files: list[ProjectFile] = []
        packages: set[str] = set()
        combined_parts: list[str] = []
        for path in sorted(root_path.rglob("*")):
            if not path.is_file() or any(part in IGNORED_DIRECTORIES for part in path.parts):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"pom.xml", "build.gradle"}:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(root_path).as_posix()
            files.append(ProjectFile(path, relative, content))
            combined_parts.append(content.lower())
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("package "):
                    packages.add(stripped[8:].rstrip(";"))

        combined = "\n".join(combined_parts)
        technologies = {
            name for name, hints in self.TECH_HINTS.items() if any(hint in combined for hint in hints)
        }
        return ProjectScan(root_path, files, technologies, packages)

