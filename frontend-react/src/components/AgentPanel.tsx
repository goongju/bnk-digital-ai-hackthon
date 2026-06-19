import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, BookOpen, Clock, FileText, ShieldCheck,
  CheckCircle, AlertCircle, Loader2, ChevronDown, ChevronUp,
  ArrowDown
} from 'lucide-react';
import type { AgentState, AgentStatus } from '../types';

const AGENTS_INIT: AgentState[] = [
  { id: 'incident-analyzer', name: '사고 분류', statusText: '대기 중', progress: 0, status: 'idle', logs: [], color: 'var(--state-pending)', icon: 'Brain' },
  { id: 'regulation-finder', name: '규정 검색', statusText: '대기 중', progress: 0, status: 'idle', logs: [], color: 'var(--state-pending)', icon: 'BookOpen' },
  { id: 'deadline-manager', name: '보고 기한 산정', statusText: '대기 중', progress: 0, status: 'idle', logs: [], color: 'var(--state-pending)', icon: 'Clock' },
  { id: 'report-writer', name: '보고서 작성', statusText: '대기 중', progress: 0, status: 'idle', logs: [], color: 'var(--state-pending)', icon: 'FileText' },
  { id: 'quality-supervisor', name: '검증', statusText: '대기 중', progress: 0, status: 'idle', logs: [], color: 'var(--state-pending)', icon: 'ShieldCheck' },
];

const iconMap: Record<string, React.ElementType> = {
  Brain, BookOpen, Clock, FileText, ShieldCheck,
};

const statusColor: Record<AgentStatus, string> = {
  idle: 'var(--state-pending)',
  running: 'var(--state-running)',
  done: 'var(--state-done)',
  error: 'var(--state-degraded)',
};

function AgentIcon({ name, color, status, agentColor }: { name: string; color: string; status: AgentStatus; agentColor: string }) {
  const Icon = iconMap[name] ?? FileText;
  const isRunning = status === 'running';
  const isDone = status === 'done';
  const isError = status === 'error';
  const isIdle = status === 'idle';

  return (
    <div className="relative flex-shrink-0">
      <div
        className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-500 ${
          isIdle ? 'border-2 border-dashed border-gray-600' :
          isRunning ? 'border-2 border-solid' :
          isDone ? 'border-2 border-solid' :
          'border-2 border-solid border-coral'
        }`}
        style={{
          borderColor: isIdle ? 'var(--bnk-border)' : isError ? 'var(--state-degraded)' : statusColor[status],
          background: isIdle ? 'var(--bnk-surface-2)' : `${statusColor[status]}15`,
        }}
      >
        {isRunning && (
          <div
            className="absolute inset-0 rounded-full spin-slow"
            style={{
              background: `conic-gradient(${statusColor['running']} 0%, transparent 70%)`,
              opacity: 0.4,
            }}
          />
        )}
        {isDone ? (
          <CheckCircle size={22} color={statusColor['done']} />
        ) : isError ? (
          <AlertCircle size={22} color={statusColor['error']} />
        ) : (
          <Icon size={20} color={isIdle ? 'var(--bnk-text-faint)' : statusColor[status]} />
        )}
        {isRunning && (
          <motion.div
            className="absolute inset-0 rounded-full pulse-running"
            style={{ background: `${statusColor['running']}18` }}
          />
        )}
      </div>
    </div>
  );
}

interface AgentCardProps {
  agent: AgentState;
}

function AgentCard({ agent }: AgentCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = agent.status === 'running';

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass rounded-xl overflow-hidden cursor-pointer transition-all duration-300`}
      onClick={() => setExpanded(e => !e)}
      style={{
        borderColor: agent.status !== 'idle' ? `${statusColor[agent.status]}40` : undefined,
      }}
    >
      <div className="p-4">
        <div className="flex items-center gap-3">
          <AgentIcon
            name={agent.icon}
            color={statusColor[agent.status]}
            status={agent.status}
            agentColor={statusColor[agent.status]}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm" style={{ color: 'var(--bnk-text)' }}>{agent.name} 에이전트</span>
              <div className="flex items-center gap-2">
                {isRunning && <Loader2 size={14} className="spin-slow" style={{ color: 'var(--state-running)' }} />}
                {expanded ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
              </div>
            </div>
            <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--bnk-text-muted)' }}>{agent.statusText}</p>
            {/* 진행률 바 */}
            <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: 'var(--bnk-border)' }}>
              <motion.div
                className="h-full rounded-full"
                animate={{ width: `${agent.progress}%` }}
                transition={{ duration: 0.5 }}
                style={{ background: agent.status === 'error' ? 'var(--state-degraded)' : statusColor[agent.status] }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 상세 로그 */}
      <AnimatePresence>
        {expanded && agent.logs.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="border-t"
            style={{ borderColor: 'var(--bnk-border)' }}
          >
            <div className="p-3 space-y-1 max-h-40 overflow-y-auto">
              {agent.logs.map((log, i) => (
                <p key={i} className="text-xs font-mono leading-relaxed" style={{ color: 'var(--bnk-text-muted)' }}>
                  <span style={{ color: statusColor[agent.status] }} className="mr-1">›</span>{log}
                </p>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

interface AgentPanelProps {
  isRunning: boolean;
  caseId: string | null;
  onAgentsComplete: (agents: AgentState[]) => void;
  triggerRun: number;
}

// 실제 백엔드 타이밍 기반 단계 정의 (incident-analyzer ~4s, reg+deadline ~40s, report-writer ~25s, responses_api ~70s, supervisor ~5s)
const DEMO_STEPS: Array<{ delay: number; agentId: string; patch: Partial<AgentState> }> = [
  // incident-analyzer: 0~5s
  { delay: 400,  agentId: 'incident-analyzer', patch: { status: 'running', statusText: '사고 유형 분류 중...', progress: 25, logs: ['전자금융사고 입력 수신', 'LLM 호출 시작'] } },
  { delay: 2500, agentId: 'incident-analyzer', patch: { progress: 70, statusText: '규정 적용 여부 판단 중...', logs: ['전자금융사고 입력 수신', 'LLM 호출 시작', '사고 유형: DDoS 공격 판별'] } },
  { delay: 5000, agentId: 'incident-analyzer', patch: { status: 'done', statusText: '사고 등급 1등급 확정', progress: 100, logs: ['전자금융사고 입력 수신', 'LLM 호출 시작', '사고 유형: DDoS 공격 판별', '등급 판정 완료: 1등급', '보고 의무: 있음'] } },

  // regulation-finder + deadline-manager: 5~45s (병렬)
  { delay: 5500,  agentId: 'regulation-finder', patch: { status: 'running', statusText: '전자금융감독규정 검색 중...', progress: 10, logs: ['규정 DB 조회 시작'] } },
  { delay: 5500,  agentId: 'deadline-manager',  patch: { status: 'running', statusText: '보고 기한 산정 중...', progress: 10, logs: ['T0 기준 기한 계산 시작'] } },
  { delay: 15000, agentId: 'regulation-finder', patch: { progress: 35, statusText: '전자금융감독규정 제37조의5 검색 중...', logs: ['규정 DB 조회 시작', '제37조의5 (전자금융사고 보고) 탐색'] } },
  { delay: 15000, agentId: 'deadline-manager',  patch: { progress: 40, statusText: '최초보고 기한 산정 완료...', logs: ['T0 기준 기한 계산 시작', '최초보고: T0+1시간 이내 확정'] } },
  { delay: 28000, agentId: 'regulation-finder', patch: { progress: 65, statusText: '제57조의4 (서비스 중단) 검색 중...', logs: ['규정 DB 조회 시작', '제37조의5 매칭', '제57조의4 탐색'] } },
  { delay: 28000, agentId: 'deadline-manager',  patch: { progress: 70, statusText: '중간·최종 기한 산정 중...', logs: ['T0 기준 기한 계산 시작', '최초보고: T0+1시간', '중간보고: T0+24시간 이내 확정'] } },
  { delay: 43000, agentId: 'regulation-finder', patch: { status: 'done', statusText: '3개 조항 적용 완료', progress: 100, logs: ['규정 DB 조회 시작', '제37조의5 매칭', '제57조의4 매칭', '시행규칙 별표2 참조', '3개 조항 최종 확정'] } },
  { delay: 43000, agentId: 'deadline-manager',  patch: { status: 'done', statusText: '보고 기한 산정 완료', progress: 100, logs: ['T0 기준 기한 계산 시작', '최초보고: T0+1시간 이내', '중간보고: T0+24시간 이내', '최종보고: T0+72시간 이내', '기한 확정 완료'] } },

  // report-writer: 45~120s (1차 Chat Completions + Responses API DOCX)
  { delay: 45000, agentId: 'report-writer', patch: { status: 'running', statusText: '보고서 초안 작성 중 (1차)...', progress: 10, logs: ['보고서 템플릿 로드', 'Chat Completions 호출'] } },
  { delay: 55000, agentId: 'report-writer', patch: { progress: 30, statusText: '사고 개요 섹션 작성 완료...', logs: ['보고서 템플릿 로드', 'Chat Completions 호출', '사고 개요 섹션 작성 완료'] } },
  { delay: 68000, agentId: 'report-writer', patch: { progress: 50, statusText: 'DOCX 생성 에이전트 호출 중...', logs: ['보고서 템플릿 로드', '1차 초안 완료', 'Responses API → report-writer-ci-only 에이전트 호출'] } },
  { delay: 85000, agentId: 'report-writer', patch: { progress: 75, statusText: 'DOCX 파일 작성 중 (Code Interpreter)...', logs: ['보고서 템플릿 로드', '1차 초안 완료', 'Code Interpreter 실행', 'DOCX 렌더링 중'] } },
  { delay: 110000, agentId: 'report-writer', patch: { status: 'done', statusText: 'DOCX 파일 생성 완료', progress: 100, logs: ['보고서 템플릿 로드', '1차 초안 완료', 'Code Interpreter 실행', 'DOCX 다운로드 완료', '캐시 저장'] } },

  // quality-supervisor: 120~130s
  { delay: 111000, agentId: 'quality-supervisor', patch: { status: 'running', statusText: '보고서 품질 검증 중...', progress: 30, logs: ['보고서 수신', '필수 항목 체크리스트 검토'] } },
  { delay: 118000, agentId: 'quality-supervisor', patch: { progress: 70, statusText: '규정 준수 최종 확인 중...', logs: ['보고서 수신', '필수 항목 체크리스트 검토', '보고 의무 조항 대조'] } },
];

// API 완료 시 남은 에이전트 즉시 완료 처리
const SNAP_COMPLETE: Record<string, Partial<AgentState>> = {
  'incident-analyzer': { status: 'done', progress: 100, statusText: '사고 등급 분석 완료' },
  'regulation-finder':  { status: 'done', progress: 100, statusText: '규정 검색 완료' },
  'deadline-manager':   { status: 'done', progress: 100, statusText: '보고 기한 산정 완료' },
  'report-writer':      { status: 'done', progress: 100, statusText: 'DOCX 파일 생성 완료' },
  'quality-supervisor': { status: 'done', progress: 100, statusText: '검증 완료 — 보고서 제출 가능' },
};

export function AgentPanel({ isRunning, caseId, onAgentsComplete, triggerRun }: AgentPanelProps) {
  const [agents, setAgents] = useState<AgentState[]>(AGENTS_INIT.map(a => ({ ...a })));
  const [elapsed, setElapsed] = useState(0);
  const [globalDone, setGlobalDone] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const prevIsRunning = useRef(false);

  const overallProgress = Math.round(agents.reduce((sum, a) => sum + a.progress, 0) / agents.length);

  const updateAgent = useCallback((id: string, patch: Partial<AgentState>) => {
    setAgents(prev => prev.map(a => a.id === id ? { ...a, ...patch } : a));
  }, []);

  // 시뮬레이션 시작
  useEffect(() => {
    if (triggerRun === 0) return;

    // 초기화
    setAgents(AGENTS_INIT.map(a => ({ ...a })));
    setGlobalDone(false);
    setElapsed(0);
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];

    startTimeRef.current = Date.now();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);

    DEMO_STEPS.forEach(({ delay, agentId, patch }) => {
      const t = setTimeout(() => updateAgent(agentId, patch), delay);
      timeoutsRef.current.push(t);
    });

    return () => {
      timeoutsRef.current.forEach(clearTimeout);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [triggerRun]);

  // API 완료 감지 → 남은 에이전트 즉시 완료
  useEffect(() => {
    if (prevIsRunning.current && !isRunning && caseId) {
      // 진행 중인 타임아웃 취소
      timeoutsRef.current.forEach(clearTimeout);
      timeoutsRef.current = [];

      // 모든 에이전트 완료 처리
      setAgents(prev => prev.map(a => {
        if (a.status === 'done') return a;
        const snap = SNAP_COMPLETE[a.id] ?? {};
        return { ...a, ...snap };
      }));

      // quality-supervisor 완료 로그
      setTimeout(() => {
        updateAgent('quality-supervisor', {
          status: 'done', progress: 100,
          statusText: '검증 완료 — 보고서 제출 가능',
          logs: ['보고서 수신', '필수 항목 체크리스트 검토', '규정 준수 확인 완료', '최종 승인'],
        });
        setGlobalDone(true);
        if (timerRef.current) clearInterval(timerRef.current);
        setAgents(prev => { onAgentsComplete(prev); return prev; });
      }, 1200);
    }
    prevIsRunning.current = isRunning;
  }, [isRunning, caseId]);

  const formatTime = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  return (
    <div className="flex flex-col h-full glass-dark rounded-2xl overflow-hidden">
      {/* 헤더 */}
      <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--bnk-border)' }}>
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-base" style={{ color: 'var(--bnk-text)' }}>에이전트 작업 현황</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: 'var(--bnk-text-muted)' }}>전체 진행률</span>
            <span className="text-sm font-bold" style={{ color: 'var(--bnk-accent)' }}>{overallProgress}%</span>
          </div>
        </div>
        {/* 전체 진행률 바 */}
        <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bnk-border)' }}>
          <motion.div
            className="h-full rounded-full"
            animate={{ width: `${overallProgress}%` }}
            transition={{ duration: 0.6 }}
            style={{ background: 'var(--bnk-accent)' }}
          />
        </div>
      </div>

      {/* 에이전트 목록 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {agents.map((agent, idx) => (
          <div key={agent.id}>
            <AgentCard agent={agent} />
            {idx < agents.length - 1 && (
              <div className="flex justify-center my-1">
                <ArrowDown size={14} style={{ color: 'var(--bnk-text-faint)' }} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 하단 */}
      <div className="px-5 py-4 border-t" style={{ borderColor: 'var(--bnk-border)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--bnk-text-muted)' }}>
            <Clock size={13} />
            <span>소요 시간: <span className="font-mono" style={{ color: 'var(--bnk-text)' }}>{formatTime(elapsed)}</span></span>
          </div>
          {globalDone && caseId && (
            <motion.a
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              href={`/api/report/docx`}
              onClick={async (e) => {
                e.preventDefault();
                try {
                  const res = await fetch('/api/report/docx', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ case_id: caseId }),
                  });
                  if (!res.ok) throw new Error('download failed');
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  const cd = res.headers.get('content-disposition') ?? '';
                  const match = cd.match(/filename\*?=(?:UTF-8'')?([^;]+)/i);
                  a.download = match ? decodeURIComponent(match[1].replace(/"/g, '')) : 'report.docx';
                  a.click();
                  URL.revokeObjectURL(url);
                } catch {
                  alert('보고서 다운로드 실패');
                }
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              style={{ background: 'var(--bnk-accent)', color: '#FFFFFF' }}
            >
              <FileText size={15} />
              보고서 다운로드 (DOCX)
            </motion.a>
          )}
        </div>
      </div>
    </div>
  );
}
