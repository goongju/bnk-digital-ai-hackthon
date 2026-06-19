from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from foundry_client import FoundryClient
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="EFARS Backend", version="1.0.0")

# CORS 설정 (Streamlit과의 통신을 위해)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Foundry 클라이언트 초기화
try:
    foundry_client = FoundryClient()
except ValueError as e:
    print(f"Warning: Foundry client initialization failed: {e}")
    foundry_client = None


class IncidentReport(BaseModel):
    """사고 보고서 요청"""

    incident_description: str
    t0_kst: str = ""
    additional_context: str = ""


class ReportResponse(BaseModel):
    """보고서 응답"""

    status: str
    data: dict = None
    error: str = None


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "foundry_connected": foundry_client is not None,
    }


@app.post("/analyze", response_model=ReportResponse)
def analyze_incident(report: IncidentReport):
    """
    사고 사실관계 분석 엔드포인트
    orchestrator 에이전트 호출 (A2A 프로토콜로 자동 에이전트 조율)

    Args:
        report: 사고 설명

    Returns:
        분석 결과 (분류, 법령, 시한, 보고서 초안, 품질 검증)
    """
    if not foundry_client:
        raise HTTPException(status_code=500, detail="Foundry client not initialized")

    if not report.incident_description.strip():
        raise HTTPException(status_code=400, detail="Incident description is empty")

    response = foundry_client.run_orchestration(
        user_facts=report.incident_description,
        t0_kst=report.t0_kst,
        additional_context=report.additional_context,
    )

    if response.get("status") == "need_input":
        return ReportResponse(status="need_input", data=response)

    if response.get("status") != "success":
        detail = {
            "message": response.get("error"),
            "endpoint": response.get("endpoint"),
            "error_body": response.get("error_body") or response.get("error_detail"),
        }
        raise HTTPException(status_code=500, detail=detail)

    return ReportResponse(status="success", data=response)


@app.get("/agents/status")
async def get_agents_status():
    """등록된 에이전트 상태 조회"""
    return {
        "incident_classifier": os.getenv("INCIDENT_CLASSIFIER_ID"),
        "regulation_search": os.getenv("REGULATION_SEARCH_ID"),
        "deadline_manager": os.getenv("DEADLINE_MANAGER_ID"),
        "report_writer": os.getenv("REPORT_WRITER_ID"),
        "quality_supervisor": os.getenv("QUALITY_SUPERVISOR_ID"),
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", 8000))

    uvicorn.run(app, host=host, port=port)
