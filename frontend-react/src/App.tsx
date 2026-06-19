import { useState, useCallback, useEffect, useRef } from 'react'
import { Sun, Moon } from 'lucide-react'
import { ChatPanel } from './components/ChatPanel'
import { AgentPanel } from './components/AgentPanel'
import type { AgentState } from './types'
import './index.css'

export default function App() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [isLoading, setIsLoading] = useState(false)
  const [caseId, setCaseId] = useState<string | null>(null)
  const [analysisResult, setAnalysisResult] = useState<Record<string, unknown> | null>(null)
  const [triggerRun, setTriggerRun] = useState(0)
  const [activeTab, setActiveTab] = useState<'chat' | 'agents'>('chat')

  // data-theme 속성을 html 요소에 반영
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const handleSubmit = useCallback(async (text: string) => {
    setIsLoading(true)
    setTriggerRun(n => n + 1)

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ incident_description: text, t0_kst: new Date().toISOString() }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const resultData = (data?.data ?? data) as Record<string, unknown>
      setCaseId((resultData.case_id as string) ?? null)
      setAnalysisResult(resultData)
    } catch (err) {
      console.error('분석 실패:', err)
      setAnalysisResult({ error: String(err) })
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleAgentsComplete = useCallback((_agents: AgentState[]) => {}, [])

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'var(--bnk-bg)', color: 'var(--bnk-text)' }}
    >
      {/* 상단 헤더 */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b"
        style={{
          background: 'var(--bnk-surface)',
          borderColor: 'var(--bnk-border)',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs"
            style={{ background: 'var(--bnk-accent)', color: '#FFFFFF' }}
          >
            BNK
          </div>
          <div>
            <h1 className="text-sm font-bold" style={{ color: 'var(--bnk-text)' }}>
              전자금융사고 보고 자동화 시스템
            </h1>
            <p className="text-xs" style={{ color: 'var(--bnk-text-muted)' }}>
              Multi-Agent AI Pipeline · BNK캐피탈
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* 모바일 탭 토글 */}
          <div
            className="flex md:hidden rounded-lg overflow-hidden"
            style={{ border: '0.5px solid var(--bnk-border)' }}
          >
            {(['chat', 'agents'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className="px-3 py-1.5 text-xs font-medium transition-colors"
                style={{
                  background: activeTab === tab ? 'var(--bnk-accent)' : 'transparent',
                  color: activeTab === tab ? '#FFFFFF' : 'var(--bnk-text-muted)',
                }}
              >
                {tab === 'chat' ? '대화' : '에이전트'}
              </button>
            ))}
          </div>

          {/* 다크/라이트 토글 */}
          <button
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            className="p-2 rounded-lg transition-colors"
            style={{
              background: 'var(--bnk-surface-2)',
              color: 'var(--bnk-text-muted)',
              border: '0.5px solid var(--bnk-border)',
            }}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </div>
      </header>

      {/* 메인 콘텐츠 */}
      <main className="flex-1 p-4 md:p-6 overflow-hidden" style={{ height: 'calc(100vh - 60px)' }}>
        {/* 데스크탑: 2분할 */}
        <div className="hidden md:grid grid-cols-2 gap-5 h-full">
          <ChatPanel
            onSubmit={handleSubmit}
            isLoading={isLoading}
            caseId={caseId}
            analysisResult={analysisResult}
          />
          <AgentPanel
            isRunning={isLoading}
            caseId={caseId}
            onAgentsComplete={handleAgentsComplete}
            triggerRun={triggerRun}
          />
        </div>

        {/* 모바일: 탭 전환 */}
        <div className="md:hidden h-full">
          {activeTab === 'chat' ? (
            <ChatPanel
              onSubmit={handleSubmit}
              isLoading={isLoading}
              caseId={caseId}
              analysisResult={analysisResult}
            />
          ) : (
            <AgentPanel
              isRunning={isLoading}
              caseId={caseId}
              onAgentsComplete={handleAgentsComplete}
              triggerRun={triggerRun}
            />
          )}
        </div>
      </main>

      {/* BNK캐피탈 로고 (우하단) */}
      <div
        className="fixed bottom-5 right-5 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
        style={{
          background: 'var(--bnk-surface)',
          border: '0.5px solid var(--bnk-border)',
          color: 'var(--bnk-text-muted)',
        }}
      >
        <div
          className="w-4 h-4 rounded flex items-center justify-center text-[9px] font-bold"
          style={{ background: 'var(--bnk-accent)', color: '#FFFFFF' }}
        >
          B
        </div>
        BNK캐피탈
      </div>
    </div>
  )
}
