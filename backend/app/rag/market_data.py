from dataclasses import dataclass
from typing import Protocol

import httpx

MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
REQUEST_TIMEOUT_SECONDS = 15
MAX_CHART_POINTS = 72


@dataclass
class PricePoint:
    timestamp_ms: int
    price: float


@dataclass
class PriceHistory:
    coin: str
    currency: str
    points: list[PricePoint]


class MarketDataProvider(Protocol):
    def day_history(self, coin: str) -> PriceHistory | None: ...


class CoinGeckoMarketData:
    def day_history(self, coin: str) -> PriceHistory | None:
        response = httpx.get(
            MARKET_CHART_URL.format(coin=coin),
            params={"vs_currency": "usd", "days": 1},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        prices = response.json().get("prices") or []
        if not prices:
            return None
        return PriceHistory(
            coin=coin,
            currency="usd",
            points=[
                PricePoint(timestamp_ms=int(timestamp), price=price)
                for timestamp, price in thin(prices)
            ],
        )


def thin(prices: list) -> list:
    if len(prices) <= MAX_CHART_POINTS:
        return prices
    step = (len(prices) - 1) / (MAX_CHART_POINTS - 1)
    return [prices[round(index * step)] for index in range(MAX_CHART_POINTS)]
