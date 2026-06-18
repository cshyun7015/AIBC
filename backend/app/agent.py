import os
import json
from dotenv import load_dotenv, find_dotenv
from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, START, END

# .env 파일 로드 (부모 디렉터리까지 탐색)
load_dotenv(find_dotenv(), override=True)

# ==========================================
# 1. 상태(State) 정의
# ==========================================
class IncidentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    incident_report: str
    layer: str
    triage_reason: str
    search_queries: List[str]
    rag_context: str
    root_cause: str
    solution: str
    confidence: str
    risk_level: str
    test_scenario: str
    playwright_code: str
    retry_count: int

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
        api_key=os.environ.get("AOAI_API_KEY"),
        azure_endpoint=os.environ.get("AOAI_ENDPOINT"),
        azure_deployment=os.environ.get("AOAI_DEPLOY_GPT4O", "aitl-prd-gpt-4o"),
        api_version="2024-02-15-preview",
        temperature=0.2 
    ).bind(response_format={"type": "json_object"})

    embeddings = AzureOpenAIEmbeddings(
        api_key=os.environ.get("AOAI_API_KEY"),
        azure_endpoint=os.environ.get("AOAI_ENDPOINT"),
        azure_deployment=os.environ.get("AOAI_DEPLOY_EMBED_3_SMALL", "aitl-prd-text-embedding-3-small"),
        api_version="2023-05-15"
    )

    # [RAG 환경 셋업 - PDF 로드 및 FAISS 로컬 저장소 활용]
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

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
# 2. 도구(Tools) 정의
# ==========================================
@tool
def search_knowledge_base(query: str) -> str:
    """과거 장애 처리 이력, 가이드라인 등 지식베이스를 검색합니다."""
    if USE_MOCK_LLM or 'vector_db' not in globals():
        return "검색 결과 없음 (Mock 환경 또는 Vector DB 미연결)"
    docs = vector_db.similarity_search(query, k=2)
    return "\n".join([f"- {doc.page_content}" for doc in docs])

@tool
def check_server_logs(layer: str) -> str:
    """특정 레이어(BACKEND, DB 등)의 최근 에러 로그를 조회합니다."""
    return f"[{layer}] Error 500: Database connection timeout at 10:24 AM."

tools = [search_knowledge_base, check_server_logs]

from langchain_core.messages import ToolMessage

def execute_tools_node(state: IncidentState):
    messages = state.get("messages", [])
    if not messages:
        return {"messages": []}
        
    last_message = messages[-1]
    tool_messages = []
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            
            tool_result = f"Error: Tool {tool_name} not found"
            for t in tools:
                if getattr(t, "name", "") == tool_name:
                    try:
                        tool_result = str(t.invoke(tool_args))
                    except Exception as e:
                        tool_result = f"Error: {str(e)}"
                    break
                    
            tool_messages.append(ToolMessage(
                content=tool_result,
                name=tool_name,
                tool_call_id=tool_call.get("id", "")
            ))
            
    return {"messages": tool_messages}

# ==========================================
# 3. 에이전트(Nodes) 정의
# ==========================================
def triage_node(state: IncidentState):
    print("▶️ [DEBUG] Entered triage_node")
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
    messages = prompt.format_messages(incident=state["incident_report"])
    response = llm.invoke(messages)
    result = json.loads(response.content)
    
    return {
        "layer": result.get("layer", "UNKNOWN"),
        "triage_reason": result.get("reason", ""),
        "search_queries": result.get("search_queries", [])
    }

def root_cause_node(state: IncidentState):
    messages = state.get("messages", [])
    
    # 도구 응답 이후 재진입한 경우가 아니면 재시도 카운트 증가
    if messages and hasattr(messages[-1], 'type') and messages[-1].type == 'tool':
        current_retry = state.get("retry_count", 0)
    else:
        current_retry = state.get("retry_count", 0) + 1

    llm_with_tools = llm.bind_tools(tools) if not USE_MOCK_LLM else None
    
    sys_prompt = load_prompt("root_cause_agent.txt")
    
    if not messages or current_retry > 1 and not hasattr(messages[-1], 'type') or (messages and messages[-1].type != 'tool' and current_retry > state.get("retry_count", 0)):
        from langchain_core.messages import SystemMessage, HumanMessage
        # 만약 재시도라면 메시지 끝에 재분석 요청 추가
        if current_retry > 1:
            messages.append(HumanMessage(content="이전 분석 결과의 신뢰도가 낮습니다. 검색 도구나 로그 도구를 다시 활용하여 원인을 더 깊이 파악하고 JSON 형태로 다시 응답하세요."))
        else:
            messages = [
                SystemMessage(content=sys_prompt),
                HumanMessage(content=f"장애 현상: {state.get('incident_report')}\n분류 레이어: {state.get('layer')}\n\n* 지시사항: 필요한 경우 도구를 호출하여 원인을 분석하고, 최종 결과는 반드시 JSON 형태로 응답하세요. (키: root_cause, solution, confidence, risk_level)")
            ]

    if USE_MOCK_LLM:
        return {
            "root_cause": "[MOCK] DB 커넥션 풀 고갈",
            "solution": "[MOCK] DB 커넥션 풀을 늘리거나 재시작합니다.",
            "confidence": "85%",
            "risk_level": "High",
            "retry_count": current_retry
        }
    
    response = llm_with_tools.invoke(messages)
    
    if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
        return {"messages": [response], "retry_count": current_retry}
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        result = json.loads(content)
    except:
        result = {}
    
    return {
        "messages": [response],
        "root_cause": result.get("root_cause", "파싱 실패"),
        "solution": result.get("solution", "파싱 실패"),
        "confidence": str(result.get("confidence", "0%")),
        "risk_level": result.get("risk_level", "Unknown"),
        "retry_count": current_retry
    }

def qa_master_node(state: IncidentState):
    if USE_MOCK_LLM:
        mock_scenario = "1. 브라우저 구동 후 localhost 진입\n2. 입력 폼에 더미 장애 증상 작성 후 전송\n3. 화면에 분석 결과(원인, 해결책 등)가 모두 렌더링되었는지 10초 내 확인"
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
            "test_scenario": mock_scenario,
            "playwright_code": mock_code
        }

    sys_prompt = load_prompt("qa_master_agent.txt")
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}\n적용된 해결책: {solution}")
    ])
    
    messages = prompt.format_messages(
        incident=state["incident_report"], 
        solution=state["solution"]
    )
    response = llm.invoke(messages)
    result = json.loads(response.content)
    
    return {
        "test_scenario": result.get("test_scenario", ""),
        "playwright_code": result.get("playwright_code", "")
    }

def escalation_node(state: IncidentState):
    return {
        "root_cause": "자동 분석 실패",
        "solution": "신뢰도가 너무 낮아 자동 분석을 완료할 수 없습니다. 수동 개입 및 추가 조사가 필요합니다.",
        "risk_level": "Critical"
    }

# ==========================================
# 3.5 조건부 라우팅 함수 (Conditional Edges)
# ==========================================
def route_after_triage(state: IncidentState) -> str:
    layer = state.get("layer", "UNKNOWN")
    if layer.upper() == "UNKNOWN":
        return "escalation_node"
    return "root_cause_analysis"

def route_after_analysis(state: IncidentState) -> str:
    import re
    confidence_str = str(state.get("confidence", "0%"))
    retry_count = state.get("retry_count", 0)
    
    # 숫자 파싱
    digits = re.findall(r'\d+', confidence_str)
    confidence = int(digits[0]) if digits else 0
    
    if confidence < 70 and retry_count < 2:
        return "root_cause_analysis"
    elif confidence < 70 and retry_count >= 2:
        return "escalation_node"
    else:
        return "qa_master"

def custom_tools_condition(state: IncidentState) -> str:
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], 'tool_calls') and len(messages[-1].tool_calls) > 0:
        return "tools"
    return route_after_analysis(state)

# ==========================================
# 4. 그래프 컴파일 (FastAPI에서 호출할 객체)
# ==========================================
workflow = StateGraph(IncidentState)
workflow.add_node("triage", triage_node)
workflow.add_node("root_cause_analysis", root_cause_node)
workflow.add_node("tools", execute_tools_node)
workflow.add_node("qa_master", qa_master_node)
workflow.add_node("escalation_node", escalation_node)

workflow.add_edge(START, "triage")
workflow.add_conditional_edges("triage", route_after_triage)
workflow.add_conditional_edges("root_cause_analysis", custom_tools_condition)
workflow.add_edge("tools", "root_cause_analysis")
workflow.add_edge("escalation_node", END)
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