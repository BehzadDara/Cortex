import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { overviewAudioUrl } from "../api";
import type { AudioOverview, OverviewLine, Source } from "../types";
import { DocumentViewer } from "./DocumentViewer";

const SKIP_SECONDS = 15;
const SPEEDS = [1, 1.25, 1.5, 0.75];
const FOLLOW_OFFSET_RATIO = 0.3;

export function formatClock(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function PlayIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14Z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <rect x="6" y="4.5" width="4" height="15" rx="1.2" />
      <rect x="14" y="4.5" width="4" height="15" rx="1.2" />
    </svg>
  );
}

function SkipIcon({ forward }: { forward: boolean }) {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {forward ? (
        <>
          <path d="M21 12a9 9 0 1 1-3-6.7" />
          <polyline points="21 3 21 8.5 15.5 8.5" />
        </>
      ) : (
        <>
          <path d="M3 12a9 9 0 1 0 3-6.7" />
          <polyline points="3 3 3 8.5 8.5 8.5" />
        </>
      )}
      <text x="12" y="15.2" textAnchor="middle" fontSize="8" fontWeight="700" fill="currentColor" stroke="none">
        {SKIP_SECONDS}
      </text>
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function ArrowDownIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </svg>
  );
}

export function WaveIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M3 10v4" />
      <path d="M7 6v12" />
      <path d="M11 3v18" />
      <path d="M15 7v10" />
      <path d="M19 10v4" />
    </svg>
  );
}

function hostClass(hosts: string[], speaker: string): string {
  return hosts.indexOf(speaker) === 1 ? "host-b" : "host-a";
}

function activeLineIndex(lines: OverviewLine[], positionMs: number): number {
  let low = 0;
  let high = lines.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (lines[middle].start_ms <= positionMs) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found;
}

function downloadName(title: string): string {
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${slug || "audio-overview"}.mp3`;
}

function usePlayback(audio: React.RefObject<HTMLAudioElement | null>) {
  const [playing, setPlaying] = useState(false);
  const [positionMs, setPositionMs] = useState(0);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      const element = audio.current;
      if (element) setPositionMs(Math.round(element.currentTime * 10) * 100);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, audio]);

  const seek = useCallback(
    (milliseconds: number) => {
      const element = audio.current;
      if (!element) return;
      const duration = Number.isFinite(element.duration) ? element.duration * 1000 : milliseconds;
      const clamped = Math.min(Math.max(milliseconds, 0), duration);
      element.currentTime = clamped / 1000;
      setPositionMs(clamped);
    },
    [audio],
  );

  const toggle = useCallback(() => {
    const element = audio.current;
    if (!element) return;
    if (element.paused) element.play().catch(() => setPlaying(false));
    else element.pause();
  }, [audio]);

  const play = useCallback(() => {
    audio.current?.play().catch(() => setPlaying(false));
  }, [audio]);

  const cycleSpeed = useCallback(() => {
    setSpeed((current) => {
      const next = SPEEDS[(SPEEDS.indexOf(current) + 1) % SPEEDS.length];
      if (audio.current) audio.current.playbackRate = next;
      return next;
    });
  }, [audio]);

  const events = {
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onEnded: () => setPlaying(false),
    onSeeked: () => audio.current && setPositionMs(audio.current.currentTime * 1000),
    onTimeUpdate: () => !playing && audio.current && setPositionMs(audio.current.currentTime * 1000),
  };

  return { playing, positionMs, speed, seek, toggle, play, cycleSpeed, events };
}

function useSpaceToToggle(toggle: () => void) {
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if (event.code !== "Space") return;
      const target = event.target as HTMLElement;
      if (target.closest("input, textarea, select, button, a, [contenteditable]")) return;
      event.preventDefault();
      toggle();
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [toggle]);
}

function useMediaSession(overview: AudioOverview) {
  useEffect(() => {
    if (!("mediaSession" in navigator) || typeof MediaMetadata === "undefined") return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: overview.title ?? "Audio overview",
      artist: overview.hosts.join(" & "),
      album: overview.collection_name ?? "Cortex",
    });
  }, [overview]);
}

function Scrubber({
  overview,
  positionMs,
  onSeek,
}: {
  overview: AudioOverview;
  positionMs: number;
  onSeek: (milliseconds: number) => void;
}) {
  const duration = overview.duration_ms ?? 1;
  const percent = Math.min((positionMs / duration) * 100, 100);
  return (
    <div className="scrubber">
      <div className="scrubber-track" aria-hidden="true">
        <div className="scrubber-fill" style={{ width: `${percent}%` }} />
        {overview.segments.slice(1).map((segment) => (
          <span
            key={segment.start_ms}
            className="scrubber-tick"
            style={{ left: `${(segment.start_ms / duration) * 100}%` }}
          />
        ))}
      </div>
      <input
        type="range"
        min={0}
        max={duration}
        step={1000}
        value={Math.min(positionMs, duration)}
        onChange={(event) => onSeek(Number(event.target.value))}
        aria-label="Seek"
        aria-valuetext={`${formatClock(positionMs)} of ${formatClock(duration)}`}
      />
    </div>
  );
}

function Chapters({
  overview,
  activeSegment,
  onSeek,
}: {
  overview: AudioOverview;
  activeSegment: number;
  onSeek: (milliseconds: number) => void;
}) {
  return (
    <ol className="chapters" aria-label="Chapters">
      {overview.segments.map((segment, index) => (
        <li key={segment.start_ms}>
          <button
            type="button"
            className={index === activeSegment ? "chapter active" : "chapter"}
            onClick={() => onSeek(segment.start_ms)}
            aria-current={index === activeSegment ? "true" : undefined}
            title={segment.focus}
          >
            <span className="chapter-time">{formatClock(segment.start_ms)}</span>
            <span className="chapter-title">{segment.title}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

function TranscriptLine({
  line,
  index,
  hosts,
  active,
  selected,
  onSelect,
  lineRef,
}: {
  line: OverviewLine;
  index: number;
  hosts: string[];
  active: boolean;
  selected: boolean;
  onSelect: (index: number) => void;
  lineRef: (element: HTMLButtonElement | null) => void;
}) {
  const classes = ["transcript-line", hostClass(hosts, line.speaker)];
  if (active) classes.push("active");
  if (selected) classes.push("selected");
  return (
    <button
      type="button"
      ref={lineRef}
      className={classes.join(" ")}
      onClick={() => onSelect(index)}
      aria-current={active ? "true" : undefined}
    >
      <span className="transcript-speaker">
        <span className="host-dot" aria-hidden="true" />
        {line.speaker}
        <span className="transcript-time">{formatClock(line.start_ms)}</span>
      </span>
      <span className="transcript-text">
        {line.text}
        {line.source !== null && (
          <span className="transcript-cite" aria-label={`Source ${line.source + 1}`}>
            {line.source + 1}
          </span>
        )}
      </span>
    </button>
  );
}

function Transcript({
  overview,
  activeIndex,
  selectedIndex,
  onSelect,
}: {
  overview: AudioOverview;
  activeIndex: number;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const lineElements = useRef<(HTMLButtonElement | null)[]>([]);
  const [following, setFollowing] = useState(true);

  const scrollToLine = useCallback((index: number) => {
    const box = container.current;
    const element = lineElements.current[index];
    if (!box || !element) return;
    box.scrollTo({
      top: element.offsetTop - box.clientHeight * FOLLOW_OFFSET_RATIO,
      behavior: "smooth",
    });
  }, []);

  useEffect(() => {
    if (following && activeIndex >= 0) scrollToLine(activeIndex);
  }, [activeIndex, following, scrollToLine]);

  function resumeFollowing() {
    setFollowing(true);
    if (activeIndex >= 0) scrollToLine(activeIndex);
  }

  function select(index: number) {
    setFollowing(true);
    onSelect(index);
  }

  return (
    <div className="transcript-wrap">
      <div
        className="transcript"
        ref={container}
        onWheel={() => setFollowing(false)}
        onTouchMove={() => setFollowing(false)}
        aria-label="Transcript"
        role="region"
        tabIndex={0}
      >
        {overview.lines.map((line, index) => (
          <div key={index} className="transcript-row">
            {(index === 0 || overview.lines[index - 1].segment !== line.segment) && (
              <h3 className="transcript-segment">
                {overview.segments[line.segment]?.title ?? `Part ${line.segment + 1}`}
              </h3>
            )}
            <TranscriptLine
              line={line}
              index={index}
              hosts={overview.hosts}
              active={index === activeIndex}
              selected={index === selectedIndex}
              onSelect={select}
              lineRef={(element) => {
                lineElements.current[index] = element;
              }}
            />
          </div>
        ))}
      </div>
      {!following && activeIndex >= 0 && (
        <button type="button" className="follow-button" onClick={resumeFollowing}>
          <ArrowDownIcon />
          Back to current line
        </button>
      )}
    </div>
  );
}

function SourcePanel({
  overview,
  line,
  onOpen,
}: {
  overview: AudioOverview;
  line: OverviewLine | null;
  onOpen: (source: Source) => void;
}) {
  if (!line) {
    return (
      <aside className="source-panel empty-source">
        <p className="source-panel-label">Sources</p>
        <p className="hint">
          Click any line in the transcript to jump to it and see the passage it came from.
        </p>
      </aside>
    );
  }
  const source = line.source === null ? null : overview.sources[line.source];
  return (
    <aside className="source-panel" aria-live="polite">
      <p className="source-panel-label">
        {source ? `Source ${(line.source ?? 0) + 1} for this line` : "Source for this line"}
      </p>
      <blockquote className={`source-quote ${hostClass(overview.hosts, line.speaker)}`}>
        <span className="source-quote-speaker">{line.speaker}</span>
        {line.text}
      </blockquote>
      {source ? (
        <>
          <p className="source-file">
            <FileIcon />
            <span>{source.filename}</span>
          </p>
          <p className="source-passage">{source.content}</p>
          <button type="button" className="ghost source-open-doc" onClick={() => onOpen(source)}>
            Show in document
          </button>
        </>
      ) : (
        <p className="hint">
          This line is conversation (a question, reaction, or transition), so it doesn't cite a passage.
        </p>
      )}
    </aside>
  );
}

export function OverviewPlayer({
  overview,
  onDelete,
}: {
  overview: AudioOverview;
  onDelete: () => void;
}) {
  const audio = useRef<HTMLAudioElement>(null);
  const playback = usePlayback(audio);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [openSource, setOpenSource] = useState<Source | null>(null);
  useSpaceToToggle(playback.toggle);
  useMediaSession(overview);

  const activeIndex = useMemo(
    () => activeLineIndex(overview.lines, playback.positionMs),
    [overview.lines, playback.positionMs],
  );
  const activeSegment = activeIndex >= 0 ? overview.lines[activeIndex].segment : 0;
  const shownLine =
    selectedIndex !== null ? overview.lines[selectedIndex] : null;
  const audioUrl = overview.audio_filename ? overviewAudioUrl(overview.audio_filename) : "";
  const title = overview.title ?? "Audio overview";

  function selectLine(index: number) {
    setSelectedIndex(index);
    playback.seek(overview.lines[index].start_ms);
    playback.play();
  }

  return (
    <section className="overview-player" aria-label={title}>
      <audio ref={audio} src={audioUrl} preload="auto" {...playback.events} />
      <header className="player-header">
        <div className="player-cover" aria-hidden="true">
          <WaveIcon size={26} />
        </div>
        <div className="player-heading">
          <p className="player-eyebrow">Audio overview</p>
          <h2 className="player-title">{title}</h2>
          <p className="player-meta">
            {overview.collection_name ?? "Deleted collection"} ·{" "}
            {formatClock(overview.duration_ms ?? 0)} ·{" "}
            {new Date(overview.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="player-actions">
          <a className="icon-button" href={audioUrl} download={downloadName(title)} aria-label="Download MP3" title="Download MP3">
            <DownloadIcon />
          </a>
          <button type="button" className="icon-button danger-hover" onClick={onDelete} aria-label="Delete overview" title="Delete overview">
            <TrashIcon />
          </button>
        </div>
      </header>

      <div className="player-hosts">
        {overview.hosts.map((host) => {
          const speaking = activeIndex >= 0 && playback.playing && overview.lines[activeIndex].speaker === host;
          return (
            <span key={host} className={`host-chip ${hostClass(overview.hosts, host)}${speaking ? " speaking" : ""}`}>
              <span className="host-avatar" aria-hidden="true">{host[0]}</span>
              {host}
              {speaking && <span className="visually-hidden"> is speaking</span>}
            </span>
          );
        })}
        {overview.focus && <span className="player-focus">Focus: {overview.focus}</span>}
      </div>

      <div className="transport">
        <button type="button" className="transport-skip" onClick={() => playback.seek(playback.positionMs - SKIP_SECONDS * 1000)} aria-label={`Back ${SKIP_SECONDS} seconds`}>
          <SkipIcon forward={false} />
        </button>
        <button type="button" className="transport-play" onClick={playback.toggle} aria-label={playback.playing ? "Pause" : "Play"}>
          {playback.playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <button type="button" className="transport-skip" onClick={() => playback.seek(playback.positionMs + SKIP_SECONDS * 1000)} aria-label={`Forward ${SKIP_SECONDS} seconds`}>
          <SkipIcon forward />
        </button>
        <div className="transport-timeline">
          <Scrubber overview={overview} positionMs={playback.positionMs} onSeek={playback.seek} />
          <div className="transport-times">
            <span>{formatClock(playback.positionMs)}</span>
            <span>-{formatClock((overview.duration_ms ?? 0) - playback.positionMs)}</span>
          </div>
        </div>
        <button type="button" className="transport-speed" onClick={playback.cycleSpeed} aria-label={`Playback speed ${playback.speed}x`}>
          {playback.speed}×
        </button>
      </div>

      <Chapters overview={overview} activeSegment={activeSegment} onSeek={playback.seek} />

      <div className="player-body">
        <Transcript
          overview={overview}
          activeIndex={activeIndex}
          selectedIndex={selectedIndex}
          onSelect={selectLine}
        />
        <SourcePanel overview={overview} line={shownLine} onOpen={setOpenSource} />
      </div>

      {openSource && <DocumentViewer source={openSource} onClose={() => setOpenSource(null)} />}
    </section>
  );
}
