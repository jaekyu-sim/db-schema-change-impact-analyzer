from __future__ import annotations

import argparse
from pathlib import Path

from src.application import analyze
from src.llm.mapping_agent import EvidenceMappingModel, OpenAIResponsesMappingModel


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Spring Boot DB migration gap mapping agent")
    parser.add_argument("--input", type=Path, default=ROOT / "test", help="분석할 Spring Boot 프로젝트가 들어 있는 폴더")
    parser.add_argument("--output", type=Path, default=ROOT / "output", help="Gap Mapping 보고서 출력 폴더")
    parser.add_argument("--no-llm", action="store_true", help="LLM 호출 없이 정적으로 증명되는 SQL 매핑만 생성")
    parser.add_argument("--model", help="OpenAI model ID; 기본값은 OPENAI_MODEL 또는 gpt-5-mini")
    args = parser.parse_args()
    try:
        model = EvidenceMappingModel() if args.no_llm else OpenAIResponsesMappingModel(model=args.model)
        results = analyze(args.input, args.output, model=model)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    for result in results:
        print(f"[{result.project.name}] target columns: {result.target_column_count}")
        for report in result.reports:
            print(f"  - {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
