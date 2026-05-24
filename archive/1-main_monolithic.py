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