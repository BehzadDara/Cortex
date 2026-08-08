import operator
from typing import Annotated, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.rag.llm import LLMProvider, ToolCall
from app.tools import Tool, to_definition

SYSTEM_PROMPT = (
    "You are Cortex, a helpful knowledge assistant. "
    "Use search_documents to answer questions about the user's documents. "
    "Break complex questions into several focused search_documents calls, "
    "one per sub-topic. "
    "If the documents contain nothing relevant, use web_search. "
    "Use the calculator for arithmetic and current_time for date or time. "
    "Once you have the evidence, answer directly and concisely from it."
)

FALLBACK_ANSWER = "I could not finish answering within the tool call limit."

RESULT_PREVIEW_CHARS = 500


class AssistantState(TypedDict):
    messages: Annotated[list[dict], operator.add]
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


def build_assistant_graph(llm: LLMProvider, tools: list[Tool]):
    definitions = [to_definition(tool) for tool in tools]
    tool_map = {tool.name: tool for tool in tools}

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
        results = []
        for call in parse_tool_calls(state["messages"][-1]):
            output = execute_tool(tool_map, call)
            writer(
                {"type": "tool_result", "name": call.name, "content": preview(output)}
            )
            results.append(
                {"role": "tool", "tool_name": call.name, "content": output}
            )
        return {"messages": results}

    def next_step(state: AssistantState) -> str:
        wants_tools = bool(state["messages"][-1].get("tool_calls"))
        if wants_tools and state["rounds"] < settings.chat_max_rounds:
            return "tools"
        return END

    graph = StateGraph(AssistantState)
    graph.add_node("model", model)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", next_step, ["tools", END])
    graph.add_edge("tools", "model")
    return graph.compile()


def initial_state(history: list[dict], question: str) -> AssistantState:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": question},
        ],
        "rounds": 0,
    }


def final_answer(state: AssistantState) -> str:
    last = state["messages"][-1]
    if last.get("role") == "assistant" and last.get("content"):
        return last["content"]
    return FALLBACK_ANSWER
