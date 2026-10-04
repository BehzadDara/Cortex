import os
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid5

from langsmith import Client, get_current_run_tree, traceable, tracing_context
from langsmith.utils import LangSmithNotFoundError

from app.config import settings


def enable_tracing(project: str) -> None:
    if not settings.langsmith_tracing:
        return
    os.environ.update(
        LANGSMITH_TRACING="true",
        LANGSMITH_API_KEY=settings.langsmith_api_key,
        LANGSMITH_ENDPOINT=settings.langsmith_endpoint,
        LANGSMITH_PROJECT=project,
    )


def without(hidden: Sequence[str]) -> Callable[[dict], dict]:
    def strip(inputs: dict) -> dict:
        return {name: value for name, value in inputs.items() if name not in hidden}

    return strip


def traced(
    name: str,
    run_type: str = "chain",
    hidden_inputs: Sequence[str] = (),
    format_output: Callable[[Any], dict] | None = None,
    reduce_stream: Callable[[list], Any] | None = None,
) -> Callable:
    return traceable(
        name=name,
        run_type=run_type,
        process_inputs=without(hidden_inputs),
        process_outputs=format_output,
        reduce_fn=reduce_stream,
    )


def describe_run(**metadata: Any) -> None:
    run = get_current_run_tree()
    if run is not None:
        run.metadata.update(metadata)


def record_token_usage(input_tokens: int, output_tokens: int) -> None:
    describe_run(
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
    )


@contextmanager
def conversation_thread(conversation_id: int) -> Iterator[None]:
    with tracing_context(metadata={"thread_id": str(conversation_id)}):
        yield


@lru_cache
def feedback_client() -> Client:
    return Client(
        api_key=settings.langsmith_api_key, api_url=settings.langsmith_endpoint
    )


def record_feedback(trace_id: str, key: str, score: int | None) -> None:
    if not settings.langsmith_tracing:
        return
    feedback_id = uuid5(UUID(trace_id), key)
    if score is None:
        delete_feedback(feedback_id)
        return
    try:
        feedback_client().update_feedback(feedback_id, score=score)
    except LangSmithNotFoundError:
        feedback_client().create_feedback(
            trace_id, key, score=score, feedback_id=feedback_id
        )


def delete_feedback(feedback_id: UUID) -> None:
    try:
        feedback_client().delete_feedback(feedback_id)
    except LangSmithNotFoundError:
        return
