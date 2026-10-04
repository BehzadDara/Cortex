import os
from collections.abc import Callable, Sequence
from typing import Any

from langsmith import get_current_run_tree, traceable

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
