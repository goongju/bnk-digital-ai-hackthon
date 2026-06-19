import os
import json
import re
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import requests
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional, Tuple

load_dotenv()


class FoundryClient:
    """코드 기반 오케스트레이터: 분류 -> 규정/기한 -> 보고서"""

    def __init__(self):
        self.endpoint = os.getenv("FOUNDRY_ENDPOINT")
        self.api_key = os.getenv("FOUNDRY_API_KEY")
        self.model_deployment = os.getenv("FOUNDRY_MODEL_DEPLOYMENT")
        self.project_name = os.getenv("FOUNDRY_PROJECT_NAME")
        self.project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        self.incident_classifier_id = os.getenv("INCIDENT_CLASSIFIER_ID")
        self.regulation_search_id = os.getenv("REGULATION_SEARCH_ID")
        self.deadline_manager_id = os.getenv("DEADLINE_MANAGER_ID")
        self.report_writer_id = os.getenv("REPORT_WRITER_ID")
        self.quality_supervisor_id = os.getenv("QUALITY_SUPERVISOR_ID")

        if not all([
            self.endpoint,
            self.api_key,
            self.model_deployment,
            self.incident_classifier_id,
            self.regulation_search_id,
            self.deadline_manager_id,
            self.report_writer_id,
            self.quality_supervisor_id,
        ]):
            raise ValueError("Missing required Foundry configuration in .env")

        # Lazy-loaded Foundry project client (requires azure-ai-projects + azure-identity)
        self._project_client = None
        self._openai_client = None

    def _get_openai_client(self):
        """Foundry project OpenAI client를 lazy-load (azure-ai-projects 필요)."""
        if self._openai_client is not None:
            return self._openai_client
        if not self.project_endpoint:
            return None
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
            if self._project_client is None:
                self._project_client = AIProjectClient(
                    endpoint=self.project_endpoint,
                    credential=DefaultAzureCredential(),
                )
            self._openai_client = self._project_client.get_openai_client()
            return self._openai_client
        except Exception as e:
            print(f"[WARN] Could not create Foundry project client: {e}", flush=True)
            return None

    # report-writer 에이전트에서 가져온 code_interpreter 파일 ID (DOCX 템플릿)
    _REPORT_WRITER_CI_FILE_ID = "assistant-1hXmDPrB9uaSuQ8FPjX8n3"
    _REPORT_WRITER_CI_AGENT_NAME = "report-writer-ci-only"

    def _invoke_writer_via_responses_api(
        self,
        payload_text: str,
        timeout_sec: int = 120,
    ) -> Tuple[bool, Optional[bytes], str]:
        """
        Foundry Responses API + Code Interpreter(code_interpreter only, no MCP)로 report-writer를 호출.
        성공 시 (True, docx_bytes, filename), 실패 시 (False, None, error_message) 반환.
        """
        oc = self._get_openai_client()
        if oc is None:
            return False, None, "Foundry project client unavailable"
        if self._project_client is None:
            return False, None, "Foundry project client not initialized"

        try:
            from azure.ai.projects.models import PromptAgentDefinition, CodeInterpreterTool, AutoCodeInterpreterToolParam

            # 원본 report-writer instructions 가져오기 (캐시)
            agent_def = self._project_client.agents.get("report-writer")
            versions = agent_def.get("versions", {})
            latest = versions.get("latest", {})
            defn = latest.get("definition", {})
            instructions = defn.instructions
            model = defn.model or self.model_deployment

            # MCP 없이 code_interpreter만 사용하는 임시 에이전트 버전 생성
            temp_agent = self._project_client.agents.create_version(
                agent_name=self._REPORT_WRITER_CI_AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=model,
                    instructions=instructions,
                    tools=[
                        CodeInterpreterTool(
                            container=AutoCodeInterpreterToolParam(
                                file_ids=[self._REPORT_WRITER_CI_FILE_ID]
                            )
                        )
                    ],
                ),
                description="Temp: code_interpreter only (no MCP) for backend use",
            )
            print(f"[RESPONSES_API] temp agent: {temp_agent.name} v{temp_agent.version}", flush=True)

            try:
                # conversation 생성
                conversation = oc.conversations.create()
                conv_id = conversation.id
                print(f"[RESPONSES_API] conversation_id={conv_id}", flush=True)

                # report-writer-ci-only 에이전트 호출
                response = oc.responses.create(
                    conversation=conv_id,
                    input=payload_text,
                    max_output_tokens=8192,
                    extra_body={
                        "agent_reference": {
                            "name": self._REPORT_WRITER_CI_AGENT_NAME,
                            "type": "agent_reference",
                        }
                    },
                    timeout=timeout_sec,
                )
                print(f"[RESPONSES_API] response status={response.status} incomplete_details={getattr(response,'incomplete_details',None)}", flush=True)
                print(f"[RESPONSES_API] output items count: {len(response.output)}", flush=True)
                for _i, _item in enumerate(response.output):
                    print(f"[RESPONSES_API]   output[{_i}] type={_item.type}", flush=True)
                    if hasattr(_item, "content"):
                        for _j, _cb in enumerate(getattr(_item, "content", []) or []):
                            anns = getattr(_cb, "annotations", []) or []
                            print(f"[RESPONSES_API]     content[{_j}] type={getattr(_cb,'type','')} annotations={len(anns)}", flush=True)
                            for _ann in anns:
                                print(f"[RESPONSES_API]       annotation type={getattr(_ann,'type','')} filename={getattr(_ann,'filename','')}", flush=True)

                # 출력에서 .docx 파일 annotation 찾기 — status 무관하게 스캔
                file_id = None
                filename = None
                container_id = None

                for item in response.output:
                    # message 타입 이외에도 tool_result 등 확인
                    content_list = getattr(item, "content", None) or []
                    for content_block in content_list:
                        for annotation in getattr(content_block, "annotations", []) or []:
                            if getattr(annotation, "type", "") == "container_file_citation":
                                fn = getattr(annotation, "filename", "")
                                if fn.endswith(".docx"):
                                    file_id = annotation.file_id
                                    filename = fn
                                    container_id = annotation.container_id
                                    break
                        if file_id:
                            break
                    if file_id:
                        break

                if not file_id or not container_id:
                    print("[RESPONSES_API] No .docx annotation found in response", flush=True)
                    return False, None, "No .docx file annotation in agent response"

                print(f"[RESPONSES_API] Found file: {filename} (id={file_id})", flush=True)
                file_content = oc.containers.files.content.retrieve(
                    file_id=file_id,
                    container_id=container_id,
                )
                docx_bytes = file_content.read()
                print(f"[RESPONSES_API] Downloaded {len(docx_bytes)} bytes", flush=True)
                return True, docx_bytes, filename or "report.docx"

            finally:
                # 임시 에이전트 버전 정리 (오류 무시)
                try:
                    self._project_client.agents.delete_version(
                        agent_name=temp_agent.name,
                        agent_version=temp_agent.version,
                    )
                except Exception:
                    pass

        except Exception as e:
            print(f"[RESPONSES_API] error: {e}", flush=True)
            return False, None, str(e)

    def _post_chat(self, messages: List[Dict[str, str]], timeout_sec: int = 20) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }
        payload = {
            "model": self.model_deployment,
            "messages": messages,
            "temperature": 0.2,
            "max_completion_tokens": 4096,
            "response_format": {"type": "json_object"},
        }
        url = f"{self.endpoint}/chat/completions"
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        if response.status_code >= 400:
            try:
                error_body = response.json()
            except ValueError:
                error_body = {"raw": response.text}
            return {
                "ok": False,
                "error": f"Foundry call failed ({response.status_code})",
                "error_body": error_body,
                "endpoint": url,
            }
        return {"ok": True, "data": response.json()}

    def _extract_json(self, content: str) -> Dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)

    def _repair_json(self, raw_content: str, timeout_sec: int = 20) -> Tuple[bool, Dict[str, Any]]:
        """모델 출력 JSON이 깨진 경우, 의미를 보존한 채 유효 JSON으로 복구 시도"""
        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You repair malformed JSON. Return one valid JSON object only. "
                    "Do not add commentary. Keep original meaning."
                ),
            },
            {
                "role": "user",
                "content": "Repair this malformed JSON:\n" + raw_content,
            },
        ]
        resp = self._post_chat(repair_messages, timeout_sec=timeout_sec)
        if not resp.get("ok"):
            return False, {}
        try:
            repaired = resp["data"]["choices"][0]["message"]["content"]
            return True, self._extract_json(repaired)
        except Exception:
            return False, {}

    def _invoke_agent_json(
        self,
        agent_name: str,
        agent_id: str,
        instruction: str,
        payload_text: str,
        timeout_sec: int = 20,
    ) -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
        delays = [0, 2, 4]
        last_error: Dict[str, Any] = {}
        for i, delay in enumerate(delays):
            if delay:
                time.sleep(delay)
            messages = [
                {
                    "role": "system",
                    "content": (
                        f"You are {agent_name}. agent_id={agent_id}. "
                        "Return strict JSON only. Do not include markdown."
                    ),
                },
                {"role": "user", "content": instruction + "\n\n" + payload_text},
            ]
            try:
                resp = self._post_chat(messages, timeout_sec=timeout_sec)
                if not resp.get("ok"):
                    last_error = resp
                    continue
                data = resp["data"]
                content = data["choices"][0]["message"]["content"]
                try:
                    parsed = self._extract_json(content)
                except Exception:
                    repaired_ok, repaired = self._repair_json(content, timeout_sec=timeout_sec)
                    if not repaired_ok:
                        raise
                    parsed = repaired
                return True, parsed, {}
            except Exception as e:
                last_error = {"error": f"{agent_name} parse/call error: {str(e)}"}
                if i == len(delays) - 1:
                    break
        return False, {}, last_error

    def _build_case_id(self, t0_kst: str, user_facts: str) -> str:
        dt = datetime.fromisoformat(t0_kst.replace("Z", "+00:00"))
        prefix = dt.strftime("%Y%m%d-%H%M")
        digest = hashlib.sha1((t0_kst + user_facts[:200]).encode("utf-8")).hexdigest()[:4]
        return f"EFARS-{prefix}-{digest}"

    def _validate_classification(self, c: Dict[str, Any]) -> List[str]:
        required = [
            "is_reportable",
            "incident_type",
            "severity_class",
            "severity_decision_authority",
        ]
        return [k for k in required if k not in c]

    def _validate_regulations(self, r: Dict[str, Any]) -> List[str]:
        missing: List[str] = []
        clauses = r.get("applicable_clauses")
        if not isinstance(clauses, list):
            missing.append("applicable_clauses")
            return missing
        for idx, item in enumerate(clauses):
            if not isinstance(item, dict) or "source" not in item:
                missing.append(f"applicable_clauses[{idx}].source")
        return missing

    def _validate_timeline(self, t: Dict[str, Any]) -> List[str]:
        missing: List[str] = []
        if "initial_due" not in t:
            missing.append("initial_due")
        if "rca_report_due_offset_days" not in t:
            missing.append("rca_report_due_offset_days")
        return missing

    def _validate_writer_output(self, w: Dict[str, Any]) -> List[str]:
        required = [
            "report_markdown",
            "report_brief_markdown",
            # report_docx_path / report_txt_path / report_brief_path 는 항상 null — _apply_writer_defaults 로 처리
            "follow_up_actions",
            "decisions_requested",
            "assumptions_needed",
            "missing_fields",
            "self_check_score",
            "citations_used",
            "impact_grades",
            "internal_strengthened_applied",
        ]
        return [k for k in required if k not in w]

    def _apply_writer_defaults(self, w: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(w)
        out.setdefault("report_markdown", "[데이터 미확보]")
        out.setdefault("report_brief_markdown", "[데이터 미확보]")
        out.setdefault("report_docx_path", None)
        out.setdefault("report_txt_path", None)
        out.setdefault("report_brief_path", None)
        out.setdefault("follow_up_actions", [])
        out.setdefault("decisions_requested", [])
        out.setdefault("assumptions_needed", [])
        out.setdefault("missing_fields", [])
        out.setdefault("self_check_score", 0.0)
        out.setdefault("citations_used", [])
        out.setdefault("impact_grades", {})
        out.setdefault("internal_strengthened_applied", False)
        return out

    def _format_final_message(
        self,
        case_id: str,
        status_text: str,
        classification: Dict[str, Any],
        regulations: Dict[str, Any],
        timeline: Dict[str, Any],
        writer: Dict[str, Any],
        degraded_components: List[str],
        alerts: List[str],
        extra_notice: List[str],
    ) -> str:
        impact = writer.get("impact_grades", {})
        follow_ups = writer.get("follow_up_actions", [])
        decisions = writer.get("decisions_requested", [])
        assumptions = writer.get("assumptions_needed", [])
        citations = writer.get("citations", [])
        missing_fields = writer.get("missing_fields", [])
        self_check = writer.get("self_check_score", 0)

        lines: List[str] = []
        lines.append(f"[CASE] {case_id}")
        lines.append(f"[STATUS] {status_text}")
        lines.append(f"[INCIDENT TYPE] {classification.get('incident_type', '')}  (사내 세칙 제6조)")
        lines.append(
            f"[SEVERITY] {classification.get('severity_class', '')} · {classification.get('severity_response_level', '')}"
        )
        lines.append(f"[DECISION AUTHORITY] {classification.get('severity_decision_authority', '')}")
        strengthened = writer.get("internal_strengthened_applied", False)
        lines.append(f"[INTERNAL STRENGTHENED] {'적용중' if strengthened else '미적용'}")
        lines.append("[KEY DEADLINES]")
        lines.append(f"  - 1차보고:    {timeline.get('initial_due', '')}  (T0 + 12h, 사내 세칙 제11조)")
        lines.append(
            f"  - 경과보고:    {timeline.get('interim_first_due', '사고 변동 시 즉시')} (사내 세칙 제11조)"
        )
        lines.append("  - 종료보고:    조치 완료 시점 (사내 세칙 제11조)")
        lines.append("  - 원인분석:    종료일 + 21일 (사내 세칙 제18조)")
        lines.append(
            f"[IMPACT GRADES] 업무 {impact.get('업무', '')} · 고객 {impact.get('고객', '')} · 재무 {impact.get('재무', '')} · 규제 {impact.get('규제', '')}"
        )
        lines.append(
            "[RESPONSIBILITY] 총괄=IT운영부장 / 실무=IT사고대응반장 / 검토=준법감시부서 / 사고선포=비상대응위원장"
        )
        lines.append(f"[REPORT FILE - DOCX]  {writer.get('report_docx_path', '')}")
        lines.append(f"[REPORT FILE - TXT]   {writer.get('report_txt_path', '')}")
        lines.append(f"[REPORT FILE - BRIEF] {writer.get('report_brief_path', '')}")
        lines.append(f"[SELF CHECK] {self_check}/1.0")
        lines.append(
            f"[NEEDS REVIEW] {', '.join(missing_fields) if missing_fields else '없음'}"
        )
        lines.append(
            f"[DEGRADED] {', '.join(degraded_components) if degraded_components else '없음'}"
        )
        if alerts:
            lines.append("")
            lines.extend(alerts)
        if extra_notice:
            lines.append("")
            lines.extend(extra_notice)
        lines.append("")
        lines.append("[BRIEF — 임원·실무 단문 공유용]")
        lines.append(writer.get("report_brief_markdown", ""))
        lines.append("")
        lines.append("[REPORT BODY]")
        report_markdown = writer.get("report_markdown", "")
        lines.append(report_markdown)

        if re.search(r"\d{1,3}(,\d{3})*\s*원", report_markdown):
            lines.append("[검토필요] 정량 금액 포함 — 가드레일 위반 가능")

        lines.append("")
        lines.append("[FOLLOW UP ACTIONS]")
        if follow_ups:
            for a in follow_ups:
                if isinstance(a, dict):
                    basis = a.get("basis", {}) if isinstance(a.get("basis", {}), dict) else {}
                    lines.append(
                        f"- [ ] {a.get('action', '')} (시한: {a.get('due_kst', '')}, 담당: {a.get('responsible_role', '')}, 기관: {a.get('agency', '')})"
                    )
                    lines.append(
                        f"      [근거: {basis.get('law', '')} {basis.get('article', '')}]"
                    )
                else:
                    lines.append(f"- [ ] {str(a)}")
        else:
            lines.append("- [ ]")

        lines.append("")
        lines.append("[DECISIONS REQUESTED]")
        if decisions:
            for d in decisions:
                if isinstance(d, dict):
                    lines.append(
                        f"- [ ] {d.get('decision', '')} · 권고: {d.get('recommendation', '')} · 시한: {d.get('deadline_kst', '')}"
                    )
                    lines.append(f"      사유: {d.get('rationale', '')}")
                else:
                    lines.append(f"- [ ] {str(d)}")
        else:
            lines.append("- [ ]")

        lines.append("")
        lines.append("[ASSUMPTIONS NEEDED]")
        if assumptions:
            for item in assumptions:
                lines.append(f"- {item}")
        else:
            lines.append("- []")

        internal_count = len([c for c in citations if isinstance(c, dict) and c.get("type") == "internal"])
        external_count = len([c for c in citations if isinstance(c, dict) and c.get("type") == "external"])
        lines.append("")
        lines.append(
            f"[CITATIONS COUNT] {len(citations)} (사내: {internal_count}건 / 외부: {external_count}건)"
        )

        if self_check < 0.75 or bool(missing_fields) or bool(degraded_components):
            lines.append("\n**검토가 필요합니다**")

        return "\n".join(lines)

    def run_orchestration(
        self,
        user_facts: str,
        t0_kst: str,
        additional_context: str = "",
    ) -> Dict[str, Any]:
        if not t0_kst:
            return {
                "status": "need_input",
                "question": "T0(사고 인지 시각 KST, ISO 8601)를 입력해주세요. 예: 2026-06-19T14:00:00+09:00",
                "missing_fields": ["T0_kst"],
            }

        case_id = self._build_case_id(t0_kst, user_facts)
        degraded_components: List[str] = []
        alerts: List[str] = []
        extra_notice: List[str] = []
        _t_start = time.time()
        print(f"[TIMER] orchestration start", flush=True)

        classifier_instruction = (
            "a2a_incident_classifier. Return JSON with keys: "
            "is_reportable, incident_type, severity_class, severity_response_level, "
            "severity_decision_authority, exclusion_basis, exclusion_clause_applied, "
            "missing_fields(array)."
        )
        _t0 = time.time()
        ok, classification, err = self._invoke_agent_json(
            "a2a_incident_classifier",
            self.incident_classifier_id,
            classifier_instruction,
            f"user_facts: {user_facts}\nadditional_context: {additional_context}",
        )
        print(f"[TIMER] incident-analyzer: {time.time()-_t0:.1f}s", flush=True)
        if not ok:
            return {
                "status": "error",
                "error": "incident-classifier 호출 실패",
                "error_detail": err,
            }

        missing_cls = self._validate_classification(classification)
        if missing_cls:
            ok2, classification2, _ = self._invoke_agent_json(
                "a2a_incident_classifier",
                self.incident_classifier_id,
                classifier_instruction,
                f"user_facts: {user_facts}\nadditional_context: {additional_context}\nmissing_keys: {missing_cls}",
            )
            if ok2:
                classification = classification2
            if self._validate_classification(classification):
                return {
                    "status": "error",
                    "error": "incident-classifier 형상 검증 실패",
                }

        if classification.get("is_reportable") is False:
            memo = (
                "본 사고는 다음 사유로 보고 대상이 아닙니다: "
                f"{classification.get('exclusion_basis', '')}\n"
                "적용 조항: "
                f"{classification.get('exclusion_clause_applied', '')}"
            )
            return {
                "status": "success",
                "case_id": case_id,
                "final_message": memo,
                "classification": classification,
                "regulations": {},
                "agent_inputs": {
                    "code-orchestrator": {"user_facts": user_facts, "t0_kst": t0_kst, "additional_context": additional_context},
                    "incident-analyzer": {"user_facts": user_facts, "additional_context": additional_context},
                    "regulation-finder": {},
                    "deadline-manager": {},
                    "report-writer": {},
                    "quality-supervisor": {},
                },
                "timeline": {},
                "degraded_components": degraded_components,
                "partial_results": False,
            }

        if classification.get("severity_class") in ["1등급", "2등급"]:
            alerts.append(
                "⚠️ **사고 등급: "
                f"{classification.get('severity_class')}** ({classification.get('severity_response_level', '')}).\n"
                "사내 세칙 제7조②에 따라 **비상대응위원장의 최종 등급 확정이 필요**하며,\n"
                "사내 세칙 제15조 5단계에 따라 **사고 선포 및 대응본부 가동 결정**이 즉시 필요합니다."
            )

        if (
            classification.get("exclusion_clause_applied") == "사내 세칙 제9조 3호"
            and "1개월 누적 발생 이력" in classification.get("missing_fields", [])
        ):
            extra_notice.append(
                "본 사고는 30만원 미만으로 1차 판정상 보고 제외이나, 사내 세칙 제9조 3호 단서에\n"
                "따라 **동일 이용자 또는 동일 수법으로 1개월 이내 3회 이상 발생** 시 누적 금액\n"
                "기준으로 재판정되어 보고 대상이 될 수 있습니다. 누적 이력을 확인 후 재실행을 권장합니다."
            )

        def call_regulation() -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
            return self._invoke_agent_json(
                "a2a_regulation_search",
                self.regulation_search_id,
                "a2a_regulation_search. Return JSON with key applicable_clauses(array). each clause must have source.",
                "classification: " + json.dumps(classification, ensure_ascii=False) + f"\nuser_facts: {user_facts}",
            )

        def call_deadline() -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
            return self._invoke_agent_json(
                "a2a_deadline_manager",
                self.deadline_manager_id,
                "a2a_deadline_manager. Return JSON with keys: initial_due(ISO8601), interim_first_due, rca_report_due_offset_days.",
                f"T0_kst: {t0_kst}\nclassification: {json.dumps(classification, ensure_ascii=False)}",
            )

        _t1 = time.time()
        with ThreadPoolExecutor(max_workers=2) as pool:
            reg_future = pool.submit(call_regulation)
            dead_future = pool.submit(call_deadline)
            reg_ok, regulations, reg_err = reg_future.result()
            dead_ok, timeline, dead_err = dead_future.result()
        print(f"[TIMER] regulation-finder + deadline-manager (parallel): {time.time()-_t1:.1f}s", flush=True)

        if not reg_ok:
            degraded_components.append("regulation-search")
            regulations = {}
        if not dead_ok:
            degraded_components.append("deadline-manager")
            timeline = {}

        if reg_ok:
            missing_reg = self._validate_regulations(regulations)
            if missing_reg:
                reg_ok2, reg2, _ = call_regulation()
                if reg_ok2:
                    regulations = reg2
                if self._validate_regulations(regulations):
                    degraded_components.append("regulation-search")
                    regulations = {}

        if dead_ok:
            missing_tl = self._validate_timeline(timeline)
            if missing_tl:
                dead_ok2, tl2, _ = call_deadline()
                if dead_ok2:
                    timeline = tl2
                if self._validate_timeline(timeline):
                    degraded_components.append("deadline-manager")
                    timeline = {}

        partial_results = bool(degraded_components)

        writer_instruction = (
            "ROLE: 전자금융사고 보고서 작성자. 분류/규정/기한 입력으로 별지 제2호서식(약식) 초안 JSON 생성. "
            "사고 판정/법령 해석/기한 산정은 하지 않는다.\n"
            "DATA RULE: 데이터 없으면 추측 금지, 반드시 '[데이터 미확보]'로 표기.\n"
            "BODY RULE: 5섹션 약식 템플릿 유지, 문단형 장문 금지, 핵심만 간략히.\n"
            "OUTPUT RULE: 반드시 JSON 객체만 반환. markdown code fence 금지. trailing text 금지.\n"
            "JSON KEYS(required): report_markdown, report_brief_markdown, report_docx_path, report_txt_path, report_brief_path, "
            "executive_summary, responsibility_matrix, follow_up_actions, decisions_requested, assumptions_needed, "
            "missing_fields, self_check_score, citations_used, impact_grades, internal_strengthened_applied.\n"
            "SHAPE LIMITS: decisions_requested<=3, follow_up_actions<=3, citations_used<=5, missing_fields<=20.\n"
            "TEXT LIMITS: report_markdown 400~700자, report_brief_markdown 150자 이하.\n"
            "ENUM RULE: responsible_role은 IT운영부장/IT사고대응반장/준법감시부서/비상대응위원장만 허용.\n"
            "JSON SAFETY: null은 JSON null 사용. 'A | null' 같은 표기 금지. self_check_score는 숫자만.\n"
            "TOOL AVAILABILITY: Code Interpreter/File Search 미가용 런타임이면 파일 경로 3개는 null로 두고 "
            "missing_fields에 'tool_unavailable' 기록. 파일 생성한 척 금지.\n"
            "CITATION RULE: 인용은 입력 regulations의 실제 항목만 사용. exact_quote는 120자 이내."
        )
        writer_payload = (
            f"case_id: {case_id}\n"
            f"user_facts: {user_facts}\n"
            f"classification: {json.dumps(classification, ensure_ascii=False)}\n"
            f"regulations: {json.dumps(regulations, ensure_ascii=False)}\n"
            f"timeline: {json.dumps(timeline, ensure_ascii=False)}\n"
            f"partial_results: {str(partial_results).lower()}\n"
            f"degraded_components: {json.dumps(degraded_components, ensure_ascii=False)}"
        )
        _t2 = time.time()
        writer_ok, writer_data, writer_err = self._invoke_agent_json(
            "a2a_report_writer",
            self.report_writer_id,
            writer_instruction,
            writer_payload,
            timeout_sec=60,
        )
        print(f"[TIMER] report-writer 1차: {time.time()-_t2:.1f}s", flush=True)
        if not writer_ok:
            return {
                "status": "error",
                "error": "report-writer 호출 실패",
                "error_detail": writer_err,
            }

        missing_writer_keys = self._validate_writer_output(writer_data)
        if missing_writer_keys:
            print(f"[TIMER] report-writer 2차 재호출 (누락키: {missing_writer_keys})", flush=True)
            _t2b = time.time()
            writer_ok2, writer_data2, _ = self._invoke_agent_json(
                "a2a_report_writer",
                self.report_writer_id,
                writer_instruction + f"\nMISSING_KEYS: {missing_writer_keys}. Return full JSON keys.",
                writer_payload,
                timeout_sec=60,
            )
            print(f"[TIMER] report-writer 2차: {time.time()-_t2b:.1f}s", flush=True)
            if writer_ok2:
                writer_data = writer_data2

        writer_data = self._apply_writer_defaults(writer_data)

        # --- Foundry Responses API로 report-writer 직접 호출하여 DOCX 생성 ---
        _t_docx = time.time()
        docx_ok, docx_bytes, docx_info = self._invoke_writer_via_responses_api(
            payload_text=(
                f"case_id: {case_id}\n"
                f"user_facts: {user_facts}\n"
                f"classification: {json.dumps(classification, ensure_ascii=False)}\n"
                f"regulations: {json.dumps(regulations, ensure_ascii=False)}\n"
                f"timeline: {json.dumps(timeline, ensure_ascii=False)}\n"
                f"partial_results: {str(partial_results).lower()}\n"
                f"degraded_components: {json.dumps(degraded_components, ensure_ascii=False)}"
            ),
            timeout_sec=120,
        )
        print(f"[TIMER] responses_api docx: {time.time()-_t_docx:.1f}s  ok={docx_ok}", flush=True)
        if docx_ok:
            writer_data["_docx_bytes"] = docx_bytes
            writer_data["_docx_filename"] = docx_info
        # -----------------------------------------------------------------------

        print(f"[TIMER] total orchestration: {time.time()-_t_start:.1f}s", flush=True)

        final_message = self._format_final_message(
            case_id=case_id,
            status_text="보고대상",
            classification=classification,
            regulations=regulations,
            timeline=timeline,
            writer=writer_data,
            degraded_components=degraded_components,
            alerts=alerts,
            extra_notice=extra_notice,
        )

        agent_inputs = {
            "code-orchestrator": {
                "user_facts": user_facts,
                "t0_kst": t0_kst,
                "additional_context": additional_context,
            },
            "incident-analyzer": {
                "user_facts": user_facts,
                "additional_context": additional_context,
            },
            "regulation-finder": {
                "classification": classification,
                "user_facts": user_facts,
            },
            "deadline-manager": {
                "T0_kst": t0_kst,
                "classification": classification,
            },
            "report-writer": {
                "case_id": case_id,
                "user_facts": user_facts,
                "classification": classification,
                "regulations": regulations,
                "timeline": timeline,
                "partial_results": partial_results,
                "degraded_components": degraded_components,
            },
            "quality-supervisor": {
                "case_id": case_id,
                "classification": classification,
                "report_writer": writer_data,
            },
        }

        return {
            "status": "success",
            "case_id": case_id,
            "classification": classification,
            "regulations": regulations,
            "timeline": timeline,
            "report_writer": writer_data,
            "degraded_components": degraded_components,
            "partial_results": partial_results,
            "final_message": final_message,
            "agent_inputs": agent_inputs,
        }
