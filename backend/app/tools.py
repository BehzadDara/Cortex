import ast
import operator
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.rag.embeddings import EmbeddingProvider
from app.rag.reranking import Reranker
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    run: Callable[..., str]


def to_definition(tool: Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY_OPERATORS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def evaluate_node(node: ast.expr) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY_OPERATORS:
        left = evaluate_node(node.left)
        right = evaluate_node(node.right)
        return BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPERATORS:
        return UNARY_OPERATORS[type(node.op)](evaluate_node(node.operand))
    raise ValueError("Unsupported expression")


def calculate(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    return str(evaluate_node(tree.body))


def current_time() -> str:
    return datetime.now().astimezone().strftime("%A, %Y-%m-%d %H:%M:%S %Z")


def build_tools(
    session: Session,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
) -> list[Tool]:
    def search_documents(query: str) -> str:
        chunks = retrieve_chunks(
            session, query, settings.top_k, embeddings, vector_store, reranker=reranker
        )
        if not chunks:
            return "No matching documents found."
        return "\n\n---\n\n".join(
            f"[{chunk.document.filename}]\n{chunk.content}" for chunk in chunks
        )

    return [
        Tool(
            name="search_documents",
            description="Search the user's indexed documents and return the most relevant passages.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"],
            },
            run=search_documents,
        ),
        Tool(
            name="calculator",
            description="Evaluate an arithmetic expression using numbers and the operators + - * / % **.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The arithmetic expression, e.g. (3 + 4) * 2",
                    }
                },
                "required": ["expression"],
            },
            run=calculate,
        ),
        Tool(
            name="current_time",
            description="Get the current local date and time.",
            parameters={"type": "object", "properties": {}},
            run=current_time,
        ),
    ]
