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
# Helper: 프롬프트 로드
# ==========================================
def load_prompt(filename: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, "prompts", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()

# ==========================================
# 2. LLM 및 RAG(Vector DB) 초기화
# ==========================================
USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "false").lower() == "true"

if not USE_MOCK_LLM:
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("AOAI_DEPLOY_GPT4O", "aitl-prd-gpt-4o"),
        api_version="2024-02-15-preview",
        temperature=0.2 
    ).bind(response_format={"type": "json_object"})

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=os.environ.get("AOAI_DEPLOY_EMBED_3_SMALL", "aitl-prd-text-embedding-3-small"),
        api_version="2023-05-15"
    )

    # [RAG 환경 셋업 - PDF 로드 및 FAISS 로컬 저장소 활용]
    import os
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    base_dir = os.path.dirname(os.path.abspath(__file__))
    faiss_index_path = os.path.join(base_dir, "faiss_index")
    pdf_path = os.path.join(base_dir, "data", "incident_tickets_for_rag.pdf")

    if os.path.exists(faiss_index_path):
        print("✅ 기존 FAISS 인덱스를 로드합니다...")
        vector_db = FAISS.load_local(faiss_index_path, embeddings, allow_dangerous_deserialization=True)
    else:
        print("🚀 PDF 파일을 읽어 새로운 FAISS 인덱스를 생성합니다...")
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
            
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(docs)
        
        vector_db = FAISS.from_documents(splits, embeddings)
        vector_db.save_local(faiss_index_path)
        print("✅ FAISS 인덱스 생성 및 로컬 저장이 완료되었습니다.")
        
    retriever = vector_db.as_retriever(search_kwargs={"k": 2})
else:
    llm = None
    retriever = None

# ==========================================
# 3. 에이전트(Nodes) 정의
# ==========================================
def triage_node(state: IncidentState):
    if USE_MOCK_LLM:
        return {
            "layer": "BACKEND",
            "triage_reason": "[MOCK] 장애 내용 분석 결과 백엔드 서버 로직 또는 DB 오류로 추정됩니다.",
            "search_queries": ["500 에러", "요청 조회 실패"]
        }
        
    sys_prompt = load_prompt("triage_agent.txt")
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
    if USE_MOCK_LLM:
        return {
            "rag_context": "[MOCK] [과거 티켓] 증상: 요청 조회 500 에러 / 원인: DB Connection Pool 고갈",
            "root_cause": "[MOCK] 과거 유사 인시던트 조회 결과, MariaDB 트랜잭션 락 또는 Connection Pool 고갈로 인한 백엔드 타임아웃이 발생했습니다.",
            "solution": "[MOCK] DB Connection Pool의 max-lifetime을 1800000(30분)으로 조정하고, 타임아웃 발생 시 재시도(Retry) 로직을 추가해야 합니다."
        }

    # RAG: Triage가 뽑아준 키워드를 바탕으로 Vector DB 검색
    search_queries = state.get("search_queries", [])
    combined_query = " ".join(search_queries) if search_queries else state["incident_report"]
    
    docs = retriever.invoke(combined_query)
    rag_context = "\n".join([f"- {doc.page_content}" for doc in docs])
    
    sys_prompt = load_prompt("root_cause_agent.txt")
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
    if USE_MOCK_LLM:
        mock_code = """// [MOCK] Playwright Test Code
import { test, expect } from '@playwright/test';

test('요청 등록 및 조회 라이프사이클 검증 테스트', async ({ page }) => {
  await page.goto('http://localhost');
  
  // 1. 요청 등록
  await page.fill('textarea[placeholder*="장애 현상을"]', '요청 등록 테스트');
  await page.click('button:has-text("인시던트 분석 시작")');
  
  // 2. 결과 출력 대기
  await expect(page.locator('.result-card')).toHaveCount(3, { timeout: 10000 });
  await expect(page.locator('text=분석 요약')).toBeVisible();
});
"""
        return {
            "playwright_code": mock_code
        }

    sys_prompt = load_prompt("qa_master_agent.txt")
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
workflow.add_node("root_cause_analysis", root_cause_node)
workflow.add_node("qa_master", qa_master_node)

workflow.set_entry_point("triage")
workflow.add_edge("triage", "root_cause_analysis")
workflow.add_edge("root_cause_analysis", "qa_master")
workflow.add_edge("qa_master", END)

itsm_agent_app = workflow.compile()

# 워크플로우 이미지 생성 및 저장 (FastAPI 서빙용)
try:
    png_bytes = itsm_agent_app.get_graph().draw_mermaid_png()
    graph_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph.png")
    with open(graph_path, "wb") as f:
        f.write(png_bytes)
    print(f"✅ LangGraph 워크플로우 이미지가 생성되었습니다: {graph_path}")
except Exception as e:
    print(f"⚠️ LangGraph 워크플로우 이미지 생성 실패: {e}")