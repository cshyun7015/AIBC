좋습니다! RAG 내부 로직 구체화와 FastAPI 백엔드 연동, 두 가지 모두 실제 서비스 패키징을 위해 반드시 거쳐야 하는 핵심 관문입니다.

코드의 유지보수성과 확장성을 위해 LangGraph 에이전트 로직을 `agent.py`로 분리하고, 이를 API로 제공하는 `main.py` (FastAPI) 두 개의 파일로 나누어 작성해 보겠습니다.

---

### 1. `agent.py` (RAG 연동 및 LangGraph 에이전트 코어)

기존 뼈대 코드의 `root_cause_node`에 **FAISS 기반의 Vector DB 검색 로직**을 추가했습니다. 실무 환경(마리아DB 티켓 이력 연동)을 모사하기 위해, 사전에 임베딩된 FAISS 인덱스를 불러와 검색하는 구조로 작성했습니다.

```python
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

```

---

### 2. `main.py` (FastAPI 백엔드 서비스)

위에서 만든 에이전트를 React나 Streamlit 같은 프론트엔드에서 호출할 수 있도록 **REST API**로 패키징합니다. (사전에 `pip install fastapi uvicorn`이 필요합니다.)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from agent import itsm_agent_app  # 앞서 만든 에이전트 앱 임포트

# ==========================================
# 1. API 데이터 모델 (Pydantic)
# ==========================================
class IncidentRequest(BaseModel):
    incident_report: str = Field(..., description="사용자가 입력한 장애 현상", example="요청 등록 후 조회 시 500 에러 발생")

class IncidentResponse(BaseModel):
    layer: str
    rag_context_used: str
    root_cause: str
    solution: str
    qa_test_code: str

# ==========================================
# 2. FastAPI 앱 초기화
# ==========================================
app = FastAPI(
    title="AntiGravity ITSM Agent API",
    description="장애 현상을 입력받아 원인 분석 및 테스트 코드를 생성하는 Multi-Agent 서비스",
    version="1.0.0"
)

# ==========================================
# 3. API 엔드포인트 라우팅
# ==========================================
@app.post("/api/v1/analyze-incident", response_model=IncidentResponse)
async def analyze_incident(request: IncidentRequest):
    try:
        # LangGraph 에이전트 파이프라인 실행
        print(f"🚀 [API 요청 수신] 인시던트 분석 시작: {request.incident_report}")
        
        # State 초기값으로 incident_report 전달
        final_state = itsm_agent_app.invoke({"incident_report": request.incident_report})
        
        # 결과를 API 응답 규격에 맞게 매핑
        return IncidentResponse(
            layer=final_state.get("layer", "UNKNOWN"),
            rag_context_used=final_state.get("rag_context", ""),
            root_cause=final_state.get("root_cause", ""),
            solution=final_state.get("solution", ""),
            qa_test_code=final_state.get("playwright_code", "")
        )
        
    except Exception as e:
        print(f"❌ [에러 발생] {str(e)}")
        raise HTTPException(status_code=500, detail=f"에이전트 실행 중 오류가 발생했습니다: {str(e)}")

# ==========================================
# 4. 서버 실행 가이드
# ==========================================
if __name__ == "__main__":
    import uvicorn
    # 터미널에서 `python main.py` 실행 시 8000 포트로 서버가 열립니다.
    uvicorn.run(app, host="0.0.0.0", port=8000)

```

---

### 💡 실행 및 테스트 방법

두 파일을 같은 폴더에 두고 아래 명령어로 서버를 기동합니다. (Azure OpenAI 환경 변수는 켜져 있어야 합니다.)

```bash
python main.py

```

서버가 켜진 상태에서, 터미널을 하나 더 열어 아래와 같이 **curl 명령어로 API를 테스트**해보면 프론트엔드 연동 준비가 완벽히 끝난 것을 확인할 수 있습니다. (또는 브라우저에서 `http://localhost:8000/docs` 에 접속하여 Swagger UI로 편하게 테스트할 수도 있습니다.)

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/analyze-incident' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "incident_report": "요청 관리 메뉴에서 요청을 등록한 직후 조회를 누르면 500 에러가 납니다."
}'

```
