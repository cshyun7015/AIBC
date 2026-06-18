from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.agent import itsm_agent_app  # 앞서 만든 에이전트 앱 임포트

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
    confidence: str
    risk_level: str
    test_scenario: str
    qa_test_code: str

from fastapi.middleware.cors import CORSMiddleware

# ==========================================
# 2. FastAPI 앱 초기화
# ==========================================
app = FastAPI(
    title="AntiGravity ITSM Agent API",
    description="장애 현상을 입력받아 원인 분석 및 테스트 코드를 생성하는 Multi-Agent 서비스",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 프론트엔드 URL만 허용하도록 변경
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 3. API 엔드포인트 라우팅
# ==========================================
@app.post("/api/v1/analyze-incident", response_model=IncidentResponse)
def analyze_incident(request: IncidentRequest):
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
            confidence=str(final_state.get("confidence", "N/A")),
            risk_level=final_state.get("risk_level", "Unknown"),
            test_scenario=final_state.get("test_scenario", ""),
            qa_test_code=final_state.get("playwright_code", "")
        )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ [에러 발생] {str(e)}")
        print(f"🔍 [상세 트레이스백]\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"에이전트 실행 중 오류가 발생했습니다: {str(e)}")

from fastapi.responses import FileResponse
import os

@app.get("/api/v1/graph-image")
def get_graph_image():
    image_path = os.path.join(os.path.dirname(__file__), "graph.png")
    if os.path.exists(image_path):
        return FileResponse(image_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Image not generated yet")

# ==========================================
# 4. 서버 실행 가이드
# ==========================================
if __name__ == "__main__":
    import uvicorn
    # 터미널에서 `python main.py` 실행 시 8000 포트로 서버가 열립니다.
    uvicorn.run(app, host="0.0.0.0", port=8000)