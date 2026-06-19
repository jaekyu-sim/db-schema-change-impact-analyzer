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

저장소 루트에서 다음 명령을 실행합니다.

```powershell
python main.py
```

결과는 프로젝트별로 `output` 폴더에 생성됩니다.

```text
output/
├─ my-migration-project_gap_mapping.md
├─ my-migration-project_gap_mapping.csv
└─ my-migration-project_gap_mapping.xlsx
```

기본 경로 대신 다른 폴더를 지정할 수도 있습니다.

```powershell
python main.py --input C:\work\migration-projects --output C:\work\gap-output
```

## 테스트

```powershell
python -m unittest discover -s tests -v
```

현재 기본 매핑 모델은 SQL에 명시된 `INSERT ... SELECT`의 위치 관계처럼 정적으로 증명되는 lineage를 처리합니다. 복잡한 서비스/DTO 변환을 추론하려면 `MappingModel` 구현에 실제 LLM 클라이언트를 연결해야 합니다.
