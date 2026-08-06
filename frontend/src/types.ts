export interface Collection {
  id: number;
  name: string;
  document_count: number;
  created_at: string;
}

export interface Doc {
  id: number;
  filename: string;
  chunk_count: number;
  collection_id: number | null;
  created_at: string;
}

export interface ConversationSummary {
  id: number;
  title: string;
  message_count: number;
  created_at: string;
}

export interface ConversationDetail {
  id: number;
  summary: string | null;
  messages: { role: string; content: string }[];
}

export interface Job {
  id: number;
  kind: string;
  status: string;
  detail: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface ChatResult {
  answer: string;
  tools_used: string[];
}

export interface AgentStep {
  query: string;
  findings: string[];
}

export interface AgentResult {
  plan: string[];
  steps: AgentStep[];
  answer: string;
}

export interface Stats {
  documents: number;
  chunks: number;
  collections: number;
  conversations: number;
  prompts: number;
  average_latency_ms: number | null;
  total_prompt_tokens: number;
  total_response_tokens: number;
}

export interface PromptLog {
  id: number;
  question: string;
  response: string;
  model: string;
  latency_ms: number;
  prompt_tokens: number | null;
  response_tokens: number | null;
  created_at: string;
}
