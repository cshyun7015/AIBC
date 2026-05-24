import os
import json
from typing import TypedDict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, END

# ==========================================
# 1. 상태(State) 정의
# ==========================================
class IncidentState(TypedDict):
    incident_report: str
    layer: str
    triage_reason: str
    search_queries: List[str]
    rag_context: str
    root_cause: str
    solution: str
    playwright_code: str

# ==========================================
# 2. LLM 및 RAG(Vector DB) 초기화
# ==========================================
llm = AzureChatOpenAI(
    azure_deployment=os.environ.get("AOAI_DEPLOY_GPT4O", "aitl-prd-gpt-4o"),
    api_version="2024-02-15-preview",
    temperature=0.2 
).bind(response_format={"type": "json_object"})

embeddings = AzureOpenAIEmbeddings(
    azure_deployment=os.environ.get("AOAI_DEPLOY_EMBED_3_SMALL", "aitl-prd-text-embedding-3-small"),
    api_version="2023-05-15"
)

# [가상의 RAG 환경 셋업] 
# 실제로는 MariaDB의 데이터를 임베딩하여 로컬이나 외부 VectorDB에 저장해둔 상태라고 가정합니다.
# 여기서는 코드가 바로 돌아갈 수 있도록 더미 데이터를 메모리에 올립니다.
dummy_texts = [
    "[티켓 #102] 증상: 요청 조회 500 에러 / 원인: DB Connection Pool 고갈 / 해결: max-lifetime 1800000으로 조정",
    "[티켓 #088] 증상: 프론트엔드 로그인 무반응 / 원인: Redis 세션 만료 / 해결: 세션 타임아웃 연장",
    "[가이드] MSA 환경에서 트랜잭션 락 발생 시 재시도 로직 구현 방법"
]
vector_db = FAISS.from_texts(dummy_texts, embeddings)
retriever = vector_db.as_retriever(search_kwargs={"k": 2})

# ==========================================
# 3. 에이전트(Nodes) 정의
# ==========================================
def triage_node(state: IncidentState):
    sys_prompt = "당신은 AntiGravity ITSM 시스템의 L1 헬프데스크(Triage) 에이전트입니다. 증상을 분석하고 'FRONTEND', 'BACKEND', 'DATABASE', 'INFRA' 중 하나로 분류하세요. 검색용 키워드 2개를 추출하세요."
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}")
    ])
    
    # JSON 출력을 강제하여 파싱 오류 방지
    response = (prompt | llm).invoke({"incident": state["incident_report"]})
    result = json.loads(response.content)
    
    return {
        "layer": result.get("layer", "UNKNOWN"),
        "triage_reason": result.get("reason", ""),
        "search_queries": result.get("search_queries", [])
    }

def root_cause_node(state: IncidentState):
    # RAG: Triage가 뽑아준 키워드를 바탕으로 Vector DB 검색
    search_queries = state.get("search_queries", [])
    combined_query = " ".join(search_queries) if search_queries else state["incident_report"]
    
    docs = retriever.invoke(combined_query)
    rag_context = "\n".join([f"- {doc.page_content}" for doc in docs])
    
    sys_prompt = "당신은 AntiGravity 프로젝트의 L2 시스템 아키텍트입니다. 장애 현상과 RAG 검색 결과를 바탕으로 근본 원인을 분석하고 해결책을 제시하세요."
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}\n분류 레이어: {layer}\n[과거 인시던트 및 가이드 검색 결과]\n{context}")
    ])
    
    response = (prompt | llm).invoke({
        "incident": state["incident_report"], 
        "layer": state["layer"], 
        "context": rag_context
    })
    result = json.loads(response.content)
    
    return {
        "rag_context": rag_context,
        "root_cause": result.get("root_cause", "분석 실패"),
        "solution": result.get("solution", "해결책 없음")
    }

def qa_master_node(state: IncidentState):
    sys_prompt = "당신은 AntiGravity 전용 'frontend-ui-qa-master' 에이전트입니다. 해결책이 적용된 후 정상 작동을 확인하기 위한 Playwright(TypeScript) E2E 테스트 시나리오와 코드를 작성하세요."
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}\n적용된 해결책: {solution}")
    ])
    
    response = (prompt | llm).invoke({
        "incident": state["incident_report"], 
        "solution": state["solution"]
    })
    result = json.loads(response.content)
    
    return {
        "playwright_code": result.get("playwright_code", "// Code generation failed")
    }

# ==========================================
# 4. 그래프 컴파일 (FastAPI에서 호출할 객체)
# ==========================================
workflow = StateGraph(IncidentState)
workflow.add_node("triage", triage_node)
workflow.add_node("root_cause", root_cause_node)
workflow.add_node("qa_master", qa_master_node)

workflow.set_entry_point("triage")
workflow.add_edge("triage", "root_cause")
workflow.add_edge("root_cause", "qa_master")
workflow.add_edge("qa_master", END)

itsm_agent_app = workflow.compile()