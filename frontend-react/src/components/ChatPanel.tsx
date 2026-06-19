import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, RotateCcw, Bot, User } from 'lucide-react';
import type { Message } from '../types';

const WELCOME_MSG: Message = {
  id: 'welcome',
  role: 'ai',
  content: '안녕하세요! 전자금융사고 보고 어시스턴트입니다.\n\n발생한 사고 내용을 자유롭게 입력해주세요. AI 에이전트가 자동으로 사고를 분류하고, 관련 규정을 검색하여 보고서를 작성해드립니다.\n\n예시: "오늘 오전 9시에 기업인터넷뱅킹에서 DDoS 공격으로 2시간 동안 서비스 장애가 발생했습니다."',
  timestamp: new Date(),
};

interface ChatPanelProps {
  onSubmit: (text: string, caseId: string | null) => void;
  isLoading: boolean;
  caseId: string | null;
  analysisResult: Record<string, unknown> | null;
}

function TypingMessage({ text }: { text: string }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  const idx = useRef(0);

  useEffect(() => {
    idx.current = 0;
    setDisplayed('');
    setDone(false);
    const interval = setInterval(() => {
      if (idx.current < text.length) {
        setDisplayed(text.slice(0, idx.current + 1));
        idx.current += 1;
      } else {
        setDone(true);
        clearInterval(interval);
      }
    }, 12);
    return () => clearInterval(interval);
  }, [text]);

  return (
    <span className={!done ? 'typing-cursor' : ''}>
      {displayed.split('\n').map((line, i) => (
        <span key={i}>
          {line}
          {i < displayed.split('\n').length - 1 && <br />}
        </span>
      ))}
    </span>
  );
}

function MessageBubble({ msg, isNew }: { msg: Message; isNew?: boolean }) {
  const isUser = msg.role === 'user';
  const time = msg.timestamp.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* 아바타 */}
      <div
        className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-1"
        style={{ background: isUser ? 'var(--bnk-accent)15' : 'var(--bnk-surface-2)', border: `1px solid ${isUser ? 'var(--bnk-accent)' : 'var(--bnk-border)'}` }}
      >
        {isUser
          ? <User size={14} color="var(--bnk-accent)" />
          : <Bot size={14} color="var(--bnk-text-muted)" />
        }
      </div>

      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className="rounded-2xl px-4 py-3 text-sm leading-relaxed"
          style={{
            background: isUser ? 'color-mix(in srgb, var(--bnk-accent) 8%, transparent)' : 'var(--bnk-surface)',
            border: `0.5px solid ${isUser ? 'color-mix(in srgb, var(--bnk-accent) 40%, transparent)' : 'var(--bnk-border)'}`,
            color: 'var(--bnk-text)',
          }}
        >
          {isNew && !isUser
            ? <TypingMessage text={msg.content} />
            : msg.content.split('\n').map((line, i) => (
                <span key={i}>{line}{i < msg.content.split('\n').length - 1 && <br />}</span>
              ))
          }
        </div>
        <span className="text-xs mt-1 px-1" style={{ color: 'var(--bnk-text-faint)' }}>{time}</span>
      </div>
    </motion.div>
  );
}

export function ChatPanel({ onSubmit, isLoading, caseId, analysisResult }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MSG]);
  const [input, setInput] = useState('');
  const [newMsgId, setNewMsgId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const prevCaseId = useRef<string | null>(null);

  // 분석 결과가 오면 AI 응답 메시지 추가
  useEffect(() => {
    if (!analysisResult || !caseId) return;
    if (prevCaseId.current === caseId) return;
    prevCaseId.current = caseId;

    const ia = (analysisResult.incident_analysis ?? {}) as Record<string, unknown>;
    const rw = (analysisResult.report_writer ?? {}) as Record<string, unknown>;

    const grade = (ia.incident_grade as string) ?? '-';
    const reportable = (ia.is_reportable as boolean) ? '✅ 보고 의무 있음' : '⬜ 보고 의무 없음';
    const summary = (rw.report_brief_markdown as string) ?? (rw.executive_summary as string) ?? '';
    const timeline = (ia.timeline as Record<string, string>) ?? {};
    const initial = timeline.initial_due ?? '-';
    const intermediate = timeline.intermediate_due ?? '-';

    const content = [
      `📋 **분석 완료** — 사고 ID: \`${caseId}\``,
      '',
      `• 사고 등급: **${grade}**`,
      `• 보고 의무: ${reportable}`,
      `• 최초보고 마감: ${initial}`,
      `• 중간보고 마감: ${intermediate}`,
      '',
      summary ? `**요약**\n${summary}` : '',
      '',
      '▶ 오른쪽 패널의 **보고서 다운로드 (DOCX)** 버튼으로 파일을 받으실 수 있습니다.',
    ].filter(l => l !== undefined).join('\n').replace(/\n{3,}/g, '\n\n').trim();

    const aiMsg: Message = {
      id: `ai-${Date.now()}`,
      role: 'ai',
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, aiMsg]);
    setNewMsgId(aiMsg.id);
  }, [caseId, analysisResult]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    // 분석 중 AI 메시지
    const thinkingMsg: Message = {
      id: `thinking-${Date.now()}`,
      role: 'ai',
      content: '⏳ 에이전트들이 사고를 분석하고 있습니다. 잠시 기다려주세요...',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg, thinkingMsg]);
    setNewMsgId(thinkingMsg.id);
    setInput('');
    onSubmit(text, caseId);
  }, [input, isLoading, caseId, onSubmit]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleReset = () => {
    setMessages([WELCOME_MSG]);
    setInput('');
    setNewMsgId(null);
  };

  // textarea 높이 자동 조절
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  };

  return (
    <div className="flex flex-col h-full glass-dark rounded-2xl overflow-hidden">
      {/* 헤더 */}
      <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--bnk-border)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'color-mix(in srgb, var(--bnk-accent) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--bnk-accent) 30%, transparent)' }}>
            <Bot size={16} color="var(--bnk-accent)" />
          </div>
          <div>
            <h2 className="font-bold text-sm" style={{ color: 'var(--bnk-text)' }}>전자금융사고 보고 어시스턴트</h2>
            <p className="text-xs" style={{ color: 'var(--bnk-text-muted)' }}>멀티 에이전트 AI 시스템</p>
          </div>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
          style={{ color: 'var(--bnk-text-muted)', border: '0.5px solid var(--bnk-border)' }}
        >
          <RotateCcw size={13} />
          새 대화
        </button>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence>
          {messages.map(msg => (
            <MessageBubble
              key={msg.id}
              msg={msg}
              isNew={msg.id === newMsgId}
            />
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* 입력창 */}
      <div className="px-4 py-4 border-t" style={{ borderColor: 'var(--bnk-border)' }}>
        <div
          className="flex items-end gap-2 rounded-xl px-3 py-2"
          style={{ background: 'var(--bnk-surface-2)', border: '0.5px solid var(--bnk-border)' }}
        >
          <button
            onClick={() => fileRef.current?.click()}
            className="flex-shrink-0 p-1.5 rounded-lg transition-colors mb-0.5"
            style={{ color: 'var(--bnk-text-faint)' }}
            title="파일 첨부"
          >
            <Paperclip size={16} />
          </button>
          <input ref={fileRef} type="file" className="hidden" accept=".pdf,.txt,.docx,.xlsx" />
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="전자금융사고 내용을 입력하세요..."
            disabled={isLoading}
            className="flex-1 bg-transparent text-sm placeholder:text-[color:var(--bnk-text-faint)] resize-none outline-none leading-relaxed py-1"
            style={{ color: 'var(--bnk-text)' }}
            style={{ maxHeight: '120px' }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors mb-0.5 disabled:opacity-30"
            style={{ background: input.trim() && !isLoading ? 'var(--bnk-accent)' : 'var(--bnk-border)', color: '#FFFFFF' }}
          >
            <Send size={15} color={input.trim() && !isLoading ? '#0A0E1A' : '#4B5563'} />
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1.5 px-1">Enter로 전송 · Shift+Enter로 줄바꿈</p>
      </div>
    </div>
  );
}
