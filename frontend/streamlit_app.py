import json
from datetime import datetime

import requests
import streamlit as st

st.set_page_config(page_title="전자금융사고 보고 자동화 시스템", page_icon="BNK", layout="wide")

BACKEND_URL = "http://localhost:8000"

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False
if "selected_agent" not in st.session_state:
    st.session_state.selected_agent = None


@st.cache_data(ttl=5)
def check_backend_health() -> bool:
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return response.status_code == 200
    except Exception:
        return False


def pipeline_status(data: dict, is_loading: bool) -> dict:
    degraded = data.get("degraded_components", []) if isinstance(data, dict) else []
    has_classification = bool(data.get("classification")) if isinstance(data, dict) else False
    has_regulations = bool(data.get("regulations")) if isinstance(data, dict) else False
    has_timeline = bool(data.get("timeline")) if isinstance(data, dict) else False
    has_writer = bool(data.get("report_writer")) if isinstance(data, dict) else False

    status = {
        "code-orchestrator": "진행 중" if is_loading else ("완료" if has_classification or has_writer else "대기 중"),
        "incident-analyzer": "완료" if has_classification else ("진행 중" if is_loading else "대기 중"),
        "regulation-finder": (
            "지연/부분" if "regulation-search" in degraded else ("완료" if has_regulations else ("진행 중" if is_loading and has_classification else "대기 중"))
        ),
        "deadline-manager": (
            "지연/부분" if "deadline-manager" in degraded else ("완료" if has_timeline else ("진행 중" if is_loading and has_classification else "대기 중"))
        ),
        "report-writer": "완료" if has_writer else ("진행 중" if is_loading and (has_regulations or has_timeline or has_classification) else "대기 중"),
        "quality-supervisor": "완료" if has_writer else ("진행 중" if is_loading and has_writer else "대기 중"),
    }
    return status


def pipeline_progress(data: dict, is_loading: bool, result_status: str | None) -> int:
    status = pipeline_status(data, is_loading)
    weights = {
        "code-orchestrator": 10,
        "incident-analyzer": 20,
        "regulation-finder": 15,
        "deadline-manager": 15,
        "report-writer": 30,
        "quality-supervisor": 10,
    }

    score = 0
    for name, state in status.items():
        w = weights.get(name, 0)
        if state == "완료":
            score += w
        elif state == "진행 중":
            score += int(w * 0.5)
        elif state == "지연/부분":
            score += int(w * 0.75)

    # Keep UX responsive: show early progress while loading starts.
    if is_loading and score < 10:
        score = 10

    if result_status == "success":
        score = 100
    elif result_status == "error":
        score = max(score, 95)

    return min(100, max(0, score))


def top_metrics(data: dict) -> tuple[str, str, str]:
    classification = data.get("classification", {}) if isinstance(data, dict) else {}
    timeline = data.get("timeline", {}) if isinstance(data, dict) else {}

    severity = classification.get("severity_class", "-")
    reportable = "보고대상" if classification.get("is_reportable") is True else ("비보고" if classification.get("is_reportable") is False else "-")
    first_due = timeline.get("initial_due", "-")
    return severity, reportable, first_due


st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(1200px 500px at 70% -10%, #1a2846, #0b1020 55%, #070b16 100%);
        color: #d8e0ff;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #101933 0%, #0a1228 100%);
        border-right: 1px solid #223156;
    }
    .block-container {
        padding-top: 2.6rem;
        padding-bottom: 1rem;
        max-width: 1500px;
    }
    .metric-card {
        background: linear-gradient(180deg, #0f1730 0%, #0a1126 100%);
        border: 1px solid #21315a;
        border-radius: 10px;
        padding: 14px 16px;
        min-height: 92px;
    }
    .metric-title {
        color: #8da0cf;
        font-size: 12px;
        margin-bottom: 8px;
    }
    .metric-value {
        color: #eef3ff;
        font-size: 23px;
        font-weight: 700;
    }
    .metric-sub {
        color: #6f85be;
        font-size: 12px;
        margin-top: 6px;
    }
    .panel {
        background: #0a1125;
        border: 1px solid #22345f;
        border-radius: 10px;
        padding: 12px 14px;
    }
    .empty-state {
        text-align: center;
        border: 1px dashed #2a3c68;
        border-radius: 12px;
        padding: 80px 20px;
        color: #8fa2cf;
        margin-top: 16px;
    }
    .section-title {
        color: #cfd9ff;
        font-weight: 700;
        margin: 6px 0 8px 0;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

result = st.session_state.analysis_result
data = result.get("data", {}) if isinstance(result, dict) else {}
result_status = result.get("status") if isinstance(result, dict) else None
severity, reportable, first_due = top_metrics(data)

with st.sidebar:
    st.markdown("### 전자금융사고 보고 자동화 시스템")
    st.caption("전자금융감독규정 제37조의57조의4")

    default_t0 = datetime.now().strftime("%Y-%m-%d %H:%M")
    t0_human = st.text_input("사고 인지 시각", value=default_t0)
    t0_kst = st.text_input(
        "T0 (ISO 8601)",
        value=datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    )
    incident_type_input = st.selectbox("사고 유형", ["자동 판별", "시스템 장애사고", "보안 침해사고", "부정거래 사고"], index=0)
    incident_description = st.text_area(
        "사고 상황 설명",
        placeholder="예) 오늘 오전 9시에 인터넷뱅킹 로그인 시스템에서 비정상 요청 급증이 탐지되었습니다.",
        height=140,
    )
    additional_context = st.text_area(
        "추가 맥락",
        placeholder="예) 동일 수법 과거 2건, 외주 운영사 관제 이관 중",
        height=90,
    )

    if st.button("사고 분석 시작", use_container_width=True, type="primary"):
        if not incident_description.strip():
            st.error("사고 상황 설명을 입력해주세요.")
        else:
            st.session_state.is_loading = True
            st.session_state.selected_agent = None

    if st.button("초기화", use_container_width=True):
        st.session_state.analysis_result = None
        st.session_state.is_loading = False
        st.session_state.selected_agent = None
        st.rerun()

    st.markdown("---")
    st.markdown("#### 에이전트 파이프라인")
    p_status = pipeline_status(data, st.session_state.is_loading)
    progress_pct = pipeline_progress(data, st.session_state.is_loading, result_status)
    st.markdown(f"진행률: **{progress_pct}%**")
    st.progress(progress_pct)
    
    # Pipeline agent buttons
    agent_names = list(p_status.keys())
    cols = st.columns(2)
    for i, name in enumerate(agent_names):
        col = cols[i % 2]
        with col:
            btn_style = "primary" if st.session_state.selected_agent == name else "secondary"
            if st.button(f"{name}\n{p_status[name]}", key=f"agent_{name}", use_container_width=True, type=btn_style):
                st.session_state.selected_agent = None if st.session_state.selected_agent == name else name
                st.rerun()

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

header_left, header_right = st.columns([8, 2])
with header_left:
    st.markdown("## 사고 분석 대시보드")
with header_right:
    if check_backend_health():
        st.success("시스템 정상")
    else:
        st.error("백엔드 연결 실패")

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(
        f"<div class='metric-card'><div class='metric-title'>사고 등급</div><div class='metric-value'>{severity}</div><div class='metric-sub'>분석 결과</div></div>",
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"<div class='metric-card'><div class='metric-title'>보고 의무</div><div class='metric-value'>{reportable}</div><div class='metric-sub'>is_reportable</div></div>",
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f"<div class='metric-card'><div class='metric-title'>최초보고 마감</div><div class='metric-value' style='font-size:18px'>{first_due}</div><div class='metric-sub'>timeline.initial_due</div></div>",
        unsafe_allow_html=True,
    )

if st.session_state.is_loading:
    with st.spinner("사고 분석 실행 중..."):
        try:
            payload = {
                "incident_description": incident_description,
                "t0_kst": t0_kst,
                "additional_context": additional_context,
            }
            response = requests.post(f"{BACKEND_URL}/analyze", json=payload, timeout=300)
            if response.status_code == 200:
                st.session_state.analysis_result = response.json()
            else:
                st.session_state.analysis_result = {
                    "status": "error",
                    "error": f"HTTP {response.status_code}: {response.text}",
                }
        except requests.exceptions.Timeout:
            st.session_state.analysis_result = {"status": "error", "error": "요청 시간이 초과되었습니다."}
        except requests.exceptions.ConnectionError:
            st.session_state.analysis_result = {"status": "error", "error": "백엔드 서버 연결에 실패했습니다."}
        except Exception as e:
            st.session_state.analysis_result = {"status": "error", "error": str(e)}
        finally:
            st.session_state.is_loading = False
            st.rerun()

result = st.session_state.analysis_result
if not result:
    st.markdown(
        """
        <div class='empty-state'>
            <h3 style='color:#cbd7ff;'>분석 준비 완료</h3>
            <p>왼쪽 입력 패널에서 사고 상황을 입력한 후<br>"사고 분석 시작" 버튼을 눌러주세요.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    if result.get("status") == "need_input":
        st.warning(result.get("data", {}).get("question", "추가 입력이 필요합니다."))
    elif result.get("status") != "success":
        st.error(result.get("error", "분석 중 오류가 발생했습니다."))
    else:
        data = result.get("data", {})
        
        # 에이전트가 선택되지 않은 경우: 탭 표시
        if not st.session_state.selected_agent:
            tabs = st.tabs(["개요", "사고 분석", "적용 규정", "보고 기한", "보고서 초안"])

            # ── 탭 0: 개요 ──────────────────────────────────────────────
            with tabs[0]:
                cls = data.get("classification", {})
                tl = data.get("timeline", {})
                wr = data.get("report_writer", {})

                # 핵심 요약 카드 3개
                sev = cls.get("severity_class", "-")
                sev_color = {"1등급": "#ff4b4b", "2등급": "#ff8c00", "medium": "#f0c040", "low": "#4caf50"}.get(sev, "#8da0cf")
                inc_type = cls.get("incident_type", "-")
                authority = cls.get("severity_decision_authority", "-")
                strengthened = "✅ 적용중" if wr.get("internal_strengthened_applied") else "—"
                self_check = wr.get("self_check_score", "-")
                missing = wr.get("missing_fields", [])

                c1, c2, c3 = st.columns(3)
                c1.markdown(f"""
<div class='metric-card'>
  <div class='metric-title'>사고 유형</div>
  <div class='metric-value' style='font-size:15px;line-height:1.4'>{inc_type}</div>
  <div class='metric-sub'>사내 세칙 제6조</div>
</div>""", unsafe_allow_html=True)
                c2.markdown(f"""
<div class='metric-card'>
  <div class='metric-title'>사고 등급</div>
  <div class='metric-value' style='color:{sev_color}'>{sev}</div>
  <div class='metric-sub'>결정권자: {authority}</div>
</div>""", unsafe_allow_html=True)
                c3.markdown(f"""
<div class='metric-card'>
  <div class='metric-title'>보고서 자체검증</div>
  <div class='metric-value'>{self_check}/1.0</div>
  <div class='metric-sub'>내부 강화기준 {strengthened}</div>
</div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # 대응 책임 매트릭스
                st.markdown("**대응 책임**")
                responsibility = [
                    ("총괄", "IT운영부장"),
                    ("실무", "IT사고대응반장"),
                    ("검토", "준법감시부서"),
                    ("사고선포", "비상대응위원장"),
                ]
                resp_cols = st.columns(len(responsibility))
                for col, (role, person) in zip(resp_cols, responsibility):
                    col.markdown(f"""<div class='metric-card' style='min-height:60px;padding:10px 12px;'>
<div class='metric-title'>{role}</div>
<div style='color:#eef3ff;font-size:13px;font-weight:600'>{person}</div>
</div>""", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # 보완 필요 항목
                if missing:
                    st.warning(f"보완 필요 항목: {', '.join(missing)}")

                # degraded
                degraded = data.get("degraded_components", [])
                if degraded:
                    st.error(f"일부 에이전트 결과 미확보: {', '.join(degraded)}")

                # 보고서 요약본
                brief = wr.get("report_brief_markdown", "")
                if brief:
                    st.markdown("**임원·실무 단문 요약**")
                    st.info(brief)

                with st.expander("원본 전체 메시지 보기"):
                    st.text(data.get("final_message", "-"))

            # ── 탭 1: 사고 분석 ─────────────────────────────────────────
            with tabs[1]:
                cls = data.get("classification", {})
                if not cls:
                    st.info("분류 데이터 없음")
                else:
                    is_rep = cls.get("is_reportable")
                    if is_rep is True:
                        st.success("보고 대상 사고입니다")
                    elif is_rep is False:
                        st.error("보고 대상 아님")
                    else:
                        st.warning("보고 여부 미결정")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**분류 상세**")
                        fields = {
                            "사고 유형": cls.get("incident_type", "-"),
                            "심각도 등급": cls.get("severity_class", "-"),
                            "대응 레벨": cls.get("severity_response_level", "-"),
                            "결정 권한": cls.get("severity_decision_authority", "-"),
                        }
                        for label, val in fields.items():
                            st.markdown(f"""<div style='display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e2e50'>
<span style='color:#8da0cf;font-size:13px'>{label}</span>
<span style='color:#eef3ff;font-size:13px;font-weight:600'>{val}</span>
</div>""", unsafe_allow_html=True)

                    with col_b:
                        st.markdown("**제외 사유**")
                        excl_basis = cls.get("exclusion_basis") or "해당 없음"
                        excl_clause = cls.get("exclusion_clause_applied") or "—"
                        st.markdown(f"""<div style='padding:6px 0;border-bottom:1px solid #1e2e50'>
<span style='color:#8da0cf;font-size:13px'>제외 사유</span><br>
<span style='color:#eef3ff;font-size:13px'>{excl_basis}</span>
</div>""", unsafe_allow_html=True)
                        st.markdown(f"""<div style='padding:6px 0;border-bottom:1px solid #1e2e50'>
<span style='color:#8da0cf;font-size:13px'>적용 조항</span><br>
<span style='color:#eef3ff;font-size:13px'>{excl_clause}</span>
</div>""", unsafe_allow_html=True)

                        missing_cls = cls.get("missing_fields", [])
                        if missing_cls:
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.warning(f"누락 필드: {', '.join(missing_cls)}")

            # ── 탭 2: 적용 규정 ─────────────────────────────────────────
            with tabs[2]:
                regs = data.get("regulations", {})
                clauses = regs.get("applicable_clauses", []) if regs else []
                if not clauses:
                    st.info("적용 규정 데이터 없음")
                else:
                    st.markdown(f"**총 {len(clauses)}개 조항 적용**")
                    for i, clause in enumerate(clauses, 1):
                        source = clause.get("source", f"조항 {i}")
                        title = clause.get("title", "")
                        summary = clause.get("summary", clause.get("description", ""))
                        quote = clause.get("exact_quote", clause.get("quote", ""))
                        obligation = clause.get("obligation_type", clause.get("type", ""))

                        with st.expander(f"📋 {source}" + (f" — {title}" if title else ""), expanded=(i == 1)):
                            if obligation:
                                st.caption(f"의무 유형: {obligation}")
                            if summary:
                                st.markdown(summary)
                            if quote:
                                st.markdown(f"> {quote}")

            # ── 탭 3: 보고 기한 ─────────────────────────────────────────
            with tabs[3]:
                tl = data.get("timeline", {})
                if not tl:
                    st.info("기한 데이터 없음")
                else:
                    initial_due = tl.get("initial_due", "-")
                    interim_due = tl.get("interim_first_due", "사고 변동 시 즉시")
                    rca_days = tl.get("rca_report_due_offset_days", "-")

                    deadlines = [
                        ("최초 보고 (1차)", initial_due, "T0 + 12h", "#ff8c00"),
                        ("경과 보고", interim_due, "사고 변동 시 즉시", "#4da6ff"),
                        ("종료 보고", "조치 완료 시점", "사내 세칙 제11조", "#6fcf97"),
                        ("원인분석 보고", f"종료일 + {rca_days}일", "사내 세칙 제18조", "#bb86fc"),
                    ]

                    for label, due, basis, color in deadlines:
                        st.markdown(f"""<div style='display:flex;align-items:center;gap:14px;padding:12px 14px;margin-bottom:8px;
background:#0a1125;border:1px solid #1e2e50;border-left:4px solid {color};border-radius:8px'>
  <div style='flex:1'>
    <div style='color:#8da0cf;font-size:12px;margin-bottom:2px'>{label}</div>
    <div style='color:#eef3ff;font-size:15px;font-weight:700'>{due}</div>
    <div style='color:#6f85be;font-size:11px;margin-top:2px'>{basis}</div>
  </div>
</div>""", unsafe_allow_html=True)

                    # 추가 타임라인 필드
                    extra_keys = {k: v for k, v in tl.items() if k not in ("initial_due", "interim_first_due", "rca_report_due_offset_days")}
                    if extra_keys:
                        with st.expander("추가 기한 정보"):
                            for k, v in extra_keys.items():
                                st.markdown(f"- **{k}**: {v}")

            # ── 탭 4: 보고서 초안 ────────────────────────────────────────
            with tabs[4]:
                wr = data.get("report_writer", {})
                report_md = wr.get("report_markdown", "[데이터 미확보]")
                st.markdown(report_md)

                st.markdown("---")
                col_dl1, col_dl2 = st.columns(2)

                # 후속 조치
                follow_ups = wr.get("follow_up_actions", [])
                if follow_ups:
                    with col_dl1:
                        st.markdown("**후속 조치**")
                        for act in follow_ups:
                            if isinstance(act, dict):
                                st.markdown(f"- [ ] **{act.get('action', '')}**  \n  시한: {act.get('due_kst', '-')} | 담당: {act.get('responsible_role', '-')}")
                            else:
                                st.markdown(f"- [ ] {act}")

                # 의사결정 요청
                decisions = wr.get("decisions_requested", [])
                if decisions:
                    with col_dl2:
                        st.markdown("**의사결정 요청**")
                        for d in decisions:
                            if isinstance(d, dict):
                                st.markdown(f"- [ ] **{d.get('decision', '')}**  \n  권고: {d.get('recommendation', '-')}")
                            else:
                                st.markdown(f"- [ ] {d}")

            with st.expander("원본 JSON 보기"):
                st.json(data)

            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            st.download_button(
                label="JSON 결과 다운로드",
                data=json_str,
                file_name=f"efars_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )
        
        # 에이전트가 선택된 경우: 해당 에이전트의 입출력만 표시
        else:
            st.markdown("---")
            st.markdown("#### 에이전트 응답 상세")
            agent_name = st.session_state.selected_agent
            st.markdown(f"**선택된 에이전트:** `{agent_name}`")

            agent_inputs = data.get("agent_inputs", {})
            input_data = agent_inputs.get(agent_name, {})

            st.markdown("**Input (요청):**")
            if input_data:
                st.json(input_data)
            else:
                st.caption("입력 데이터 없음")

            st.markdown("**Output (응답):**")
            if agent_name == "code-orchestrator":
                st.json({"final_message": data.get("final_message", "-")})
            elif agent_name == "incident-analyzer":
                st.json(data.get("classification", {}))
            elif agent_name == "regulation-finder":
                st.json(data.get("regulations", {}))
            elif agent_name == "deadline-manager":
                st.json(data.get("timeline", {}))
            elif agent_name == "report-writer":
                st.json(data.get("report_writer", {}))
            elif agent_name == "quality-supervisor":
                st.json(data.get("report_writer", {}))
