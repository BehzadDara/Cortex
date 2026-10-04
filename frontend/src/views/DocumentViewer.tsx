import { useEffect, useRef, useState } from "react";
import { locatePassage } from "../api";
import type { Passage, Source } from "../types";

function CloseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

function usePassage(source: Source) {
  const [passage, setPassage] = useState<Passage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    locatePassage(source).then(
      (found) => {
        if (!cancelled) setPassage(found);
      },
      (reason: Error) => {
        if (!cancelled) setError(reason.message);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [source]);

  return { passage, error };
}

function useEscape(onEscape: () => void) {
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if (event.key === "Escape") onEscape();
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [onEscape]);
}

function HighlightedText({ passage }: { passage: Passage }) {
  const highlight = useRef<HTMLElement>(null);

  useEffect(() => {
    highlight.current?.scrollIntoView({ block: "start" });
  }, [passage]);

  return (
    <pre className="viewer-text">
      {passage.text.slice(0, passage.start)}
      <mark ref={highlight}>{passage.text.slice(passage.start, passage.end)}</mark>
      {passage.text.slice(passage.end)}
    </pre>
  );
}

export function DocumentViewer({
  source,
  onClose,
}: {
  source: Source;
  onClose: () => void;
}) {
  const { passage, error } = usePassage(source);
  useEscape(onClose);

  return (
    <div className="viewer-backdrop" onClick={onClose}>
      <div
        className="viewer"
        role="dialog"
        aria-label={source.filename}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="viewer-header">
          <span className="viewer-title">{source.filename}</span>
          <button className="viewer-close" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>
        <div className="viewer-body">
          {error && <p className="viewer-status">{error}</p>}
          {!error && !passage && <p className="viewer-status">Loading…</p>}
          {passage && <HighlightedText passage={passage} />}
        </div>
      </div>
    </div>
  );
}
