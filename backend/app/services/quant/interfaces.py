"""
Future-facing interfaces for agents, trading, streaming, and ML.

Implementations can be swapped without changing API contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class ResearchAgent(Protocol):
    async def run(self, ticker: str, context: dict[str, Any]) -> dict[str, Any]: ...


class MarketDataProvider(ABC):
    @abstractmethod
    async def ohlcv(self, ticker: str, days: int) -> list[dict[str, Any]]:
        raise NotImplementedError


class BrokerGateway(ABC):
    """Placeholder for IBKR / FIX / crypto connectors."""

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError


class StreamBus(ABC):
    """Placeholder for Kafka / NATS ingestion."""

    @abstractmethod
    async def publish(self, topic: str, payload: bytes) -> None:
        raise NotImplementedError


class FeatureStore(ABC):
    @abstractmethod
    async def write_features(self, entity_id: str, features: dict[str, float]) -> None:
        raise NotImplementedError


class ModelServer(ABC):
    @abstractmethod
    async def infer(self, model_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class StrategyEngine(ABC):
    @abstractmethod
    def evaluate(self, state: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
