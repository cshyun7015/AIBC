# 프로젝트 구조화 완료 가이드

AntiGravity ITSM 지능형 인시던트 분석 Agent 프로젝트의 디렉터리 구조화 및 리팩토링이 완료되었습니다. 변경된 구조와 실행 방법을 안내해 드립니다.

## 변경된 디렉터리 구조

흩어져 있던 파일들을 목적에 맞게 재배치했습니다.

```text
/Users/cshyun/Workspace/AIBC/
├── docs/                                    # 기획안 및 제출 문서
│   ├── assignment.md                        # 과제 요구사항
│   ├── answer-01-planning.md                # 기획안
│   ├── answer-02-prompts-and-monolithic.md  # 프롬프트/단일버전
│   └── answer-03-fastapi-refactoring.md     # 분리버전 가이드
├── app/                                     # 메인 소스 코드
│   ├── main.py                              # FastAPI 서버 진입점
│   ├── agent.py                             # LangGraph 에이전트 코어
│   └── prompts/                             # 에이전트 프롬프트 텍스트
│       ├── triage_agent.txt                 # Triage 에이전트 프롬프트
│       ├── root_cause_agent.txt             # Root-Cause 에이전트 프롬프트
│       └── qa_master_agent.txt              # QA-Master 에이전트 프롬프트
└── archive/                                 # 구버전 백업
    └── 1-main_monolithic.py
```

## 주요 리팩토링 내용

1. **프롬프트 분리 및 동적 로드**: 
   `app/agent.py` 내부에 하드코딩되어 있던 시스템 프롬프트들을 분리하여 `app/prompts/*.txt` 파일로 저장했습니다. 코드 내부에는 `load_prompt` 유틸리티 함수를 추가하여 실행 시 이 텍스트 파일들을 동적으로 읽어오도록 수정했습니다. 이를 통해 코드를 수정하지 않고도 프롬프트를 쉽게 튜닝할 수 있습니다.

2. **모듈 import 경로 수정**: 
   `app/main.py`에서 `agent.py`를 참조할 때, 명시적으로 `from app.agent import itsm_agent_app`를 사용하도록 수정하여, 최상위 경로에서 서버를 구동할 때 발생할 수 있는 Import 에러를 방지했습니다.

## 서버 실행 방법

모든 소스 파일이 `app` 폴더로 이동되었으므로, 터미널에서 아래 명령어를 통해 서버를 실행하실 수 있습니다. (FastAPI, Langchain 등의 패키지가 설치되어 있어야 합니다.)

```bash
# 프로젝트 최상단 디렉터리(/Users/cshyun/Workspace/AIBC)에서 실행
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> [!TIP]
> `--reload` 옵션을 사용하면 `app/prompts/` 내부의 텍스트를 수정하거나 코드를 변경했을 때 서버가 자동으로 재시작되어 매우 편리합니다.
