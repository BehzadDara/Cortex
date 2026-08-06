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

export interface BatchIngest {
  ingested: Doc[];
  skipped: number;
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
