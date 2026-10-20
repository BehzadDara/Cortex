import { useEffect, useRef, useSyncExternalStore } from "react";
import type {
  TurnLatency,
  VoiceConversation,
  VoicePhase,
  VoiceSnapshot,
} from "../voice/conversation";

const TITLES: Record<VoicePhase, string> = {
  starting: "Getting ready",
  listening: "Listening",
  hearing: "Hearing you",
  transcribing: "Transcribing",
  thinking: "Thinking",
  speaking: "Speaking",
  confirming: "Waiting for your answer",
  failed: "Voice mode stopped",
};

const ORB_LEVEL_GAIN = 2.6;
const ORB_MAX_GROWTH = 0.55;
const ORB_EASING = 0.22;

function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

function quoted(text: string): string {
  return `“${text}”`;
}

function titleFor(snapshot: VoiceSnapshot, activity: string | null): string {
  if (snapshot.muted && snapshot.phase === "listening") return "Microphone off";
  if (snapshot.phase === "thinking" && activity) return activity;
  return TITLES[snapshot.phase];
}

function detailFor(snapshot: VoiceSnapshot): string {
  const heard = snapshot.heard ? quoted(snapshot.heard) : null;
  switch (snapshot.phase) {
    case "failed":
      return snapshot.failure ?? "Something went wrong.";
    case "starting":
      return "Loading the speech models. The first start takes a few seconds.";
    case "hearing":
      return "Pause when you're done.";
    case "transcribing":
      return "Turning your words into text.";
    case "thinking":
      return heard ?? "Working on it.";
    case "speaking":
      return "Start talking to interrupt.";
    case "confirming":
      return "Say yes or no, or use Allow and Deny above.";
    case "listening":
      if (snapshot.muted) return "Unmute to keep talking.";
      return snapshot.notice ?? heard ?? "Go ahead. Pause when you're done.";
  }
}

export function VoiceDock({
  engine,
  activity,
  onEnd,
  onRetry,
}: {
  engine: VoiceConversation;
  activity: string | null;
  onEnd: () => void;
  onRetry: () => void;
}) {
  const snapshot = useSyncExternalStore(engine.subscribe, engine.getSnapshot);
  const { phase, muted, latency } = snapshot;
  const failed = phase === "failed";
  const dock = useRef<HTMLElement>(null);

  useEffect(() => {
    dock.current?.focus();
  }, []);

  return (
    <section
      ref={dock}
      className="voice-dock"
      aria-label="Voice conversation"
      tabIndex={-1}
    >
      <VoiceOrb engine={engine} phase={phase} muted={muted} />
      <div className="voice-status">
        <p className="voice-title" role="status" aria-live="polite">
          {titleFor(snapshot, activity)}
        </p>
        <p className={failed ? "voice-detail failed" : "voice-detail"}>
          {detailFor(snapshot)}
        </p>
        {latency && !failed && <LatencyReadout latency={latency} />}
      </div>
      <div className="voice-controls">
        {failed ? (
          <button className="primary voice-retry" onClick={onRetry}>
            Try again
          </button>
        ) : (
          <>
            <button
              className={muted ? "voice-control muted" : "voice-control"}
              aria-label={muted ? "Unmute microphone" : "Mute microphone"}
              aria-pressed={muted}
              data-tip={muted ? "Unmute" : "Mute"}
              disabled={phase === "starting"}
              onClick={() => engine.setMuted(!muted)}
            >
              {muted ? <MicOffIcon /> : <MicIcon />}
            </button>
            <button
              className="voice-control"
              aria-label="Stop speaking"
              data-tip="Stop speaking"
              disabled={phase !== "speaking"}
              onClick={() => engine.silence()}
            >
              <SquareIcon />
            </button>
          </>
        )}
        <button className="voice-end" onClick={onEnd}>
          <CloseIcon />
          End
        </button>
      </div>
    </section>
  );
}

function VoiceOrb({
  engine,
  phase,
  muted,
}: {
  engine: VoiceConversation;
  phase: VoicePhase;
  muted: boolean;
}) {
  const halo = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let growth = 0;
    const animate = () => {
      const target = Math.min(1, Math.sqrt(engine.level()) * ORB_LEVEL_GAIN);
      growth += (target - growth) * ORB_EASING;
      halo.current?.style.setProperty("--growth", String(1 + growth * ORB_MAX_GROWTH));
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [engine]);

  return (
    <div className="voice-orb" data-phase={phase} data-muted={muted} aria-hidden="true">
      <span ref={halo} className="voice-orb-halo" />
      <span className="voice-orb-core">
        <PhaseIcon phase={phase} muted={muted} />
      </span>
    </div>
  );
}

function PhaseIcon({ phase, muted }: { phase: VoicePhase; muted: boolean }) {
  if (phase === "failed") return <AlertIcon />;
  if (phase === "speaking") return <WaveIcon />;
  if (phase === "thinking" || phase === "transcribing" || phase === "starting") {
    return <EllipsisIcon />;
  }
  return muted ? <MicOffIcon /> : <MicIcon />;
}

function LatencyReadout({ latency }: { latency: TurnLatency }) {
  const parts = [
    ["pause", latency.endpointMs],
    ["transcribe", latency.transcribeMs],
    ["think", latency.thinkMs],
    ["voice", latency.voiceMs],
  ] as const;
  return (
    <p
      className="voice-latency"
      title="Time from the moment you stopped talking to Cortex's first spoken word"
    >
      <span className="voice-latency-total">{seconds(latency.totalMs)}</span>
      <span>to first word</span>
      <span className="voice-latency-parts">
        ({parts.map(([label, ms]) => `${label} ${seconds(ms)}`).join(" · ")})
      </span>
    </p>
  );
}

function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}

function MicOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="2" x2="22" y1="2" y2="22" />
      <path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" />
      <path d="M5 10v2a7 7 0 0 0 12 5" />
      <path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}

function SquareIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="1.5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

function WaveIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 10v3" />
      <path d="M6 6v11" />
      <path d="M10 3v18" />
      <path d="M14 8v7" />
      <path d="M18 5v13" />
      <path d="M22 10v3" />
    </svg>
  );
}

function EllipsisIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="5" cy="12" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <circle cx="19" cy="12" r="1.8" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" x2="12" y1="8" y2="12" />
      <line x1="12" x2="12.01" y1="16" y2="16" />
    </svg>
  );
}
