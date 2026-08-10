import operator
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.config import settings
from app.rag.llm import LLMProvider, ToolCall
from app.rag.prompts import build_route_prompt
from app.tools import (
    DOCUMENT_SEARCH_DEFINITION,
    WEB_SEARCH_DEFINITION,
    SourceChunk,
    Tool,
    ToolOutput,
    to_definition,
)

SYSTEM_PROMPT = (
    "You are Cortex, a helpful knowledge assistant. "
    "When document search results appear below, use them: if they answer the "
    "question, answer directly from them; if they do not, split the question "
    "into sub-topics and run one focused search_documents call per sub-topic "
    "before anything else, and only use web_search when those also come back "
    "empty. "
    "If the message is just small talk or tells you what to say back, answer "
    "it directly and never search for it. The same applies when the message "
    "itself already contains everything needed to answer. "
    "When no document results appear, the question does not need the user's "
    "documents: use web_search for live or public information that no "
    "dedicated tool covers. "
    "Use the calculator for arithmetic. "
    "Use world_clock for date or time, passing the IANA timezone of the place "
    "the user asks about, like Asia/Tehran; when no place is named, pass the "
    "user's timezone. "
    "Use get_weather for current weather in a place. "
    "Use crypto_price for cryptocurrency prices, passing the CoinGecko id "
    "like bitcoin or ethereum. "
    "Use kb_stats when the user asks how many documents, chunks, "
    "collections, or conversations their knowledge base holds, and "
    "usage_stats when they ask how much they have used Cortex — prompts, "
    "tokens, or latency. "
    "world_clock, get_weather, crypto_price, kb_stats, and usage_stats each "
    "render a visual card in the interface, so after calling one, answer in "
    "one short sentence and never repeat the card's numbers in a list or "
    "table. "
    "Document passages and web results are labeled with bracketed numbers "
    "like [1]. When a claim in your answer comes from one, cite its number "
    "right after the claim, like [1] or [2][3]. "
    "Cite only numbers that appear in the search results. "
    "If you have no search results, do not write bracketed numbers at all. "
    "When the user asks for a diagram, flowchart, or chart, write it as a "
    "mermaid code block — the interface renders mermaid. Prefer flowchart "
    "syntax and always put node labels in double quotes, like "
    'A["label"] --> B["label"]. Keep citation numbers out of the diagram; '
    "cite in the surrounding text instead. "
    "Once you have the evidence, answer directly and concisely from it."
)

FALLBACK_ANSWER = "I could not finish answering within the tool call limit."

DECLINED_RESULT = "The user declined the web search."

APPROVAL_TOOLS = {"web_search"}

RESULT_PREVIEW_CHARS = 500


class AssistantState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    sources: Annotated[list[dict], operator.add]
    widgets: Annotated[list[dict], operator.add]
    needs_documents: bool
    rounds: int
    elapsed_ms: Annotated[int, operator.add]
    prompt_tokens: Annotated[int, operator.add]
    response_tokens: Annotated[int, operator.add]


@dataclass
class RunUsage:
    elapsed_ms: int
    prompt_tokens: int
    response_tokens: int


def timed(node):
    def run(state: AssistantState) -> dict:
        started = time.perf_counter()
        update = node(state)
        update["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        return update

    return run


def parse_tool_calls(message: dict) -> list[ToolCall]:
    return [
        ToolCall(
            name=call["function"]["name"],
            arguments=call["function"].get("arguments") or {},
        )
        for call in message.get("tool_calls") or []
    ]


def execute_tool(tool_map: dict[str, Tool], call: ToolCall) -> ToolOutput:
    tool = tool_map.get(call.name)
    if tool is None:
        return ToolOutput(text=f"Unknown tool: {call.name}")
    try:
        result = tool.run(**call.arguments)
    except Exception as error:
        return ToolOutput(text=f"Tool error: {error}")
    if isinstance(result, ToolOutput):
        return result
    return ToolOutput(text=result)


def preview(result: str) -> str:
    if len(result) <= RESULT_PREVIEW_CHARS:
        return result
    return result[:RESULT_PREVIEW_CHARS] + "…"


def number_sources(found: list[SourceChunk], offset: int) -> list[dict]:
    return [
        {
            "id": offset + position,
            "filename": chunk.filename,
            "content": chunk.content,
            "url": chunk.url,
        }
        for position, chunk in enumerate(found, start=1)
    ]


def format_source(source: dict) -> str:
    header = f"[{source['id']}] {source['filename']}"
    if source["url"]:
        header += f"\n{source['url']}"
    return f"{header}\n{source['content']}"


def format_sources(sources: list[dict], empty_message: str) -> str:
    if not sources:
        return empty_message
    return "\n\n---\n\n".join(format_source(source) for source in sources)


def decide_route(fast_llm: LLMProvider, question: str) -> bool:
    try:
        decision = fast_llm.complete(build_route_prompt(question))
    except Exception:
        return True
    return not decision.strip().lower().startswith("no")


def build_assistant_graph(
    llm: LLMProvider,
    fast_llm: LLMProvider,
    tools: list[Tool],
    search_documents,
    search_web,
    checkpointer: BaseCheckpointSaver | None = None,
):
    definitions = [
        DOCUMENT_SEARCH_DEFINITION,
        WEB_SEARCH_DEFINITION,
        *(to_definition(tool) for tool in tools),
    ]
    tool_map = {tool.name: tool for tool in tools}

    def run_search(
        search, name: str, empty_message: str, query: str, offset: int, writer
    ) -> tuple[list[dict], str]:
        found = number_sources(search(query), offset)
        output = format_sources(found, empty_message)
        writer({"type": "tool_result", "name": name, "content": preview(output)})
        if found:
            writer({"type": "sources", "sources": found})
        return found, output

    def run_document_search(query: str, offset: int, writer) -> tuple[list[dict], str]:
        return run_search(
            search_documents,
            "search_documents",
            "No matching documents found.",
            query,
            offset,
            writer,
        )

    def run_web_search(query: str, offset: int, writer) -> tuple[list[dict], str]:
        return run_search(
            search_web, "web_search", "No web results found.", query, offset, writer
        )

    def route(state: AssistantState) -> dict:
        return {"needs_documents": decide_route(fast_llm, state_question(state))}

    def after_route(state: AssistantState) -> str:
        return "retrieve" if state["needs_documents"] else "model"

    def retrieve(state: AssistantState) -> dict:
        writer = get_stream_writer()
        question = state_question(state)
        writer(
            {
                "type": "tool_call",
                "name": "search_documents",
                "arguments": {"query": question},
            }
        )
        found, output = run_document_search(question, len(state["sources"]), writer)
        return {
            "sources": found,
            "messages": [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_documents",
                                "arguments": {"query": question},
                            }
                        }
                    ],
                },
                {"role": "tool", "tool_name": "search_documents", "content": output},
            ],
        }

    def model(state: AssistantState) -> dict:
        writer = get_stream_writer()
        reply = llm.chat_stream(
            state["messages"],
            definitions,
            lambda token: writer({"type": "token", "content": token}),
        )
        for call in reply.tool_calls:
            writer(
                {"type": "tool_call", "name": call.name, "arguments": call.arguments}
            )
        return {
            "messages": [reply.raw_message],
            "rounds": state["rounds"] + 1,
            "prompt_tokens": reply.prompt_tokens,
            "response_tokens": reply.response_tokens,
        }

    def run_tools(state: AssistantState) -> dict:
        writer = get_stream_writer()
        calls = parse_tool_calls(state["messages"][-1])
        approvals = {
            index: interrupt({"name": call.name, "arguments": call.arguments})
            for index, call in enumerate(calls)
            if call.name in APPROVAL_TOOLS
        }
        results = []
        new_sources: list[dict] = []
        new_widgets: list[dict] = []
        for index, call in enumerate(calls):
            if approvals.get(index) is False:
                output = DECLINED_RESULT
                writer(
                    {
                        "type": "tool_result",
                        "name": call.name,
                        "content": preview(output),
                    }
                )
            elif call.name == "search_documents":
                offset = len(state["sources"]) + len(new_sources)
                found, output = run_document_search(
                    str(call.arguments.get("query", "")), offset, writer
                )
                new_sources.extend(found)
            elif call.name == "web_search":
                offset = len(state["sources"]) + len(new_sources)
                found, output = run_web_search(
                    str(call.arguments.get("query", "")), offset, writer
                )
                new_sources.extend(found)
            else:
                tool_output = execute_tool(tool_map, call)
                output = tool_output.text
                writer(
                    {
                        "type": "tool_result",
                        "name": call.name,
                        "content": preview(output),
                    }
                )
                if tool_output.widget is not None:
                    widget = {
                        "kind": tool_output.widget.kind,
                        "data": tool_output.widget.data,
                    }
                    writer({"type": "widget", "widget": widget})
                    new_widgets.append(widget)
            results.append(
                {"role": "tool", "tool_name": call.name, "content": output}
            )
        return {"messages": results, "sources": new_sources, "widgets": new_widgets}

    def next_step(state: AssistantState) -> str:
        wants_tools = bool(state["messages"][-1].get("tool_calls"))
        if wants_tools and state["rounds"] < settings.chat_max_rounds:
            return "tools"
        return END

    graph = StateGraph(AssistantState)
    graph.add_node("route", timed(route))
    graph.add_node("retrieve", timed(retrieve))
    graph.add_node("model", timed(model))
    graph.add_node("tools", timed(run_tools))
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", after_route, ["retrieve", "model"])
    graph.add_edge("retrieve", "model")
    graph.add_conditional_edges("model", next_step, ["tools", END])
    graph.add_edge("tools", "model")
    return graph.compile(checkpointer=checkpointer)


def system_message(timezone: str | None = None) -> dict:
    today = datetime.now().strftime("%A, %B %-d, %Y")
    content = f"{SYSTEM_PROMPT} Today is {today}."
    if timezone:
        content += f" The user's timezone is {timezone}."
    return {"role": "system", "content": content}


def initial_state(
    history: list[dict], question: str, timezone: str | None = None
) -> AssistantState:
    return {
        "messages": [
            system_message(timezone),
            *history,
            {"role": "user", "content": question},
        ],
        "sources": [],
        "widgets": [],
        "needs_documents": True,
        "rounds": 0,
        "elapsed_ms": 0,
        "prompt_tokens": 0,
        "response_tokens": 0,
    }


CITATION_MARKER = re.compile(r"\s*\[\d+\](?!\()")


def strip_citation_markers(text: str) -> str:
    return CITATION_MARKER.sub("", text).strip()


def final_answer(state: AssistantState) -> str:
    last = state["messages"][-1]
    if last.get("role") == "assistant" and last.get("content"):
        answer = last["content"]
        return answer if state.get("sources") else strip_citation_markers(answer)
    return FALLBACK_ANSWER


def state_usage(state: AssistantState) -> RunUsage:
    return RunUsage(
        elapsed_ms=state.get("elapsed_ms", 0),
        prompt_tokens=state.get("prompt_tokens", 0),
        response_tokens=state.get("response_tokens", 0),
    )


def state_question(state: AssistantState) -> str:
    return next(
        message["content"]
        for message in reversed(state["messages"])
        if message.get("role") == "user"
    )


def extract_steps(messages: list[dict]) -> list[dict]:
    steps: list[dict] = []
    for message in messages:
        for call in parse_tool_calls(message):
            steps.append(
                {"name": call.name, "arguments": call.arguments, "result": None}
            )
        if message.get("role") == "tool":
            for step in steps:
                if step["name"] == message.get("tool_name") and step["result"] is None:
                    step["result"] = preview(message["content"])
                    break
    return steps
