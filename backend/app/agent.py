import os
import json
from dotenv import load_dotenv, find_dotenv
from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
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
# Helper: 프롬프트 임포트 및 파서
# ==========================================
from app.prompts import TRIAGE_AGENT_PROMPT, ROOT_CAUSE_AGENT_PROMPT, QA_MASTER_AGENT_PROMPT

import re
import datetime

def print_trace(agent_name: str, message: str):
    """콘솔에 시각과 에이전트명을 예쁘게 트레이싱합니다."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 파란색 시각, 노란색 에이전트명으로 콘솔 출력
    print(f"\033[96m[{now}]\033[0m \033[93m[{agent_name}]\033[0m {message}")

def robust_json_parse(content: str) -> dict:
    """LLM이 반환한 텍스트에서 안전하게 JSON을 추출 및 파싱합니다."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            # 마크다운 JSON 블록 추출
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
                return json.loads(content)
            # 순수 중괄호 영역 추출
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        return {}

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

    vector_db = None
    if os.path.exists(faiss_index_path):
        print("✅ 기존 FAISS 인덱스를 로드합니다...")
        try:
            vector_db = FAISS.load_local(faiss_index_path, embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"⚠️ FAISS 인덱스 로드 실패. 인덱스가 깨졌으므로 자동 재빌드합니다: {e}")
            import shutil
            shutil.rmtree(faiss_index_path, ignore_errors=True)
            vector_db = None

    if vector_db is None:
        print("🚀 PDF 파일을 읽어 새로운 FAISS 인덱스를 생성합니다...")
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
            
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        
        # [NEW] 데이터 정제 및 메타데이터 파싱 파이프라인
        from app.preprocessing import DocumentPreprocessor
        preprocessor = DocumentPreprocessor()
        
        # 1. 원본 텍스트 정제
        docs = preprocessor.clean_documents(docs)
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(docs)
        
        # 2. 청크 단위 메타데이터 구조화
        splits = preprocessor.extract_and_inject_metadata(splits)
        
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
from typing import Optional

@tool
def search_knowledge_base(query: str, layer_filter: Optional[str] = None) -> str:
    """
    과거 장애 처리 이력을 검색합니다. 
    layer_filter: 특정 계층(BACKEND, DB, FRONTEND 등)의 문서만 필터링하고 싶을 때 입력합니다.
    """
    if USE_MOCK_LLM or 'vector_db' not in globals():
        return "검색 결과 없음 (Mock 환경 또는 Vector DB 미연결)"
        
    print(f"▶️ [DEBUG] RAG Search Initiated | Query: {query} | Filter: {layer_filter}")

    # 1. Query Expansion (LLM을 이용해 동의어/연관 검색어 생성)
    expanded_queries = [query]
    try:
        expansion_prompt = f"다음 검색어와 관련된 동의어나 장애 시스템 로그 키워드를 2개만 콤마로 구분해서 작성해줘: {query}\n답변 예시: 키워드1, 키워드2"
        from langchain_core.messages import HumanMessage
        expansion_res = llm.invoke([HumanMessage(content=expansion_prompt)])
        extra_queries = [q.strip() for q in expansion_res.content.split(",") if q.strip()]
        expanded_queries.extend(extra_queries[:2]) # 최대 2개 추가
    except Exception as e:
        print(f"⚠️ [DEBUG] Query Expansion Failed: {e}")

    print(f"▶️ [DEBUG] Expanded Queries: {expanded_queries}")

    # 2. 멀티 쿼리 검색, Score Threshold, Metadata Filtering 적용
    # L2 Distance threshold: 작을수록 유사함. 보통 1.0~1.2 사이를 기준으로 삼습니다.
    threshold = 1.2 
    filter_dict = {"layer": layer_filter} if layer_filter else {}
    
    def execute_search(queries, search_filter, max_distance):
        temp_results = {}
        for q in queries:
            try:
                # k=5로 넉넉하게 뽑은 뒤 필터링
                docs_and_scores = vector_db.similarity_search_with_score(q, k=5, filter=search_filter)
                for doc, distance in docs_and_scores:
                    distance = float(distance)
                    if distance <= max_distance:
                        # 중복 문서 제거 (더 작은 거리(점수)를 가진 결과만 유지)
                        if doc.page_content not in temp_results or temp_results[doc.page_content][1] > distance:
                            temp_results[doc.page_content] = (doc, distance)
            except Exception as e:
                print(f"⚠️ [DEBUG] Search Error for '{q}': {e}")
        return temp_results

    all_results = execute_search(expanded_queries, filter_dict, threshold)

    # 3. Fallback Retrieval (검색 결과가 없으면 필터 해제 및 임계치 완화)
    if not all_results:
        print("⚠️ [DEBUG] No results with high confidence. Triggering Fallback Retrieval...")
        all_results = execute_search(expanded_queries, {}, 1.6)

    if not all_results:
        return "검색 결과가 없습니다. 다른 키워드나 넓은 범위로 다시 검색해주세요."

    # 4. Reranking (점수순 오름차순 정렬 후 Top 3 추출)
    sorted_docs = sorted(all_results.values(), key=lambda x: x[1])
    top_docs = [item[0] for item in sorted_docs[:3]]

    # 5. 결과 반환 (메타데이터 포함)
    results = []
    for doc in top_docs:
        meta_str = ", ".join([f"{k}: {v}" for k, v in doc.metadata.items() if k not in ['source', 'page']])
        prefix = f"[{meta_str}]\n" if meta_str else ""
        results.append(f"{prefix}- {doc.page_content}")
        
    final_output = "\n\n".join(results)
    print(f"▶️ [DEBUG] Search complete. Returned {len(top_docs)} docs.")
    return final_output

# [NEW] 모의 로그 및 헬스 체크 상태 생성
try:
    from app.utils.log_generator import generate_logs
    generate_logs()
except Exception as e:
    print(f"⚠️ [DEBUG] Failed to generate mock logs: {e}")

@tool
def check_server_logs(layer: str) -> str:
    """
    특정 계층(BACKEND, DB, FRONTEND 등)의 실제 에러 로그 파일(.log)을 읽어와서 반환합니다.
    """
    layer = layer.upper()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if layer == "BACKEND":
        log_file = os.path.join(base_dir, "data", "logs", "backend.log")
    elif layer == "DB":
        log_file = os.path.join(base_dir, "data", "logs", "db.log")
    elif layer == "FRONTEND":
        log_file = os.path.join(base_dir, "data", "logs", "frontend.log")
    else:
        return f"지원되지 않는 계층입니다: {layer}"
        
    if not os.path.exists(log_file):
        return f"로그 파일을 찾을 수 없습니다: {log_file}"
        
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[-50:]) # 마지막 50줄 반환
    except Exception as e:
        return f"로그 읽기 오류: {e}"

@tool
def check_service_health(service_name: str) -> str:
    """
    특정 서비스(backend, db, frontend)의 실시간 헬스 체크 상태(CPU, 메모리, DB 커넥션 풀 등)를 조회합니다.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    health_file = os.path.join(base_dir, "data", "logs", "health_status.json")
    
    if not os.path.exists(health_file):
        return "상태 정보를 찾을 수 없습니다."
        
    try:
        with open(health_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        target = service_name.lower()
        key_to_check = None
        if "backend" in target or "백엔드" in target:
            key_to_check = "backend_server"
        elif "db" in target or "database" in target or "데이터베이스" in target:
            key_to_check = "database"
        elif "front" in target or "프론트" in target:
            key_to_check = "frontend"
        else:
            return f"알 수 없는 서비스입니다: {service_name}. 가능한 값: backend, db, frontend."
            
        if key_to_check in data:
            return json.dumps(data[key_to_check], indent=2, ensure_ascii=False)
        return "해당 서비스의 상세 상태가 존재하지 않습니다."
    except Exception as e:
        return f"상태 조회 실패: {e}"

tools = [search_knowledge_base, check_server_logs, check_service_health]

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
                        print_trace("Tool Executor", f"'{tool_name}' 실행 중... (인자: {tool_args})")
                        tool_result = str(t.invoke(tool_args))
                        print_trace("Tool Executor", f"'{tool_name}' 실행 완료. 결과를 반환합니다.")
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
    print_trace("Triage Agent", f"새로운 인시던트 접수: '{state.get('incident_report')}'")
    if USE_MOCK_LLM:
        return {
            "layer": "BACKEND",
            "triage_reason": "[MOCK] 장애 내용 분석 결과 백엔드 서버 로직 또는 DB 오류로 추정됩니다.",
            "search_queries": ["500 에러", "요청 조회 실패"]
        }
        
    sys_prompt = TRIAGE_AGENT_PROMPT
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}")
    ])
    
    # JSON 출력을 강제하여 파싱 오류 방지
    messages = prompt.format_messages(incident=state["incident_report"])
    response = llm.invoke(messages)
    result = robust_json_parse(response.content)
    
    layer_result = result.get("layer", "UNKNOWN")
    print_trace("Triage Agent", f"분류 완료 - 레이어: {layer_result}, 사유: {result.get('reason', '')}")
    
    return {
        "layer": layer_result,
        "triage_reason": result.get("reason", ""),
        "search_queries": result.get("search_queries", [])
    }

def root_cause_node(state: IncidentState):
    state_messages = state.get("messages", [])
    
    # 도구 응답 이후 재진입한 경우가 아니면 재시도 카운트 증가
    if state_messages and hasattr(state_messages[-1], 'type') and state_messages[-1].type == 'tool':
        print_trace("Root-Cause Agent", "도구 실행 결과를 수신하여 분석을 재개합니다.")
        current_retry = state.get("retry_count", 0)
    else:
        print_trace("Root-Cause Agent", f"원인 분석을 시작합니다. (대상 레이어: {state.get('layer')})")
        current_retry = state.get("retry_count", 0) + 1

    llm_with_tools = llm.bind_tools(tools) if not USE_MOCK_LLM else None
    
    sys_prompt = ROOT_CAUSE_AGENT_PROMPT
    
    from langchain_core.messages import SystemMessage, HumanMessage
    
    # 항상 최상단에 SystemMessage와 초기 HumanMessage를 배치합니다.
    base_messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"장애 현상: {state.get('incident_report')}\n분류 레이어: {state.get('layer')}\n\n* 지시사항: 필요한 경우 도구를 호출하여 원인을 분석하고, 최종 결과는 반드시 JSON 형태로 응답하세요. (키: root_cause, solution, confidence, risk_level)")
    ]
    
    # LangGraph State에 누적된 이전 대화(Tool calls 등)를 덧붙입니다.
    invocation_messages = base_messages + state_messages
    
    # 단순 재시도(도구 호출 응답이 아님)인데 신뢰도가 낮아 다시 온 경우 피드백 메시지 추가
    if current_retry > 1 and (not state_messages or state_messages[-1].type != 'tool'):
        invocation_messages.append(HumanMessage(content="이전 분석 결과의 신뢰도가 낮거나 올바른 JSON 포맷이 아닙니다. 검색 도구(search_knowledge_base)나 로그 도구(check_server_logs, check_service_health)를 적극적으로 호출하여 데이터를 수집하고 확실한 원인을 파악하세요."))

    if USE_MOCK_LLM:
        return {
            "root_cause": "[MOCK] DB 커넥션 풀 고갈",
            "solution": "[MOCK] DB 커넥션 풀을 늘리거나 재시작합니다.",
            "confidence": "85%",
            "risk_level": "High",
            "retry_count": current_retry
        }
    
    response = llm_with_tools.invoke(invocation_messages)
    
    if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
        for tc in response.tool_calls:
            print_trace("Root-Cause Agent", f"추가 단서 수집을 위해 도구를 호출합니다: {tc.get('name')}")
        return {"messages": [response], "retry_count": current_retry}
    
    result = robust_json_parse(response.content)
    confidence_val = str(result.get("confidence", "0%"))
    print_trace("Root-Cause Agent", f"원인 분석 및 해결책 도출 완료 (신뢰도: {confidence_val})")
    
    return {
        "messages": [response],
        "root_cause": result.get("root_cause", "파싱 실패"),
        "solution": result.get("solution", "파싱 실패"),
        "confidence": str(result.get("confidence", "0%")),
        "risk_level": result.get("risk_level", "Unknown"),
        "retry_count": current_retry
    }

def qa_master_node(state: IncidentState):
    print_trace("QA Master Agent", "제시된 해결책을 검증하기 위한 E2E 테스트 시나리오 및 코드 작성을 시작합니다.")
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

    sys_prompt = QA_MASTER_AGENT_PROMPT
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("user", "장애 현상: {incident}\n적용된 해결책: {solution}")
    ])
    
    messages = prompt.format_messages(
        incident=state["incident_report"], 
        solution=state["solution"]
    )
    response = llm.invoke(messages)
    result = robust_json_parse(response.content)
    
    print_trace("QA Master Agent", "테스트 시나리오 및 Playwright 코드 작성 완료.")
    
    return {
        "test_scenario": result.get("test_scenario", ""),
        "playwright_code": result.get("playwright_code", "")
    }

def escalation_node(state: IncidentState):
    print_trace("System", "분석 신뢰도가 임계치 미달이므로 자동 분석을 중단하고 수동 개입(Escalation) 모드로 전환합니다.")
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

memory = MemorySaver()
itsm_agent_app = workflow.compile(checkpointer=memory)

# 워크플로우 이미지 생성 및 저장 (FastAPI 서빙용)
try:
    png_bytes = itsm_agent_app.get_graph().draw_mermaid_png()
    graph_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph.png")
    with open(graph_path, "wb") as f:
        f.write(png_bytes)
    print(f"✅ LangGraph 워크플로우 이미지가 생성되었습니다: {graph_path}")
except Exception as e:
    print(f"⚠️ LangGraph 워크플로우 이미지 생성 실패: {e}")