from __future__ import annotations

import argparse
from pathlib import Path

from src.application import analyze
from src.llm.mapping_agent import EvidenceMappingModel, LocalChatOpenAIMappingModel


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Spring Boot DB migration gap mapping agent")
    parser.add_argument("--input", type=Path, default=ROOT / "test", help="분석할 Spring Boot 프로젝트가 들어 있는 폴더")
    parser.add_argument("--output", type=Path, default=ROOT / "output", help="Gap Mapping 보고서 출력 폴더")
    parser.add_argument("--no-llm", action="store_true", help="LLM 호출 없이 정적으로 증명되는 SQL 매핑만 생성")
    parser.add_argument("--model", help="로컬 sLLM model ID; 기본값은 SLLM_MODEL")
    parser.add_argument("--base-url", help="OpenAI-compatible endpoint; 기본값은 SLLM_BASE_URL 또는 http://localhost:8000/v1")
    parser.add_argument("--api-key", help="로컬 서버가 인증을 요구할 때 사용할 API key")
    parser.add_argument(
        "--structured-output",
        choices=["json_mode", "json_schema", "function_calling", "raw"],
        help="서버가 지원하는 구조화 출력 방식; 기본값은 SLLM_STRUCTURED_OUTPUT_METHOD 또는 json_mode",
    )
    args = parser.parse_args()
    try:
        model = EvidenceMappingModel() if args.no_llm else LocalChatOpenAIMappingModel(
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            structured_output_method=args.structured_output,
        )
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
