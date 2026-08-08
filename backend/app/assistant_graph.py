import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.config import settings
from app.rag.llm import LLMProvider, ToolCall
from app.tools import (
    DOCUMENT_SEARCH_DEFINITION,
    SourceChunk,
    Tool,
    to_definition,
)

SYSTEM_PROMPT = (
    "You are Cortex, a helpful knowledge assistant. "
    "The user's documents have already been searched with the raw question; "
    "the results follow. If they answer the question, answer directly from them. "
    "If they do not, split the question into sub-topics and run one focused "
    "search_documents call per sub-topic before anything else. "
    "Only use web_search when focused document searches also come back empty. "
    "Use the calculator for arithmetic and current_time for date or time. "
    "Document passages are labeled with bracketed numbers like [1]. "
    "When a claim in your answer comes from a passage, cite that passage's "
    "number right after the claim, like [1] or [2][3]. "
    "Cite only numbers that appear in the search results. "
    "Once you have the evidence, answer directly and concisely from it."
)

FALLBACK_ANSWER = "I could not finish answering within the tool call limit."

DECLINED_RESULT = "The user declined the web search."

APPROVAL_TOOLS = {"web_search"}

RESULT_PREVIEW_CHARS = 500


class AssistantState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    sources: Annotated[list[dict], operator.add]
    rounds: int


def parse_tool_calls(message: dict) -> list[ToolCall]:
    return [
        ToolCall(
            name=call["function"]["name"],
            arguments=call["function"].get("arguments") or {},
        )
        for call in message.get("tool_calls") or []
    ]


def execute_tool(tool_map: dict[str, Tool], call: ToolCall) -> str:
    tool = tool_map.get(call.name)
    if tool is None:
        return f"Unknown tool: {call.name}"
    try:
        return tool.run(**call.arguments)
    except Exception as error:
        return f"Tool error: {error}"


def preview(result: str) -> str:
    if len(result) <= RESULT_PREVIEW_CHARS:
        return result
    return result[:RESULT_PREVIEW_CHARS] + "…"


def number_sources(found: list[SourceChunk], offset: int) -> list[dict]:
    return [
        {"id": offset + position, "filename": chunk.filename, "content": chunk.content}
        for position, chunk in enumerate(found, start=1)
    ]


def format_sources(sources: list[dict]) -> str:
    if not sources:
        return "No matching documents found."
    return "\n\n---\n\n".join(
        f"[{source['id']}] {source['filename']}\n{source['content']}"
        for source in sources
    )


def build_assistant_graph(
    llm: LLMProvider,
    tools: list[Tool],
    search_documents,
    checkpointer: BaseCheckpointSaver | None = None,
):
    definitions = [DOCUMENT_SEARCH_DEFINITION, *(to_definition(tool) for tool in tools)]
    tool_map = {tool.name: tool for tool in tools}

    def run_document_search(query: str, offset: int, writer) -> tuple[list[dict], str]:
        found = number_sources(search_documents(query), offset)
        output = format_sources(found)
        writer(
            {
                "type": "tool_result",
                "name": "search_documents",
                "content": preview(output),
            }
        )
        if found:
            writer({"type": "sources", "sources": found})
        return found, output

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
        return {"messages": [reply.raw_message], "rounds": state["rounds"] + 1}

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
            else:
                output = execute_tool(tool_map, call)
                writer(
                    {
                        "type": "tool_result",
                        "name": call.name,
                        "content": preview(output),
                    }
                )
            results.append(
                {"role": "tool", "tool_name": call.name, "content": output}
            )
        return {"messages": results, "sources": new_sources}

    def next_step(state: AssistantState) -> str:
        wants_tools = bool(state["messages"][-1].get("tool_calls"))
        if wants_tools and state["rounds"] < settings.chat_max_rounds:
            return "tools"
        return END

    graph = StateGraph(AssistantState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("model", model)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "model")
    graph.add_conditional_edges("model", next_step, ["tools", END])
    graph.add_edge("tools", "model")
    return graph.compile(checkpointer=checkpointer)


def initial_state(history: list[dict], question: str) -> AssistantState:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": question},
        ],
        "sources": [],
        "rounds": 0,
    }


def final_answer(state: AssistantState) -> str:
    last = state["messages"][-1]
    if last.get("role") == "assistant" and last.get("content"):
        return last["content"]
    return FALLBACK_ANSWER


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
