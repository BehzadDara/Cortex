import type {
  Collection,
  ConversationDetail,
  ConversationSummary,
  Doc,
  ImageAnswer,
  Job,
  PromptLog,
  Source,
  Stats,
} from "./types";

const BASE = "/api";

async function toError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  return new Error(body?.detail ?? `Request failed with ${response.status}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) throw await toError(response);
  return response.json();
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export const getCollections = () => request<Collection[]>("/collections");

export const createCollection = (name: string) =>
  request<Collection>("/collections", jsonInit("POST", { name }));

export async function deleteCollection(id: number): Promise<void> {
  const response = await fetch(`${BASE}/collections/${id}`, { method: "DELETE" });
  if (!response.ok) throw await toError(response);
}

export const getConversations = () =>
  request<ConversationSummary[]>("/conversations");

export const getConversation = (id: number) =>
  request<ConversationDetail>(`/conversations/${id}`);

export const renameConversation = (id: number, title: string) =>
  request<ConversationSummary>(`/conversations/${id}`, jsonInit("PATCH", { title }));

export async function deleteConversation(id: number): Promise<void> {
  const response = await fetch(`${BASE}/conversations/${id}`, { method: "DELETE" });
  if (!response.ok) throw await toError(response);
}

export const getDocuments = () => request<Doc[]>("/documents");

export async function uploadDocument(
  file: File,
  collectionId: number | null,
): Promise<Doc> {
  const form = new FormData();
  form.append("file", file);
  if (collectionId !== null) form.append("collection_id", String(collectionId));
  const response = await fetch(`${BASE}/documents`, { method: "POST", body: form });
  if (!response.ok) throw await toError(response);
  return response.json();
}

export const indexWebsite = (url: string, collectionId: number | null) =>
  request<Job>(
    "/documents/url",
    jsonInit("POST", { url, collection_id: collectionId }),
  );

export const indexRepository = (url: string, collectionId: number | null) =>
  request<Job>(
    "/documents/repository",
    jsonInit("POST", { url, collection_id: collectionId }),
  );

export const getJob = (id: number) => request<Job>(`/jobs/${id}`);

export async function waitForJob(id: number): Promise<Job> {
  while (true) {
    const job = await getJob(id);
    if (job.status === "done" || job.status === "failed") return job;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}

export async function deleteDocument(id: number): Promise<void> {
  const response = await fetch(`${BASE}/documents/${id}`, { method: "DELETE" });
  if (!response.ok) throw await toError(response);
}

export async function askImage(
  file: File,
  question: string,
  conversationId: number | null,
): Promise<ImageAnswer> {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question);
  if (conversationId !== null) form.append("conversation_id", String(conversationId));
  const response = await fetch(`${BASE}/ask-image`, { method: "POST", body: form });
  if (!response.ok) throw await toError(response);
  return response.json();
}

export const getStats = () => request<Stats>("/stats");

export const getLogs = (limit = 20) => request<PromptLog[]>(`/logs?limit=${limit}`);

export interface StreamHandlers {
  onConversation: (id: number) => void;
  onToken: (token: string) => void;
  onTitle: (id: number, title: string) => void;
  onToolCall?: (name: string, args: Record<string, unknown>) => void;
  onToolResult?: (name: string, content: string) => void;
  onSources?: (sources: Source[]) => void;
  onApproval?: (
    name: string,
    args: Record<string, unknown>,
    thread: string,
  ) => void;
}

async function streamEvents(
  path: string,
  body: unknown,
  handlers: StreamHandlers,
): Promise<void> {
  const response = await fetch(`${BASE}${path}`, jsonInit("POST", body));
  if (!response.ok || !response.body) throw await toError(response);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const raw of events) {
      if (!raw.startsWith("data: ")) continue;
      const event = JSON.parse(raw.slice(6));
      if (event.type === "conversation") handlers.onConversation(event.id);
      else if (event.type === "token") handlers.onToken(event.content);
      else if (event.type === "title") handlers.onTitle(event.id, event.title);
      else if (event.type === "tool_call")
        handlers.onToolCall?.(event.name, event.arguments);
      else if (event.type === "tool_result")
        handlers.onToolResult?.(event.name, event.content);
      else if (event.type === "sources") handlers.onSources?.(event.sources);
      else if (event.type === "approval")
        handlers.onApproval?.(event.name, event.arguments, event.thread);
      else if (event.type === "done") return;
    }
  }
}

export const streamAssistant = (
  question: string,
  conversationId: number | null,
  handlers: StreamHandlers,
) =>
  streamEvents(
    "/assistant",
    { question, conversation_id: conversationId },
    handlers,
  );

export const resumeAssistant = (
  thread: string,
  conversationId: number,
  approved: boolean,
  handlers: StreamHandlers,
) =>
  streamEvents(
    "/assistant/resume",
    { thread, conversation_id: conversationId, approved },
    handlers,
  );
