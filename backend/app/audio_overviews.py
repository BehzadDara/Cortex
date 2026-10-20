import threading
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.dependencies import (
    get_embedding_provider,
    get_host_voices,
    get_overview_audio_store,
    get_overview_writer,
    get_reranker,
    get_vector_store,
)
from app.models import AudioOverview, Chunk, Document
from app.rag.audio_mixing import Clip, MixedEpisode, mix_episode
from app.rag.audio_overview import (
    EPISODE_LENGTHS,
    Outline,
    Passage,
    PassageSearch,
    ProgressCallback,
    Script,
    ScriptLine,
    SourceDocument,
    plan_outline,
    summarize_documents,
    write_script,
)
from app.rag.chunking import stitch_chunks
from app.rag.retrieval import retrieve_chunks
from app.rag.speech import TextToSpeech, spoken_text

STAGE_SPANS = {
    "reading": (0.0, 0.15),
    "planning": (0.15, 0.2),
    "writing": (0.2, 0.5),
    "recording": (0.5, 0.97),
    "mixing": (0.97, 1.0),
}
UNFINISHED = ("queued", "running")
INTERRUPTED = "Cortex restarted before this overview finished. Try again."

production_lock = threading.Lock()


class OverviewDeleted(Exception):
    pass


class ProgressReporter:
    def __init__(self, overview_id: int) -> None:
        self.overview_id = overview_id

    def save(self, **values) -> None:
        with SessionLocal() as session:
            result = session.execute(
                update(AudioOverview)
                .where(AudioOverview.id == self.overview_id)
                .values(**values)
            )
            session.commit()
        if result.rowcount == 0:
            raise OverviewDeleted

    def stage(self, stage: str) -> ProgressCallback:
        start, end = STAGE_SPANS[stage]

        def report(fraction: float, detail: str) -> None:
            self.save(
                stage=stage, progress=start + (end - start) * fraction, detail=detail
            )

        return report


def largest_document_ids(session: Session, collection_id: int) -> list[int]:
    query = (
        select(Document.id)
        .join(Chunk)
        .where(Document.collection_id == collection_id)
        .group_by(Document.id)
        .order_by(func.count(Chunk.id).desc())
        .limit(settings.overview_max_documents)
    )
    return list(session.scalars(query))


def focused_document_ids(session: Session, collection_id: int, focus: str) -> list[int]:
    chunks = retrieve_chunks(
        session,
        focus,
        settings.overview_max_documents * settings.overview_passages_per_segment,
        get_embedding_provider(),
        get_vector_store(),
        collection_id,
        get_reranker(),
    )
    return [chunk.document_id for chunk in chunks]


def chosen_document_ids(
    session: Session, collection_id: int, focus: str | None
) -> list[int]:
    focused = focused_document_ids(session, collection_id, focus) if focus else []
    ranked = dict.fromkeys(focused + largest_document_ids(session, collection_id))
    return list(ranked)[: settings.overview_max_documents]


def collection_documents(
    session: Session, collection_id: int, focus: str | None
) -> list[SourceDocument]:
    documents = []
    for document_id in chosen_document_ids(session, collection_id, focus):
        document = session.get(Document, document_id)
        chunks = sorted(document.chunks, key=lambda chunk: chunk.position)
        text, _ = stitch_chunks([chunk.content for chunk in chunks])
        documents.append(SourceDocument(filename=document.filename, text=text))
    return documents


def passage_search(session: Session, collection_id: int) -> PassageSearch:
    def search(query: str) -> list[Passage]:
        chunks = retrieve_chunks(
            session,
            query,
            settings.overview_passages_per_segment,
            get_embedding_provider(),
            get_vector_store(),
            collection_id,
            get_reranker(),
        )
        return [
            Passage(chunk_id=chunk.id, filename=chunk.document.filename, content=chunk.content)
            for chunk in chunks
        ]

    return search


def record_lines(
    lines: list[ScriptLine], voices: dict[str, TextToSpeech], report: ProgressCallback
) -> list[Clip]:
    clips = []
    for index, line in enumerate(lines):
        report(index / len(lines), f"Recording line {index + 1} of {len(lines)}")
        audio = voices[line.speaker].speak(spoken_text(line.text))
        clips.append(Clip(audio=audio, speaker=line.speaker, segment=line.segment))
    return clips


def finished_values(
    outline: Outline, script: Script, episode: MixedEpisode, filename: str
) -> dict:
    lines = [
        {
            "segment": line.segment,
            "speaker": line.speaker,
            "text": line.text,
            "source": line.source,
            "start_ms": start,
            "end_ms": end,
        }
        for line, (start, end) in zip(script.lines, episode.timings)
    ]
    segment_starts = {}
    for line in lines:
        segment_starts.setdefault(line["segment"], line["start_ms"])
    segments = [
        {"title": segment.title, "focus": segment.focus, "start_ms": segment_starts[index]}
        for index, segment in enumerate(outline.segments)
        if index in segment_starts
    ]
    sources = [
        {"id": source.chunk_id, "filename": source.filename, "content": source.content}
        for source in script.sources
    ]
    return {
        "status": "done",
        "stage": None,
        "progress": 1.0,
        "detail": None,
        "segments": segments,
        "lines": lines,
        "sources": sources,
        "audio_filename": filename,
        "duration_ms": episode.duration_ms,
        "finished_at": datetime.now(timezone.utc),
    }


def produce_overview(overview_id: int, reporter: ProgressReporter) -> None:
    with SessionLocal() as session:
        overview = session.get(AudioOverview, overview_id)
        if overview is None or overview.collection_id is None:
            raise OverviewDeleted
        length = EPISODE_LENGTHS[overview.length]
        documents = collection_documents(session, overview.collection_id, overview.focus)
        if not documents:
            raise ValueError("This collection has no documents yet.")
        llm = get_overview_writer()
        hosts = tuple(settings.overview_host_voices)

        summaries = summarize_documents(llm, documents, reporter.stage("reading"))
        reporter.stage("planning")(0.0, "Planning the episode")
        outline = plan_outline(llm, summaries, hosts, length, overview.focus)
        reporter.save(title=outline.title)
        script = write_script(
            llm,
            outline,
            passage_search(session, overview.collection_id),
            hosts,
            length,
            reporter.stage("writing"),
        )

    clips = record_lines(script.lines, get_host_voices(), reporter.stage("recording"))
    reporter.stage("mixing")(0.0, "Mixing the episode")
    episode = mix_episode(clips, seed=overview_id)
    store = get_overview_audio_store()
    filename = store.save(episode.audio, "mp3")
    try:
        reporter.save(**finished_values(outline, script, episode, filename))
    except OverviewDeleted:
        store.delete(filename)
        raise


def run_audio_overview(overview_id: int) -> None:
    reporter = ProgressReporter(overview_id)
    with production_lock:
        try:
            reporter.save(status="running", stage="reading", detail="Reading your documents")
            produce_overview(overview_id, reporter)
        except OverviewDeleted:
            return
        except Exception as error:
            try:
                reporter.save(
                    status="failed",
                    detail=str(error) or type(error).__name__,
                    finished_at=datetime.now(timezone.utc),
                )
            except OverviewDeleted:
                return


def fail_interrupted_overviews() -> None:
    with SessionLocal() as session:
        session.execute(
            update(AudioOverview)
            .where(AudioOverview.status.in_(UNFINISHED))
            .values(
                status="failed",
                detail=INTERRUPTED,
                finished_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
