**AntiGravity ITSM 지능형 인시던트 분석 에이전트**의 실제 구현을 위한 프롬프트 템플릿과 LangGraph 파이썬 코드 뼈대를 작성해 드리겠습니다.

각 에이전트가 역할을 명확히 수행할 수 있도록 프롬프트에 페르소나와 출력 구조(JSON)를 강제하고, LangGraph의 상태(State)를 통해 이 데이터가 유기적으로 흐르도록 설계했습니다.

---

### 1. 에이전트별 시스템 프롬프트 템플릿

시스템의 기술 스택과 환경을 프롬프트 내에 명시하여, 에이전트가 엉뚱한 언어나 도구를 제안하지 않도록 제한하는 것이 중요합니다.

#### 🕵️‍♂️ [Triage Agent] - 초기 분류 에이전트

```text
당신은 AntiGravity ITSM 시스템의 L1 헬프데스크(Triage) 에이전트입니다.
사용자가 입력한 장애 증상을 분석하여 장애가 발생한 시스템 레이어를 분류하는 것이 당신의 역할입니다.

[시스템 환경]
- Frontend: React + TypeScript
- Backend: Spring Boot (MSA)
- Database: MariaDB
- Observability: Grafana, Loki, Promtail

[지시사항]
1. 증상을 읽고 다음 중 하나의 레이어로 분류하세요: 'FRONTEND', 'BACKEND', 'DATABASE', 'INFRA', 'UNKNOWN'
2. 분류한 이유를 1~2문장으로 간략히 작성하세요.
3. Root-Cause 에이전트가 검색할 수 있도록 검색용 핵심 키워드(Search Query)를 2~3개 추출하세요.

[출력 형식 (반드시 JSON으로 응답)]
{
  "layer": "분류된 레이어",
  "reason": "분류 사유",
  "search_queries": ["키워드1", "키워드2"]
}

```

#### 🔍 [Root-Cause Agent] - 원인 분석 에이전트

```text
당신은 AntiGravity 프로젝트의 L2 시스템 아키텍트입니다. 
Triage 에이전트가 분류한 정보와 과거 ITSM 인시던트 티켓(RAG 검색 결과), 그리고 시스템 로그(Loki/Promtail)를 종합하여 근본 원인을 분석하고 해결책을 제시해야 합니다.

[분석 프로세스 - Chain of Thought]
1. [증상 확인]: 사용자의 문제와 Triage 결과를 확인합니다.
2. [과거 이력 대조]: 제공된 RAG 컨텍스트(과거 티켓 및 해결 이력)에서 유사한 사례가 있는지 대조합니다.
3. [원인 추론]: Spring Boot 백엔드 로직, MSA 간 통신, 혹은 MariaDB의 트랜잭션 등 구체적인 원인을 추론합니다.
4. [해결책 도출]: 코드 수정 방안이나 DB/서버 설정 변경 등 구체적인 해결책을 작성합니다.

[출력 형식 (반드시 JSON으로 응답)]
{
  "root_cause": "상세한 원인 분석 내용",
  "solution": "구체적인 해결 방안 (코드 스니펫 또는 설정값 포함)",
  "confidence_score": 0~100 사이의 확신도
}

```

#### 🛠️ [QA-Master Agent] - 품질 검증 에이전트

```text
당신은 AntiGravity 전용 "frontend-ui-qa-master" 에이전트입니다.
Root-Cause 에이전트가 제시한 해결책이 시스템에 적용되었다고 가정하고, 이 문제가 완전히 해결되었는지 검증하기 위한 E2E 테스트 스크립트를 작성하는 것이 당신의 역할입니다.

[제약 사항]
- 테스트 프레임워크: Playwright
- 언어: TypeScript
- 컨테이너 환경에서 실행 가능하도록 CI/CD 친화적으로 작성할 것.
- 단순한 UI 클릭을 넘어 '요청 등록 -> 조회 -> 처리 -> 삭제'와 같은 라이프 사이클 케이스를 포함할 것.

[출력 형식 (반드시 JSON으로 응답)]
{
  "test_scenario": "테스트 시나리오 요약",
  "playwright_code": "작성된 Playwright TypeScript 코드 전체"
}

```

---

### 2. LangGraph 기반 Python 코드 뼈대 (`main.py`)

프롬프트를 바탕으로 에이전트들을 연결하고 데이터(상태)를 주고받는 워크플로우 뼈대입니다.

```python
import json
from typing import TypedDict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END

# ==========================================
# 1. 그래프 상태(State) 정의
# ==========================================
class IncidentState(TypedDict):
    incident_report: str       # 사용자가 입력한 장애 현상
    layer: str                 # Triage가 분류한 레이어 (예: BACKEND)
    triage_reason: str
    search_queries: List[str]  # RAG 검색용 키워드
    rag_context: str           # Vector DB에서 가져온 과거 티켓/로그 정보
    root_cause: str            # Root-Cause 에이전트의 원인 분석
    solution: str              # 해결책
    playwright_code: str       # QA-Master가 생성한 E2E 테스트 코드

# ==========================================
# 2. LLM 초기화 (JSON 출력을 위해 format 설정 가능)
# ==========================================
llm = AzureChatOpenAI(
    azure_deployment="aitl-prd-gpt-4o",
    api_version="2024-02-15-preview",
    temperature=0.2 # 분석의 정확도를 위해 낮은 온도로 설정
).bind(response_format={"type": "json_object"})

# ==========================================
# 3. 노드(에이전트) 정의
# ==========================================
def triage_node(state: IncidentState):
    print("🚦 [Triage Agent] 인시던트 분류 중...")
    # (위에서 정의한 Triage 시스템 프롬프트 사용)
    sys_prompt = "당신은 AntiGravity ITSM 시스템의 L1 헬프데스크(Triage) 에이전트입니다..." 
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"incident": state["incident_report"]})
    result = json.loads(response.content)
    
    return {
        "layer": result.get("layer"),
        "triage_reason": result.get("reason"),
        "search_queries": result.get("search_queries")
    }

def root_cause_node(state: IncidentState):
    print(f"🔍 [Root-Cause Agent] {state['layer']} 레이어 분석 중...")
    
    # [TODO] 실제 구현 시 여기에 FAISS/ChromaDB를 이용한 RAG 검색 로직 추가
    # queries = state["search_queries"]
    # context = my_vector_db.search(queries)
    dummy_rag_context = "과거 티켓 #102: MariaDB Connection Pool 고갈로 인한 Spring Boot 응답 지연 발생 이력 있음."
    
    # (위에서 정의한 Root-Cause 시스템 프롬프트 사용)
    sys_prompt = "당신은 AntiGravity 프로젝트의 L2 시스템 아키텍트입니다..."
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}\nTriage 결과: {layer}\n관련 과거 이력: {context}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "incident": state["incident_report"], 
        "layer": state["layer"], 
        "context": dummy_rag_context
    })
    result = json.loads(response.content)
    
    return {
        "rag_context": dummy_rag_context,
        "root_cause": result.get("root_cause"),
        "solution": result.get("solution")
    }

def qa_master_node(state: IncidentState):
    print("🛠️ [QA-Master Agent] 검증용 E2E(Playwright) 코드 생성 중...")
    
    sys_prompt = "당신은 AntiGravity 전용 'frontend-ui-qa-master' 에이전트입니다..."
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "해결된 장애 현상: {incident}\n적용된 해결책: {solution}\n이 상황을 검증할 라이프 사이클 테스트를 작성하세요.")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "incident": state["incident_report"], 
        "solution": state["solution"]
    })
    result = json.loads(response.content)
    
    return {
        "playwright_code": result.get("playwright_code")
    }

# ==========================================
# 4. 그래프 빌드 및 워크플로우 정의
# ==========================================
workflow = StateGraph(IncidentState)

# 노드 등록
workflow.add_node("triage", triage_node)
workflow.add_node("root_cause", root_cause_node)
workflow.add_node("qa_master", qa_master_node)

# 흐름(Edge) 정의
workflow.set_entry_point("triage")
workflow.add_edge("triage", "root_cause")
workflow.add_edge("root_cause", "qa_master")
workflow.add_edge("qa_master", END)

# 컴파일
itsm_agent_app = workflow.compile()

# ==========================================
# 5. 실행 테스트
# ==========================================
if __name__ == "__main__":
    test_incident = "요청 관리 메뉴에서 '요청 등록' 후 즉시 '요청 조회'를 누르면 간헐적으로 500 에러가 반환됩니다."
    
    final_state = itsm_agent_app.invoke({"incident_report": test_incident})
    
    print("\n" + "="*50)
    print("✅ [최종 인시던트 분석 리포트]")
    print("="*50)
    print(f"- 원인: {final_state.get('root_cause')}")
    print(f"- 해결책: {final_state.get('solution')}")
    print("\n[생성된 Playwright 검증 코드]")
    print(final_state.get('playwright_code'))

```

이 뼈대 코드에서 RAG를 연동하는 `root_cause_node`의 내부 로직을 먼저 구체화해 볼까요, 아니면 이 에이전트 파이프라인을 FastAPI로 감싸서 UI와 통신할 수 있는 API 구조를 먼저 잡아볼까요?
