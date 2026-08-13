import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import ReactMarkdown from "react-markdown";
import { useNavigate, useParams } from "react-router-dom";
import remarkGfm from "remark-gfm";
import {
  askImage,
  branchConversation,
  continueAssistant,
  deleteConversation,
  getConversation,
  getConversations,
  renameConversation,
  resumeAssistant,
  streamAssistant,
  submitFeedback,
} from "../api";
import type {
  ConversationSummary,
  Feedback,
  Source,
  ToolStep,
  Usage,
  Widget,
} from "../types";
import { WidgetList } from "./ChatWidgets";

interface Attachment {
  name: string;
  url?: string;
}

interface Approval {
  name: string;
  arguments: Record<string, unknown>;
  thread: string;
}

interface BranchOrigin {
  fromId: number | null;
  title: string | null;
  count: number;
}

interface ChatMessage {
  id?: number;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
  attachment?: Attachment;
  steps?: ToolStep[];
  sources?: Source[];
  widgets?: Widget[];
  approval?: Approval;
  usage?: Usage;
  feedback?: Feedback | null;
}

function formatDuration(ms: number): string {
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function isAbortError(caught: unknown): boolean {
  return caught instanceof DOMException && caught.name === "AbortError";
}

function parseStoredContent(content: string): {
  content: string;
  attachment?: Attachment;
} {
  const match = content.match(/^([\s\S]*?)\s*\(image: (.+)\)$/);
  if (!match) return { content };
  return { content: match[1], attachment: { name: match[2] } };
}

const EMPTY_HINT =
  "Your documents are searched first, then the model works with tools — more searches, web, calculator — and shows each step.";

const PENDING_LABEL = "Working";

const STEP_LABELS: Record<string, { running: string; done: string }> = {
  search_documents: { running: "Searching documents", done: "Searched documents" },
  web_search: { running: "Searching the web", done: "Searched the web" },
  calculator: { running: "Calculating", done: "Calculated" },
  current_time: { running: "Checking the time", done: "Checked the time" },
  world_clock: { running: "Checking the time", done: "Checked the time" },
  get_weather: { running: "Checking the weather", done: "Checked the weather" },
  crypto_price: { running: "Fetching market prices", done: "Fetched market prices" },
  kb_stats: { running: "Checking your library", done: "Checked your library" },
  usage_stats: { running: "Checking usage", done: "Checked usage" },
  generate_image: { running: "Generating an image", done: "Generated an image" },
  web_image_search: {
    running: "Searching web images",
    done: "Searched web images",
  },
};

function stepLabel(step: ToolStep): string {
  const labels = STEP_LABELS[step.name] ?? {
    running: `Running ${step.name}`,
    done: `Ran ${step.name}`,
  };
  return step.result === null ? labels.running : labels.done;
}

function stepDetail(step: ToolStep): string {
  const detail =
    step.arguments.query ??
    step.arguments.expression ??
    step.arguments.city ??
    step.arguments.coin ??
    step.arguments.timezone ??
    "";
  return String(detail);
}

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

function PaperclipIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
    </svg>
  );
}

function CalculatorIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="16" height="20" x="4" y="2" rx="2" />
      <path d="M8 6h8M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function ArrowDownIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </svg>
  );
}

function ArrowUpIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m5 12 7-7 7 7" />
      <path d="M12 19V5" />
    </svg>
  );
}

function WrenchIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

function CloudIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 3v16a2 2 0 0 0 2 2h16" />
      <path d="m19 9-5 5-4-4-3 3" />
    </svg>
  );
}

function DatabaseIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14a9 3 0 0 0 18 0V5" />
      <path d="M3 12a9 3 0 0 0 18 0" />
    </svg>
  );
}

function ImageIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
      <circle cx="9" cy="9" r="2" />
      <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
    </svg>
  );
}

const STEP_ICONS: Record<string, ComponentType> = {
  search_documents: SearchIcon,
  web_search: GlobeIcon,
  calculator: CalculatorIcon,
  current_time: ClockIcon,
  world_clock: ClockIcon,
  get_weather: CloudIcon,
  crypto_price: ChartIcon,
  kb_stats: DatabaseIcon,
  usage_stats: ChartIcon,
  generate_image: ImageIcon,
  web_image_search: ImageIcon,
};

function DownloadIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  );
}

function downloadSvg(svg: string) {
  const blob = new Blob([svg], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "diagram.svg";
  link.click();
  URL.revokeObjectURL(url);
}

let mermaidSequence = 0;

function MermaidBlock({ code }: { code: string }) {
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSvg(null);
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "strict",
        });
        const { svg: rendered } = await mermaid.render(
          `mermaid-${++mermaidSequence}`,
          code,
        );
        if (!cancelled) setSvg(rendered);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (svg === null) return <code>{code}</code>;
  return (
    <div className="mermaid-figure">
      <div className="mermaid-diagram" dangerouslySetInnerHTML={{ __html: svg }} />
      <button
        className="ghost mermaid-download"
        onClick={() => downloadSvg(svg)}
        aria-label="Download diagram as SVG"
      >
        <DownloadIcon />
        Download SVG
      </button>
    </div>
  );
}

function CodeBlock({
  className,
  children,
}: {
  className?: string;
  children?: ReactNode;
}) {
  const language = /language-(\w+)/.exec(className ?? "")?.[1];
  if (language === "mermaid") {
    return <MermaidBlock code={String(children).trim()} />;
  }
  return <code className={className}>{children}</code>;
}

function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: (props) => (
            <a {...props} target="_blank" rel="noopener noreferrer" />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

function AnswerBody({
  content,
  sources,
}: {
  content: string;
  sources?: Source[];
}) {
  const [activeSource, setActiveSource] = useState<number | null>(null);
  const sourceMap = new Map((sources ?? []).map((source) => [source.id, source]));
  const linked = content.replace(/\[(\d+)\](?!\()/g, (match, id) =>
    sourceMap.has(Number(id)) ? `[${id}](#source-${id})` : match,
  );
  const active = activeSource === null ? null : sourceMap.get(activeSource);

  return (
    <>
      <div className="markdown">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code: CodeBlock,
            a: ({ href, children, ...props }) => {
              if (href?.startsWith("#source-")) {
                const id = Number(href.slice("#source-".length));
                return (
                  <button
                    className={activeSource === id ? "citation active" : "citation"}
                    onClick={() =>
                      setActiveSource(activeSource === id ? null : id)
                    }
                  >
                    {id}
                  </button>
                );
              }
              return (
                <a {...props} href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              );
            },
          }}
        >
          {linked}
        </ReactMarkdown>
      </div>
      {active && (
        <div className="source-card">
          <div className="source-title">
            {active.url ? <GlobeIcon /> : <FileIcon />}
            {active.url ? (
              <a href={active.url} target="_blank" rel="noopener noreferrer">
                {active.filename}
              </a>
            ) : (
              active.filename
            )}
          </div>
          <div className="source-content">{active.content}</div>
        </div>
      )}
    </>
  );
}

function BranchIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="6" x2="6" y1="3" y2="15" />
      <circle cx="18" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M18 9a9 9 0 0 1-9 9" />
    </svg>
  );
}

function ThumbUpIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M7 10v12" />
      <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
    </svg>
  );
}

function ThumbDownIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17 14V2" />
      <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
    </svg>
  );
}

function FeedbackControl({
  messageId,
  feedback,
  onChange,
}: {
  messageId: number;
  feedback: Feedback | null;
  onChange: (value: Feedback | null) => void;
}) {
  async function vote(value: Feedback) {
    const next = feedback === value ? null : value;
    const previous = feedback;
    onChange(next);
    try {
      await submitFeedback(messageId, next);
    } catch {
      onChange(previous);
    }
  }

  function thumbClass(value: Feedback): string {
    return feedback === value
      ? `meta-button ${value} selected`
      : `meta-button ${value}`;
  }

  return (
    <span className="feedback" role="group" aria-label="Rate this answer">
      <button
        className={thumbClass("like")}
        aria-label="Like"
        aria-pressed={feedback === "like"}
        data-tip={feedback === "like" ? "Remove like" : "Like"}
        onClick={() => vote("like")}
      >
        <ThumbUpIcon />
      </button>
      <button
        className={thumbClass("dislike")}
        aria-label="Dislike"
        aria-pressed={feedback === "dislike"}
        data-tip={feedback === "dislike" ? "Remove dislike" : "Dislike"}
        onClick={() => vote("dislike")}
      >
        <ThumbDownIcon />
      </button>
    </span>
  );
}

function UsageMeta({ usage, actions }: { usage?: Usage; actions?: ReactNode }) {
  return (
    <div className="message-meta">
      {usage && (
        <>
          {usage.elapsed_ms !== null && (
            <span className="meta-item" title="Response time">
              <ClockIcon />
              <span className="meta-value">{formatDuration(usage.elapsed_ms)}</span>
            </span>
          )}
          <span className="meta-item" title="Prompt tokens">
            <ArrowDownIcon />
            <span className="meta-value">
              {usage.prompt_tokens.toLocaleString()}
            </span>
            <span className="meta-label">prompt</span>
          </span>
          <span className="meta-item" title="Response tokens">
            <ArrowUpIcon />
            <span className="meta-value">
              {usage.response_tokens.toLocaleString()}
            </span>
            <span className="meta-label">response</span>
          </span>
        </>
      )}
      {actions}
    </div>
  );
}

function StepRow({ step }: { step: ToolStep }) {
  const Icon = STEP_ICONS[step.name] ?? WrenchIcon;
  const detail = stepDetail(step);
  const running = step.result === null;

  return (
    <details className="step">
      <summary>
        <Icon />
        <span>{stepLabel(step)}</span>
        {detail && <span className="step-detail">{detail}</span>}
        {running && <span className="dots" aria-hidden="true" />}
      </summary>
      {step.result && (
        <div className="step-result">
          <Markdown>{step.result}</Markdown>
        </div>
      )}
    </details>
  );
}

function AttachmentCard({ attachment }: { attachment: Attachment }) {
  if (attachment.url) {
    return (
      <figure className="message-attachment">
        <img src={attachment.url} alt={attachment.name} />
        <figcaption>{attachment.name}</figcaption>
      </figure>
    );
  }
  return (
    <span className="message-attachment file">
      <FileIcon />
      {attachment.name}
    </span>
  );
}

export default function ChatView() {
  const { id } = useParams();
  const routeId = id ? Number(id) : null;
  const navigate = useNavigate();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [branch, setBranch] = useState<BranchOrigin | null>(null);
  const [question, setQuestion] = useState("");
  const [attachedImage, setAttachedImage] = useState<File | null>(null);
  const [attachedPreview, setAttachedPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const awaitingApproval = useRef(false);
  const streamAbort = useRef<AbortController | null>(null);

  function abortActiveStream() {
    streamAbort.current?.abort();
    streamAbort.current = null;
    awaitingApproval.current = false;
    setBusy(false);
  }

  function startStream(): AbortSignal {
    const controller = new AbortController();
    streamAbort.current = controller;
    return controller.signal;
  }

  function refreshConversations() {
    getConversations().then(setConversations).catch(() => {});
  }

  useEffect(() => {
    refreshConversations();
  }, []);

  useEffect(() => {
    if (routeId === null) {
      abortActiveStream();
      setConversationId(null);
      setMessages([]);
      setBranch(null);
      setError(null);
    } else if (routeId !== conversationId) {
      abortActiveStream();
      openConversation(routeId);
    }
  }, [routeId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function openConversation(target: number) {
    try {
      const conversation = await getConversation(target);
      setConversationId(target);
      setError(null);
      setBranch(
        conversation.branched_count !== null
          ? {
              fromId: conversation.branched_from_id,
              title: conversation.branched_from_title,
              count: conversation.branched_count,
            }
          : null,
      );
      setMessages(
        conversation.messages.map((message) => {
          const parsed =
            message.role === "user"
              ? parseStoredContent(message.content)
              : { content: message.content };
          return {
            id: message.id,
            role: message.role === "user" ? ("user" as const) : ("assistant" as const),
            content: parsed.content,
            attachment: parsed.attachment,
            steps: message.steps ?? undefined,
            sources: message.sources ?? undefined,
            widgets: message.widgets ?? undefined,
            feedback: message.feedback,
            usage:
              message.prompt_tokens !== null && message.response_tokens !== null
                ? {
                    elapsed_ms: message.elapsed_ms,
                    prompt_tokens: message.prompt_tokens,
                    response_tokens: message.response_tokens,
                  }
                : undefined,
          };
        }),
      );
      if (conversation.active_thread) {
        continueRun(target);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  async function continueRun(target: number) {
    setBusy(true);
    const signal = startStream();
    try {
      await continueAssistant(
        target,
        {
          ...assistantHandlers(""),
          onConversation: () => {},
          onSnapshot: (question, steps, sources, widgets) => {
            awaitingApproval.current = false;
            setMessages((current) => [
              ...current,
              { role: "user", content: question },
              {
                role: "assistant",
                content: PENDING_LABEL,
                pending: true,
                steps,
                sources,
                widgets,
              },
            ]);
          },
        },
        signal,
      );
      refreshConversations();
    } catch (caught) {
      if (isAbortError(caught)) return;
      setMessages((current) =>
        current[current.length - 1]?.pending ? current.slice(0, -1) : current,
      );
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      if (!signal.aborted && !awaitingApproval.current) setBusy(false);
    }
  }

  function appendAssistantToken(token: string) {
    setMessages((current) => {
      const updated = [...current];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = {
        ...last,
        content: last.pending ? token : last.content + token,
        pending: false,
      };
      return updated;
    });
  }

  function replaceLastMessage(message: ChatMessage) {
    setMessages((current) => [...current.slice(0, -1), message]);
  }

  function updateLastMessage(update: (last: ChatMessage) => ChatMessage) {
    setMessages((current) => [
      ...current.slice(0, -1),
      update(current[current.length - 1]),
    ]);
  }

  function addStep(name: string, args: Record<string, unknown>) {
    updateLastMessage((last) => ({
      ...last,
      steps: [...(last.steps ?? []), { name, arguments: args, result: null }],
      content: PENDING_LABEL,
      pending: true,
    }));
  }

  function resolveStep(name: string, content: string) {
    updateLastMessage((last) => {
      const steps = [...(last.steps ?? [])];
      for (let index = steps.length - 1; index >= 0; index--) {
        if (steps[index].name === name && steps[index].result === null) {
          steps[index] = { ...steps[index], result: content };
          break;
        }
      }
      return { ...last, steps };
    });
  }

  function requestApproval(name: string, args: Record<string, unknown>, thread: string) {
    awaitingApproval.current = true;
    updateLastMessage((last) => ({
      ...last,
      approval: { name, arguments: args, thread },
    }));
  }

  function addSources(sources: Source[]) {
    updateLastMessage((last) => ({
      ...last,
      sources: [...(last.sources ?? []), ...sources],
    }));
  }

  function addWidget(widget: Widget) {
    updateLastMessage((last) => ({
      ...last,
      widgets: [...(last.widgets ?? []), widget],
    }));
  }

  function applyUsage(usage: Usage) {
    updateLastMessage((last) => ({ ...last, usage }));
  }

  function applySavedId(messageId: number) {
    updateLastMessage((last) => ({ ...last, id: messageId }));
  }

  function setMessageFeedback(index: number, feedback: Feedback | null) {
    setMessages((current) =>
      current.map((message, position) =>
        position === index ? { ...message, feedback } : message,
      ),
    );
  }

  async function branchAt(messageId: number) {
    try {
      const created = await branchConversation(messageId);
      refreshConversations();
      navigate(`/chats/${created.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  const assistantHandlers = (firstQuestion: string) => ({
    onConversation: (created: number) => adoptConversation(created, firstQuestion),
    onToken: appendAssistantToken,
    onTitle: applyTitle,
    onToolCall: addStep,
    onToolResult: resolveStep,
    onSources: addSources,
    onWidget: addWidget,
    onUsage: applyUsage,
    onSaved: applySavedId,
    onApproval: requestApproval,
  });

  async function decideApproval(approval: Approval, approved: boolean) {
    if (conversationId === null) return;
    awaitingApproval.current = false;
    updateLastMessage((last) => ({
      ...last,
      approval: undefined,
      content: PENDING_LABEL,
      pending: true,
    }));
    const signal = startStream();
    try {
      await resumeAssistant(
        approval.thread,
        conversationId,
        approved,
        assistantHandlers(""),
        signal,
      );
      refreshConversations();
    } catch (caught) {
      if (isAbortError(caught)) return;
      setMessages((current) =>
        current[current.length - 1]?.pending ? current.slice(0, -1) : current,
      );
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      if (!signal.aborted && !awaitingApproval.current) setBusy(false);
    }
  }

  function adoptConversation(created: number, firstQuestion: string) {
    setConversationId(created);
    if (conversationId === null) {
      setConversations((current) => [
        {
          id: created,
          title: firstQuestion.slice(0, 20),
          message_count: 0,
          created_at: new Date().toISOString(),
        },
        ...current,
      ]);
      navigate(`/chats/${created}`, { replace: true });
    }
    refreshConversations();
    setTimeout(refreshConversations, 4000);
  }

  function applyTitle(target: number, title: string) {
    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === target ? { ...conversation, title } : conversation,
      ),
    );
  }

  function clearAttachment() {
    setAttachedImage(null);
    setAttachedPreview(null);
    if (imageInput.current) imageInput.current.value = "";
  }

  function attachImage(file: File | null) {
    if (attachedPreview) URL.revokeObjectURL(attachedPreview);
    setAttachedImage(file);
    setAttachedPreview(file ? URL.createObjectURL(file) : null);
  }

  async function submit() {
    const trimmed = question.trim();
    if (!trimmed || busy) return;

    const image = attachedImage;
    const preview = attachedPreview;
    const existingId = conversationId;

    setError(null);
    setBusy(true);
    setQuestion("");
    setAttachedImage(null);
    setAttachedPreview(null);
    if (imageInput.current) imageInput.current.value = "";
    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: trimmed,
        attachment: image
          ? { name: image.name, url: preview ?? undefined }
          : undefined,
      },
      {
        role: "assistant",
        content: image ? "Reading the image" : PENDING_LABEL,
        pending: true,
      },
    ]);

    const signal = startStream();
    try {
      if (image) {
        const result = await askImage(image, trimmed, existingId, signal);
        replaceLastMessage({ role: "assistant", content: result.answer });
        adoptConversation(result.conversation_id, trimmed);
      } else {
        await streamAssistant(
          trimmed,
          existingId,
          assistantHandlers(trimmed),
          signal,
        );
        refreshConversations();
      }
    } catch (caught) {
      if (isAbortError(caught)) return;
      setMessages((current) =>
        current[current.length - 1]?.pending ? current.slice(0, -1) : current,
      );
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      if (!signal.aborted && !awaitingApproval.current) setBusy(false);
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
        <div className="chat-messages">
          <div className="chat-messages-inner">
            {messages.length === 0 && (
              <div className="chat-empty">
                <h3>Ask your knowledge base</h3>
                <p className="hint">{EMPTY_HINT}</p>
              </div>
            )}
            {messages.map((message, index) => (
              <Fragment key={index}>
              <div className={`message-group ${message.role}`}>
                {message.attachment && (
                  <AttachmentCard attachment={message.attachment} />
                )}
                <div className={`message ${message.role}`}>
                {message.steps && message.steps.length > 0 && (
                  <div className="steps">
                    {message.steps.map((step, i) => (
                      <StepRow key={i} step={step} />
                    ))}
                  </div>
                )}
                {message.approval ? (
                  <div className="approval">
                    <div className="approval-text">
                      <GlobeIcon />
                      <span>
                        {message.approval.name === "web_image_search"
                          ? "Cortex wants to search the web for images of "
                          : "Cortex wants to search the web for "}
                        <strong>
                          {String(message.approval.arguments.query ?? "")}
                        </strong>
                      </span>
                    </div>
                    <div className="approval-actions">
                      <button
                        className="primary"
                        onClick={() => decideApproval(message.approval!, true)}
                      >
                        Allow
                      </button>
                      <button
                        className="ghost"
                        onClick={() => decideApproval(message.approval!, false)}
                      >
                        Deny
                      </button>
                    </div>
                  </div>
                ) : message.pending ? (
                  <span className="thinking">
                    {message.content}
                    <span className="dots" aria-hidden="true" />
                  </span>
                ) : message.role === "assistant" ? (
                  <>
                    {message.widgets && <WidgetList widgets={message.widgets} />}
                    <AnswerBody content={message.content} sources={message.sources} />
                  </>
                ) : (
                  message.content
                )}
                {message.role === "assistant" &&
                  !message.pending &&
                  !message.approval &&
                  (message.usage || message.id !== undefined) && (
                    <UsageMeta
                      usage={message.usage}
                      actions={
                        message.id !== undefined ? (
                          <span className="meta-actions">
                            <button
                              className="meta-button"
                              aria-label="Create new branch"
                              data-tip="Create new branch"
                              onClick={() => branchAt(message.id!)}
                            >
                              <BranchIcon />
                            </button>
                            <FeedbackControl
                              messageId={message.id}
                              feedback={message.feedback ?? null}
                              onChange={(value) => setMessageFeedback(index, value)}
                            />
                          </span>
                        ) : undefined
                      }
                    />
                  )}
                </div>
              </div>
              {branch && index === branch.count - 1 && (
                <div className="branch-divider">
                  <span>
                    Branched from{" "}
                    {branch.fromId !== null ? (
                      <button
                        className="branch-link"
                        onClick={() => navigate(`/chats/${branch.fromId}`)}
                      >
                        {branch.title}
                      </button>
                    ) : (
                      "a deleted chat"
                    )}
                  </span>
                </div>
              )}
              </Fragment>
            ))}
            <div ref={bottom} />
          </div>
        </div>

        <div className="chat-composer">
          <div className="chat-composer-inner">
            {attachedImage && attachedPreview && (
              <div className="attachment-preview">
                <img src={attachedPreview} alt={attachedImage.name} />
                <div className="attachment-meta">
                  <span className="attachment-name">{attachedImage.name}</span>
                  <button
                    className="danger"
                    aria-label="Remove image"
                    onClick={clearAttachment}
                  >
                    remove
                  </button>
                </div>
              </div>
            )}
            <div className="row">
              <input
                ref={imageInput}
                type="file"
                accept=".png,.jpg,.jpeg"
                style={{ display: "none" }}
                onChange={(event) => attachImage(event.target.files?.[0] ?? null)}
              />
              <button
                className="ghost icon"
                aria-label="Attach an image"
                disabled={busy}
                onClick={() => imageInput.current?.click()}
              >
                <PaperclipIcon />
              </button>
              <input
                className="grow"
                placeholder={
                  attachedImage ? "Ask about the image…" : "Ask a question…"
                }
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
