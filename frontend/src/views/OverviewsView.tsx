import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { createAudioOverview, deleteAudioOverview, getAudioOverviews, getCollections } from "../api";
import type { AudioOverview, AudioOverviewSummary, Collection, OverviewLength } from "../types";
import { formatClock, WaveIcon } from "./OverviewPlayer";
import { errorMessage, isUnfinished, overviewName } from "./overviewStatus";

const LIBRARY_POLL_MS = 3000;

const LENGTHS: { value: OverviewLength; label: string; detail: string }[] = [
  { value: "short", label: "Short", detail: "About 5 minutes" },
  { value: "long", label: "Long", detail: "About 10 minutes" },
];

function ChevronIcon() {
  return (
    <svg className="library-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m9 18 6-6-6-6" />
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

function useLibrary() {
  const [overviews, setOverviews] = useState<AudioOverviewSummary[] | null>(null);
  const refresh = useCallback(() => {
    getAudioOverviews().then(setOverviews).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  const working = (overviews ?? []).some(isUnfinished);
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(refresh, LIBRARY_POLL_MS);
    return () => clearInterval(timer);
  }, [working, refresh]);

  return { overviews, refresh };
}

function CreatePanel({
  collections,
  initialCollectionId,
  onCreated,
}: {
  collections: Collection[];
  initialCollectionId: number | null;
  onCreated: (overview: AudioOverview) => void;
}) {
  const usable = collections.filter((collection) => collection.document_count > 0);
  const [collectionId, setCollectionId] = useState<number | null>(initialCollectionId);
  const [length, setLength] = useState<OverviewLength>("short");
  const [focus, setFocus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialCollectionId !== null) setCollectionId(initialCollectionId);
  }, [initialCollectionId]);

  const chosen = collectionId ?? usable[0]?.id ?? null;

  async function create() {
    if (chosen === null) return;
    setSubmitting(true);
    setError(null);
    try {
      const overview = await createAudioOverview(chosen, length, focus.trim());
      setFocus("");
      onCreated(overview);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="panel overview-create">
      <h2>New audio overview</h2>
      <p className="panel-note">
        Two hosts, Ava and Michael, talk through a collection like a podcast. Every line keeps the
        passage it came from, and everything runs on this Mac.
      </p>
      {collections.length > 0 && usable.length === 0 ? (
        <p className="empty">Add documents to a collection first, then come back to make an overview.</p>
      ) : (
        <>
          <div className="overview-form">
            <div className="field">
              <label htmlFor="overview-collection">Collection</label>
              <select
                id="overview-collection"
                value={chosen ?? ""}
                onChange={(event) => setCollectionId(Number(event.target.value))}
              >
                {collections.map((collection) => (
                  <option key={collection.id} value={collection.id} disabled={collection.document_count === 0}>
                    {collection.name} · {collection.document_count}{" "}
                    {collection.document_count === 1 ? "document" : "documents"}
                  </option>
                ))}
              </select>
            </div>
            <fieldset className="field length-field">
              <legend>Length</legend>
              <div className="segmented">
                {LENGTHS.map((option) => (
                  <label key={option.value} className={length === option.value ? "segment checked" : "segment"}>
                    <input
                      type="radio"
                      name="overview-length"
                      value={option.value}
                      checked={length === option.value}
                      onChange={() => setLength(option.value)}
                    />
                    <span className="segment-label">{option.label}</span>
                    <span className="segment-detail">{option.detail}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
          <div className="field">
            <label htmlFor="overview-focus">
              Focus <span className="optional">optional</span>
            </label>
            <input
              id="overview-focus"
              className="full"
              maxLength={300}
              placeholder="e.g. the surprising results, explained for a beginner"
              value={focus}
              onChange={(event) => setFocus(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && create()}
            />
          </div>
          <div className="overview-submit">
            <button type="button" className="primary make-overview" onClick={create} disabled={submitting || chosen === null}>
              <WaveIcon size={15} />
              {submitting ? "Starting…" : "Make an audio overview"}
            </button>
            <span className="hint">Takes a few minutes and keeps going if you leave.</span>
          </div>
          {error && <p className="error">{error}</p>}
        </>
      )}
    </div>
  );
}

function LibraryRow({
  overview,
  onDelete,
}: {
  overview: AudioOverviewSummary;
  onDelete: () => void;
}) {
  const working = isUnfinished(overview);
  const status =
    overview.status === "done"
      ? formatClock(overview.duration_ms ?? 0)
      : overview.status === "failed"
        ? "Failed"
        : overview.status === "queued"
          ? "Queued"
          : `${Math.round(overview.progress * 100)}%`;
  return (
    <li className="library-row">
      <Link to={`/overviews/${overview.id}`} className="library-open">
        <span className={`library-icon ${overview.status}`} aria-hidden="true">
          <WaveIcon size={16} />
        </span>
        <span className="library-text">
          <span className="library-title">{overviewName(overview)}</span>
          <span className="library-meta">
            {overview.collection_name ?? "Deleted collection"} · {overview.length === "long" ? "Long" : "Short"} ·{" "}
            {new Date(overview.created_at).toLocaleDateString()}
          </span>
          {working && (
            <span className="library-progress" aria-hidden="true">
              <span style={{ transform: `scaleX(${overview.progress})` }} />
            </span>
          )}
        </span>
        <span className={`library-status ${overview.status}`}>{status}</span>
        <ChevronIcon />
      </Link>
      <button type="button" className="icon-button danger-hover" onClick={onDelete} aria-label={`Delete ${overviewName(overview)}`} title="Delete">
        <TrashIcon />
      </button>
    </li>
  );
}

export default function OverviewsView() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const requestedCollection = searchParams.get("collection");
  const [collections, setCollections] = useState<Collection[]>([]);
  const { overviews, refresh } = useLibrary();

  useEffect(() => {
    getCollections().then(setCollections).catch(() => {});
  }, []);

  function created(overview: AudioOverview) {
    navigate(`/overviews/${overview.id}`);
  }

  async function remove(overview: AudioOverviewSummary) {
    if (!window.confirm(`Delete "${overviewName(overview)}"?`)) return;
    await deleteAudioOverview(overview.id).catch(() => {});
    refresh();
  }

  return (
    <div className="page">
      <div className="page-inner overviews-page">
        <header className="overviews-header">
          <h1>Audio overviews</h1>
          <p className="hint">Podcast-style conversations about your collections, made and played on this Mac.</p>
        </header>
        <CreatePanel
          collections={collections}
          initialCollectionId={requestedCollection ? Number(requestedCollection) : null}
          onCreated={created}
        />
        <div className="panel">
          <h2>Library{overviews ? ` (${overviews.length})` : ""}</h2>
          {overviews === null ? (
            <p className="empty" aria-busy="true">Loading…</p>
          ) : overviews.length === 0 ? (
            <p className="empty">No overviews yet. Pick a collection above and make your first one.</p>
          ) : (
            <ul className="library">
              {overviews.map((overview) => (
                <LibraryRow key={overview.id} overview={overview} onDelete={() => remove(overview)} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
