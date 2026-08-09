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

export interface ToolStep {
  name: string;
  arguments: Record<string, unknown>;
  result: string | null;
}

export interface Source {
  id: number;
  filename: string;
  content: string;
  url: string | null;
}

export interface Usage {
  elapsed_ms: number | null;
  prompt_tokens: number;
  response_tokens: number;
}

export interface ConversationDetail {
  id: number;
  summary: string | null;
  active_thread: string | null;
  messages: {
    role: string;
    content: string;
    steps: ToolStep[] | null;
    sources: Source[] | null;
    elapsed_ms: number | null;
    prompt_tokens: number | null;
    response_tokens: number | null;
  }[];
}

export interface Job {
  id: number;
  kind: string;
  status: string;
  detail: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface ImageAnswer {
  conversation_id: number;
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
