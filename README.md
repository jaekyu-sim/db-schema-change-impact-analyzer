# Spring Boot Data Migration Gap Mapping Agent

## 폴더 구조

분석할 Spring Boot 프로젝트를 이 저장소의 `test` 폴더 아래에 둡니다.

```text
python-program-analysis-agent-springboot-data/
├─ main.py
├─ test/
│  └─ my-migration-project/
│     ├─ pom.xml 또는 build.gradle
│     └─ src/
└─ output/
```

`test` 아래에 여러 Spring Boot 프로젝트를 두면 각각 분석합니다. 분석 대상 프로젝트는 `.gitignore`에 의해 이 에이전트 저장소의 커밋에서 제외됩니다.

## 실행

최초 한 번 의존성을 설치합니다.

```powershell
python -m pip install -e .
```

OpenAI API 키와 사용할 모델을 설정한 뒤 실행합니다.

```powershell
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="gpt-5-mini"
python main.py
```

저장소 루트에서 실행하면 `test/` 아래 프로젝트를 모두 분석합니다. LLM은 전체 프로젝트가 아니라 Target 컬럼별 관련 코드 컨텍스트만 전달받습니다.

LLM 연결 전 Detector가 Target write를 찾는지만 점검하려면 다음 명령을 사용합니다.

```powershell
python main.py --no-llm
```

결과는 프로젝트별로 `output` 폴더에 생성됩니다.

```text
output/
├─ my-migration-project_gap_mapping.md
├─ my-migration-project_gap_mapping.csv
└─ my-migration-project_gap_mapping.xlsx
```

각 행은 Target DB 컬럼 하나를 나타내며 `source_table`, `source_column`, `source_expression`과 근거를 포함합니다. `mapping_status`는 다음 중 하나입니다.

- `MAPPED`: Source table/column까지 확인됨
- `DERIVED`: 상수, 함수, 조합식 등 expression으로 확인됨
- `UNRESOLVED`: 수집한 코드 근거와 확장 재시도로도 확인되지 않음

현재 Detector는 MyBatis XML, JPA Repository/Native Query, QueryDSL select/update, JdbcTemplate, NamedParameterJdbcTemplate, Java/Kotlin 문자열 SQL, 독립 SQL 파일, Spring Batch JDBC reader/writer 패턴을 수집합니다. 기술 후보 탐지는 실행 우선순위 참고용이며 Detector 실행을 차단하지 않습니다.

기본 경로 대신 다른 폴더를 지정할 수도 있습니다.

```powershell
python main.py --input C:\work\migration-projects --output C:\work\gap-output
```

## 테스트

```powershell
python -m unittest discover -s tests -v
```

기본 실행은 OpenAI Responses API를 실제 호출합니다. `--no-llm` 모드는 SQL에 명시된 `INSERT ... SELECT`의 위치 관계처럼 정적으로 증명되는 lineage만 처리합니다.
