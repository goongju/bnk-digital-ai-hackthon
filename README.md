# EFARS - 전자금융사고보고서 자동 작성 시스템

**사고 사실관계 입력 → AI 자동 분석 → 보고서 자동 생성**

## 🏗️ 프로젝트 구조

```
elec_fin_incident_report/
├── .env                          # Foundry 설정 (민감한 정보)
├── .gitignore
├── requirements.txt               # Python 의존성
├── README.md
├── backend/
│   ├── main.py                   # FastAPI 백엔드 서버
│   └── foundry_client.py         # Foundry orchestrator 호출 로직
└── frontend/
    └── streamlit_app.py          # Streamlit UI
```

## 🚀 빠른 시작

### 1️⃣ 환경 설정 확인

`.env` 파일이 이미 생성되어 있으며, Foundry 설정이 포함되어 있습니다:

```env
FOUNDRY_ENDPOINT=https://testuser49-0376-resource.openai.azure.com/openai/v1
FOUNDRY_API_KEY=EUvaWjIaVvzOebVN7yV64Iz8SXAm9hix5dkqUMxge7ENfiRo6L2nJQQJ99CFACfhMk5XJ3w3AAAAACOGl2W5
FOUNDRY_PROJECT_NAME=testuser49-0376
ORCHESTRATOR_AGENT_ID=2dd4cef5-a45d-447f-b257-8852e4028784
```

### 2️⃣ 의존성 설치

```bash
pip install -r requirements.txt
```

### 3️⃣ FastAPI 백엔드 실행

```bash
python backend/main.py
```

Backend가 실행되면 다음과 같은 메시지가 나타나야 합니다:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4️⃣ Streamlit UI 실행 (새 터미널)

```bash
streamlit run frontend/streamlit_app.py
```

UI가 열리면 자동으로 브라우저에서 `http://localhost:8501` 이 표시됩니다.

## 📋 사용 방법

### Streamlit UI에서:

1. **사고 정보 입력**
   - 사고 발생일: 날짜 선택
   - 사고 발생 기관명: 기관 이름 입력
   - 사고 사실관계 설명: 상세 설명 입력

2. **분석 시작**
   - "🚀 분석 시작" 버튼 클릭
   - orchestrator가 A2A 프로토콜로 다음 에이전트들을 자동 조율합니다:
     - `incident-classifier`: 사고 분류
     - `regulation-search`: 적용 법령 검색
     - `deadline-manager`: 보고 시한 산정
     - `report-writer`: 보고서 초안 작성
     - `quality-supervisor`: 품질 검증

3. **결과 확인**
   - 📋 **보고서 탭**: 최종 보고서 내용
   - 🏷️ **분류 탭**: 사고 분류 정보
   - ⚖️ **법령 탭**: 적용 법령
   - 📅 **시한 탭**: 보고 시한
   - ✅ **품질 탭**: 품질 검증 결과

4. **결과 다운로드**
   - JSON 형식으로 분석 결과 다운로드 가능

## 🔌 API 엔드포인트

FastAPI 백엔드는 다음 엔드포인트를 제공합니다:

### Health Check
```
GET /health
```

응답:
```json
{
  "status": "healthy",
  "foundry_connected": true
}
```

### 사고 분석
```
POST /analyze
Content-Type: application/json

{
  "incident_description": "사고 설명..."
}
```

응답:
```json
{
  "status": "success",
  "data": {
    "classification": {...},
    "regulations": [...],
    "deadline": {...},
    "report": "...",
    "quality_check": {...}
  }
}
```

### 에이전트 상태 조회
```
GET /agents/status
```

응답:
```json
{
  "orchestrator": "2dd4cef5-a45d-447f-b257-8852e4028784",
  "incident_classifier": "b450b437-37b8-4e6a-bde6-08393a302f44",
  ...
}
```

## 🔧 Foundry 에이전트 구조

```
orchestrator (오케스트레이터)
├── incident-classifier (사고 분류)
├── regulation-search (법령 검색)
├── deadline-manager (시한 관리)
├── report-writer (보고서 작성)
└── quality-supervisor (품질 감시)
```

- **A2A 프로토콜**: Agent-to-Agent 통신 프로토콜로, orchestrator가 자동으로 다른 에이전트들을 조율합니다.
- **응답 형식**: JSON 형식의 구조화된 데이터를 반환합니다.

## ⚙️ 설정 변경

`.env` 파일을 수정하여 설정을 변경할 수 있습니다:

```env
# Foundry 엔드포인트 변경
FOUNDRY_ENDPOINT=https://your-foundry-endpoint.openai.azure.com/openai/v1

# API 키 변경
FOUNDRY_API_KEY=your-api-key

# 서버 포트 변경
FASTAPI_PORT=8000
STREAMLIT_PORT=8501
```

변경 후 서버를 재실행하면 적용됩니다.

## 🐛 문제 해결

### 백엔드 연결 오류
```
⚠️ 백엔드 서버에 연결할 수 없습니다.
```

**해결책:**
1. FastAPI 백엔드가 실행 중인지 확인: `python backend/main.py`
2. 포트 8000이 사용 가능한지 확인: `netstat -an | findstr 8000` (Windows)

### Foundry 인증 오류
```
❌ 분석 실패: Unauthorized
```

**해결책:**
1. `.env` 파일의 `FOUNDRY_API_KEY` 확인
2. 키가 만료되지 않았는지 확인 (Foundry 포털에서 재생성 가능)

### 응답 타임아웃
```
⏱️ 요청 시간 초과. 분석이 너무 오래 걸렸습니다.
```

**해결책:**
- Foundry 에이전트의 처리 시간이 길 수 있습니다.
- `frontend/streamlit_app.py`의 타임아웃 값을 증가시킬 수 있습니다:
  ```python
  timeout=120  # 120초로 설정
  ```

## 📝 개발 노트

### Foundry orchestrator 응답 스키마

현재 구현은 orchestrator가 다음과 같은 형식의 JSON 응답을 반환한다고 가정합니다:

```json
{
  "classification": {
    "type": "보안사고",
    "severity": "심각"
  },
  "regulations": [
    "전자금융감독규정 제XX조",
    ...
  ],
  "deadline": {
    "report_deadline": "2026-06-20T09:00:00Z",
    "days_remaining": 1
  },
  "report": "최종 보고서 내용...",
  "quality_check": {
    "status": "pass",
    "issues": []
  }
}
```

실제 응답 형식이 다르면 `foundry_client.py`의 `parse_orchestrator_response()` 메서드를 조정하면 됩니다.

### 향후 개선 사항

- [ ] 사고 분류 선택 화면 추가 (orchestrator 응답 기반)
- [ ] 보고서 자동 생성 후 Word/PDF 다운로드
- [ ] 사고 이력 관리 (데이터베이스 연동)
- [ ] 사용자 인증 (SSO 연동)
- [ ] 알림 기능 (시한 만료 전 알림)
- [ ] 에이전트별 상세 로그 조회

## 📞 지원

문제가 발생하면:
1. `.env` 설정 확인
2. 백엔드 서버 로그 확인
3. Foundry 포털에서 에이전트 상태 확인

---

**Made with ❤️ for EFARS**
