import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { createAudioOverview, deleteAudioOverview, getAudioOverview } from "../api";
import type { AudioOverview } from "../types";
import { formatClock, OverviewPlayer, WaveIcon } from "./OverviewPlayer";
import { errorMessage, isUnfinished, overviewName } from "./overviewStatus";

const POLL_MS = 1500;

const STAGES = [
  { key: "reading", label: "Read" },
  { key: "planning", label: "Plan" },
  { key: "writing", label: "Write" },
  { key: "recording", label: "Record" },
  { key: "mixing", label: "Mix" },
];

function ArrowLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m12 19-7-7 7-7" />
      <path d="M19 12H5" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
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

function useElapsed(since: string): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return formatClock(now - new Date(since).getTime());
}

function useOverview(id: number) {
  const [overview, setOverview] = useState<AudioOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setOverview(null);
    setError(null);
    async function load() {
      try {
        const found = await getAudioOverview(id);
        if (cancelled) return;
        setOverview(found);
        if (isUnfinished(found)) timer = setTimeout(load, POLL_MS);
      } catch (caught) {
        if (!cancelled) setError(errorMessage(caught));
      }
    }
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id]);

  return { overview, error };
}

function StageSteps({ overview }: { overview: AudioOverview }) {
  const current = STAGES.findIndex((stage) => stage.key === overview.stage);
  return (
    <ol className="stage-steps">
      {STAGES.map((stage, index) => {
        const state =
          overview.status === "queued" || index > current
            ? "upcoming"
            : index < current
              ? "done"
              : "current";
        return (
          <li key={stage.key} className={`stage-step ${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="stage-marker" aria-hidden="true">
              {state === "done" ? <CheckIcon /> : index + 1}
            </span>
            <span className="stage-label">{stage.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function ProgressCard({
  overview,
  onCancel,
}: {
  overview: AudioOverview;
  onCancel: () => void;
}) {
  const elapsed = useElapsed(overview.created_at);
  const percent = Math.round(overview.progress * 100);
  const queued = overview.status === "queued";
  return (
    <section className="overview-progress" aria-label="Making the audio overview">
      <header className="player-header">
        <div className="player-cover working" aria-hidden="true">
          <WaveIcon size={26} />
        </div>
        <div className="player-heading">
          <p className="player-eyebrow">Making your audio overview</p>
          <h2 className="player-title">{overviewName(overview)}</h2>
          <p className="player-meta">
            {overview.collection_name ?? "Collection"} · {overview.length === "long" ? "Long" : "Short"} · {elapsed} elapsed
          </p>
          {overview.focus && <p className="player-meta">Focus: {overview.focus}</p>}
        </div>
      </header>
      <StageSteps overview={overview} />
      <div
        className="progress-bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label="Progress"
      >
        <div className="progress-fill" style={{ transform: `scaleX(${overview.progress})` }} />
      </div>
      <div className="progress-footer">
        <p className="progress-detail" aria-live="polite">
          {queued ? "Waiting for the overview ahead of it to finish" : overview.detail ?? "Starting"}
        </p>
        <span className="progress-percent">{percent}%</span>
      </div>
      <div className="progress-actions">
        <p className="hint">
          Usually takes a few minutes. You can leave this page; it keeps going in the background.
        </p>
        <button type="button" className="ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </section>
  );
}

function FailedCard({
  overview,
  onRetry,
  onDelete,
}: {
  overview: AudioOverview;
  onRetry: () => void;
  onDelete: () => void;
}) {
  return (
    <section className="overview-failed" role="alert">
      <span className="failed-icon">
        <AlertIcon />
      </span>
      <div className="failed-body">
        <h2 className="player-title">This overview didn't finish</h2>
        <p className="failed-detail">{overview.detail ?? "Something went wrong."}</p>
        <div className="row">
          {overview.collection_id !== null && (
            <button type="button" className="primary" onClick={onRetry}>
              Try again
            </button>
          )}
          <button type="button" className="ghost" onClick={onDelete}>
            Remove
          </button>
        </div>
      </div>
    </section>
  );
}

function SelectedOverview({
  id,
  onDeleted,
  onRetry,
}: {
  id: number;
  onDeleted: () => void;
  onRetry: (overview: AudioOverview) => void;
}) {
  const { overview, error } = useOverview(id);

  async function remove(confirmText: string | null) {
    if (confirmText && !window.confirm(confirmText)) return;
    await deleteAudioOverview(id).catch(() => {});
    onDeleted();
  }

  if (error) return <p className="error panel">{error}</p>;
  if (!overview) return <div className="overview-skeleton" aria-busy="true" aria-label="Loading overview" />;
  if (isUnfinished(overview))
    return <ProgressCard overview={overview} onCancel={() => remove("Stop making this overview?")} />;
  if (overview.status === "failed")
    return <FailedCard overview={overview} onRetry={() => onRetry(overview)} onDelete={() => remove(null)} />;
  return <OverviewPlayer overview={overview} onDelete={() => remove(`Delete "${overviewName(overview)}"?`)} />;
}

export default function OverviewDetailView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const overviewId = Number(id);

  async function retry(overview: AudioOverview) {
    if (overview.collection_id === null) return;
    const next = await createAudioOverview(overview.collection_id, overview.length, overview.focus ?? "");
    await deleteAudioOverview(overview.id).catch(() => {});
    navigate(`/overviews/${next.id}`, { replace: true });
  }

  return (
    <div className="page">
      <div className="page-inner overviews-page">
        <Link to="/overviews" className="back-link">
          <ArrowLeftIcon />
          All audio overviews
        </Link>
        <SelectedOverview key={overviewId} id={overviewId} onDeleted={() => navigate("/overviews")} onRetry={retry} />
      </div>
    </div>
  );
}
