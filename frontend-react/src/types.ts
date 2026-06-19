export type AgentStatus = 'idle' | 'running' | 'done' | 'error';

export interface AgentState {
  id: string;
  name: string;
  statusText: string;
  progress: number;
  status: AgentStatus;
  logs: string[];
  color: string;
  icon: string;
}

export interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface AnalysisResult {
  case_id: string;
  incident_analysis?: Record<string, unknown>;
  report_writer?: Record<string, unknown>;
}
