import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  chat,
  deleteConversation,
  getCollections,
  getConversation,
  getConversations,
  renameConversation,
  runAgent,
  streamAsk,
} from "../api";
import type { AgentResult, Collection, ConversationSummary } from "../types";

type Mode = "ask" | "chat" | "agent";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
  trace?: AgentResult;
}

const MODE_HINTS: Record<Mode, string> = {
  ask: "Answers come from your indexed documents, with conversation memory.",
  chat: "The model decides which tools to use: document search, calculator, time.",
  agent: "Plans sub-questions, searches each, then synthesizes an answer.",
};

function PencilIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
    </svg>
  );
}

export default function ChatView() {
  const { id } = useParams();
  const routeId = id ? Number(id) : null;
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>("ask");
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  function refreshConversations() {
    getConversations().then(setConversations).catch(() => {});
  }

  useEffect(() => {
    getCollections().then(setCollections).catch(() => {});
    refreshConversations();
  }, []);

  useEffect(() => {
    if (routeId === null) {
      setConversationId(null);
      setMessages([]);
      setError(null);
    } else if (routeId !== conversationId) {
      openConversation(routeId);
    }
  }, [routeId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function openConversation(target: number) {
    try {
      const conversation = await getConversation(target);
      setMode("ask");
      setConversationId(target);
      setError(null);
      setMessages(
        conversation.messages.map((message) => ({
          role: message.role === "user" ? "user" : "assistant",
          content: message.content,
        })),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  function appendAssistantToken(token: string) {
    setMessages((current) => {
      const updated = [...current];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = { ...last, content: last.content + token };
      return updated;
    });
  }

  async function submit() {
    const trimmed = question.trim();
    if (!trimmed || busy) return;

    setError(null);
    setBusy(true);
    setQuestion("");
    setMessages((current) => [...current, { role: "user", content: trimmed }]);

    try {
      if (mode === "ask") {
        const existingId = conversationId;
        setMessages((current) => [...current, { role: "assistant", content: "" }]);
        await streamAsk(
          trimmed,
          collectionId,
          existingId,
          (created) => {
            setConversationId(created);
            if (existingId === null) {
              setConversations((current) => [
                {
                  id: created,
                  title: trimmed.slice(0, 80),
                  message_count: 0,
                  created_at: new Date().toISOString(),
                },
                ...current,
              ]);
              navigate(`/chats/${created}`, { replace: true });
            }
          },
          appendAssistantToken,
        );
        refreshConversations();
        setTimeout(refreshConversations, 4000);
      } else if (mode === "chat") {
        const result = await chat(trimmed);
        setMessages((current) => [
          ...current,
          { role: "assistant", content: result.answer, tools: result.tools_used },
        ]);
      } else {
        const result = await runAgent(trimmed, collectionId);
        setMessages((current) => [
          ...current,
          { role: "assistant", content: result.answer, trace: result },
        ]);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  async function rename(conversation: ConversationSummary) {
    const title = window.prompt("Rename chat", conversation.title);
    if (title === null || !title.trim()) return;
    try {
      await renameConversation(conversation.id, title.trim());
      refreshConversations();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  async function remove(conversation: ConversationSummary) {
    if (!window.confirm(`Delete "${conversation.title}"?`)) return;
    try {
      await deleteConversation(conversation.id);
      if (conversation.id === conversationId) navigate("/chats");
      refreshConversations();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <div className="chat-layout">
      <aside className="chat-sidebar">
        <div className="chat-sidebar-top">
          <button
            className="primary"
            style={{ width: "100%" }}
            onClick={() => navigate("/chats")}
          >
            New chat
          </button>
        </div>
        <nav className="chat-list">
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={
                conversation.id === conversationId ? "chat-item active" : "chat-item"
              }
            >
              <button
                className="chat-item-main"
                onClick={() => navigate(`/chats/${conversation.id}`)}
              >
                <span className="chat-item-title">{conversation.title}</span>
                <span className="hint">{conversation.message_count} messages</span>
              </button>
              <div className="chat-item-actions">
                <button aria-label="Rename chat" onClick={() => rename(conversation)}>
                  <PencilIcon />
                </button>
                <button aria-label="Delete chat" onClick={() => remove(conversation)}>
                  <TrashIcon />
                </button>
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <section className="chat-main">
        <div className="chat-toolbar">
          <div className="mode-switch">
            {(["ask", "chat", "agent"] as Mode[]).map((name) => (
              <button
                key={name}
                className={mode === name ? "active" : ""}
                onClick={() => setMode(name)}
              >
                {name}
              </button>
            ))}
          </div>
          {mode !== "chat" && (
            <select
              aria-label="Collection filter"
              value={collectionId ?? ""}
              onChange={(event) =>
                setCollectionId(event.target.value ? Number(event.target.value) : null)
              }
            >
              <option value="">All collections</option>
              {collections.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="chat-messages">
          <div className="chat-messages-inner">
            {messages.length === 0 && (
              <div className="chat-empty">
                <h3>Ask your knowledge base</h3>
                <p className="hint">{MODE_HINTS[mode]}</p>
              </div>
            )}
            {messages.map((message, index) => (
              <div key={index} className={`message ${message.role}`}>
                {message.content || (busy && index === messages.length - 1 ? "…" : "")}
                {message.tools && message.tools.length > 0 && (
                  <div className="chips">
                    {message.tools.map((tool, i) => (
                      <span key={i} className="chip">
                        {tool}
                      </span>
                    ))}
                  </div>
                )}
                {message.trace && (
                  <div className="trace">
                    <div>
                      <strong>Plan</strong>
                    </div>
                    {message.trace.plan.map((step, i) => (
                      <div key={i}>• {step}</div>
                    ))}
                    <div style={{ marginTop: 6 }}>
                      <strong>Evidence</strong>
                    </div>
                    {message.trace.steps.map((step, i) => (
                      <div key={i}>
                        {step.query} → {step.findings.length} findings
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottom} />
          </div>
        </div>

        <div className="chat-composer">
          <div className="chat-composer-inner">
            <div className="row">
              <input
                className="grow"
                placeholder={busy ? "Thinking…" : "Ask a question…"}
                value={question}
                disabled={busy}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && submit()}
              />
              <button className="primary" onClick={submit} disabled={busy}>
                Send
              </button>
            </div>
            {error && <p className="error">{error}</p>}
          </div>
        </div>
      </section>
    </div>
  );
}
