import ast
import operator
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Collection, Conversation, Document, PromptLog
from app.rag.embeddings import EmbeddingProvider
from app.rag.image_generation import GeneratedImage, ImageGenerator
from app.rag.market_data import MarketDataProvider
from app.rag.reranking import Reranker
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore
from app.rag.weather import WeatherProvider
from app.rag.web_search import WebSearchProvider


@dataclass
class Widget:
    kind: str
    data: dict


@dataclass
class ToolOutput:
    text: str
    widget: Widget | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    run: Callable[..., str | ToolOutput]


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


def resolve_zone(name: str):
    if name in ("", "local"):
        return datetime.now().astimezone().tzinfo
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def format_utc_offset(moment: datetime) -> str:
    offset = moment.utcoffset()
    total_minutes = int(offset.total_seconds() // 60) if offset else 0
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def zone_label(zone_name: str) -> str:
    return zone_name.rsplit("/", 1)[-1].replace("_", " ")


def world_clock(timezone: str = "local") -> ToolOutput:
    zone = resolve_zone(timezone)
    if zone is None:
        return ToolOutput(
            text=(
                f"Unknown timezone '{timezone}'. "
                "Pass an IANA name like Asia/Tehran or Europe/Berlin."
            )
        )
    now = datetime.now(zone)
    offset = format_utc_offset(now)
    label = zone_label(timezone) if timezone not in ("", "local") else "your timezone"
    return ToolOutput(
        text=(
            f"Current time in {label}: "
            f"{now.strftime('%A, %Y-%m-%d %H:%M')} (UTC{offset})"
        ),
        widget=Widget(
            kind="clock",
            data={
                "timezone": timezone if timezone not in ("", "local") else None,
                "label": label,
                "iso_time": now.isoformat(),
                "utc_offset": offset,
            },
        ),
    )


def format_price(value: float) -> str:
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.4g}"


def build_weather_tool(weather: WeatherProvider) -> Tool:
    def get_weather(city: str) -> ToolOutput:
        report = weather.current(city)
        if report is None:
            return ToolOutput(text=f"No weather data found for '{city}'.")
        return ToolOutput(
            text=(
                f"Weather in {report.city}, {report.country}: {report.condition}, "
                f"{report.temperature_c:g}°C (feels like {report.feels_like_c:g}°C), "
                f"humidity {report.humidity}%, wind {report.wind_kmh:g} km/h, "
                f"today {report.low_c:g} to {report.high_c:g}°C."
            ),
            widget=Widget(kind="weather", data=asdict(report)),
        )

    return Tool(
        name="get_weather",
        description="Get the current weather conditions for a city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. Tehran or Berlin",
                }
            },
            "required": ["city"],
        },
        run=get_weather,
    )


def build_crypto_tool(market_data: MarketDataProvider) -> Tool:
    def crypto_price(coin: str) -> ToolOutput:
        coin_id = coin.strip().lower().replace(" ", "-")
        history = market_data.day_history(coin_id)
        if history is None:
            return ToolOutput(
                text=(
                    f"No price data found for '{coin}'. "
                    "Pass a CoinGecko id like bitcoin or ethereum."
                )
            )
        prices = [point.price for point in history.points]
        current, opening = prices[-1], prices[0]
        change_pct = (current - opening) / opening * 100
        return ToolOutput(
            text=(
                f"{coin_id} price: ${format_price(current)} now, "
                f"{change_pct:+.2f}% over the last 24 hours, "
                f"high ${format_price(max(prices))}, low ${format_price(min(prices))}."
            ),
            widget=Widget(
                kind="price_chart",
                data={
                    "coin": history.coin,
                    "currency": history.currency,
                    "current": current,
                    "change_pct": round(change_pct, 2),
                    "high": max(prices),
                    "low": min(prices),
                    "points": [
                        {"t": point.timestamp_ms, "p": point.price}
                        for point in history.points
                    ],
                },
            ),
        )

    return Tool(
        name="crypto_price",
        description=(
            "Get the current price and last 24 hours of price history "
            "for a cryptocurrency."
        ),
        parameters={
            "type": "object",
            "properties": {
                "coin": {
                    "type": "string",
                    "description": "CoinGecko coin id, e.g. bitcoin or ethereum",
                }
            },
            "required": ["coin"],
        },
        run=crypto_price,
    )


def save_generated_image(image: GeneratedImage) -> str:
    filename = f"{uuid4().hex}.{image.extension}"
    directory = Path(settings.image_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(image.data)
    return filename


def build_image_tool(image_generator: ImageGenerator) -> Tool:
    def generate_image(prompt: str) -> ToolOutput:
        image = image_generator.generate(prompt)
        filename = save_generated_image(image)
        return ToolOutput(
            text=f"Generated the image and showed it to the user: {prompt}",
            widget=Widget(
                kind="image",
                data={
                    "filename": filename,
                    "prompt": prompt,
                    "width": image.width,
                    "height": image.height,
                },
            ),
        )

    return Tool(
        name="generate_image",
        description=(
            "Generate an image from a text description and show it to the "
            "user. Use it for pictures, photos, artwork, and illustrations — "
            "never for diagrams or charts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "A detailed English description of the image to "
                        "generate, e.g. subject, setting, style, lighting"
                    ),
                }
            },
            "required": ["prompt"],
        },
        run=generate_image,
    )


@dataclass
class SourceChunk:
    filename: str
    content: str
    url: str | None = None


SEARCH_PARAMETERS = {
    "type": "object",
    "properties": {"query": {"type": "string", "description": "The search query"}},
    "required": ["query"],
}

DOCUMENT_SEARCH_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search the user's indexed documents and return the most relevant passages.",
        "parameters": SEARCH_PARAMETERS,
    },
}

WEB_SEARCH_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the public web for current or general information that is not in the user's documents.",
        "parameters": SEARCH_PARAMETERS,
    },
}


def build_document_search(
    session: Session,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
):
    def search_documents(query: str) -> list[SourceChunk]:
        chunks = retrieve_chunks(
            session,
            query,
            settings.top_k,
            embeddings,
            vector_store,
            reranker=reranker,
            min_score=settings.agent_min_relevance,
        )
        return [
            SourceChunk(filename=chunk.document.filename, content=chunk.content)
            for chunk in chunks
        ]

    return search_documents


def build_web_search(web_search: WebSearchProvider):
    def search_web(query: str) -> list[SourceChunk]:
        try:
            results = web_search.search(query)
        except Exception:
            return []
        return [
            SourceChunk(
                filename=result.title, content=result.snippet, url=result.url
            )
            for result in results
        ]

    return search_web


def build_kb_stats_tool(session: Session) -> Tool:
    def kb_stats() -> ToolOutput:
        counts = {
            "documents": session.scalar(select(func.count(Document.id))),
            "chunks": session.scalar(select(func.count(Chunk.id))),
            "collections": session.scalar(select(func.count(Collection.id))),
            "conversations": session.scalar(select(func.count(Conversation.id))),
        }
        return ToolOutput(
            text=(
                f"Knowledge base: {counts['documents']} documents, "
                f"{counts['chunks']} chunks, {counts['collections']} collections, "
                f"{counts['conversations']} conversations."
            ),
            widget=Widget(kind="kb_stats", data=counts),
        )

    return Tool(
        name="kb_stats",
        description=(
            "Get the size of the user's knowledge base: how many documents, "
            "chunks, collections, and conversations it holds."
        ),
        parameters={"type": "object", "properties": {}},
        run=kb_stats,
    )


USAGE_WINDOW_DAYS = 7


def build_usage_stats_tool(session: Session) -> Tool:
    def usage_stats() -> ToolOutput:
        start = date.today() - timedelta(days=USAGE_WINDOW_DAYS - 1)
        day = func.date(PromptLog.created_at)
        rows = session.execute(
            select(
                day,
                func.count(PromptLog.id),
                func.coalesce(
                    func.sum(
                        func.coalesce(PromptLog.prompt_tokens, 0)
                        + func.coalesce(PromptLog.response_tokens, 0)
                    ),
                    0,
                ),
            )
            .where(day >= start)
            .group_by(day)
        ).all()
        by_day = {row[0]: row for row in rows}
        days = []
        for offset in range(USAGE_WINDOW_DAYS):
            current = start + timedelta(days=offset)
            row = by_day.get(current)
            days.append(
                {
                    "date": current.isoformat(),
                    "prompts": row[1] if row else 0,
                    "tokens": int(row[2]) if row else 0,
                }
            )
        total_prompts = sum(entry["prompts"] for entry in days)
        total_tokens = sum(entry["tokens"] for entry in days)
        average_latency = session.scalar(
            select(func.avg(PromptLog.latency_ms)).where(day >= start)
        )
        average_latency_ms = int(average_latency) if average_latency else None
        summary = (
            f"Cortex usage over the last {USAGE_WINDOW_DAYS} days: "
            f"{total_prompts} prompts, {total_tokens:,} tokens"
        )
        if average_latency_ms is not None:
            summary += f", average latency {average_latency_ms:,} ms"
        return ToolOutput(
            text=summary + ".",
            widget=Widget(
                kind="usage",
                data={
                    "days": days,
                    "total_prompts": total_prompts,
                    "total_tokens": total_tokens,
                    "average_latency_ms": average_latency_ms,
                },
            ),
        )

    return Tool(
        name="usage_stats",
        description=(
            "Get how much the user has used Cortex over the last week: "
            "prompts, tokens, and average latency."
        ),
        parameters={"type": "object", "properties": {}},
        run=usage_stats,
    )


def build_tools(
    session: Session,
    weather: WeatherProvider,
    market_data: MarketDataProvider,
    image_generator: ImageGenerator,
) -> list[Tool]:
    return [
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
            name="world_clock",
            description=(
                "Get the current date and time in a timezone. "
                "Defaults to the user's timezone when none is given."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name, e.g. Asia/Tehran or Europe/Berlin",
                    }
                },
            },
            run=world_clock,
        ),
        build_weather_tool(weather),
        build_crypto_tool(market_data),
        build_kb_stats_tool(session),
        build_usage_stats_tool(session),
        build_image_tool(image_generator),
    ]
