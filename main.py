from __future__ import annotations

import argparse
from pathlib import Path

from src.application import analyze


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Spring Boot DB migration gap mapping agent")
    parser.add_argument("--input", type=Path, default=ROOT / "test", help="분석할 Spring Boot 프로젝트가 들어 있는 폴더")
    parser.add_argument("--output", type=Path, default=ROOT / "output", help="Gap Mapping 보고서 출력 폴더")
    args = parser.parse_args()
    try:
        results = analyze(args.input, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    for result in results:
        print(f"[{result.project.name}] target columns: {result.target_column_count}")
        for report in result.reports:
            print(f"  - {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

