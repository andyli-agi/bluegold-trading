from __future__ import annotations

from abc import ABC, abstractmethod

from bluegold_trading.core.models import Account, Order, OrderResult, Position


class Broker(ABC):
    """Interface that every brokerage adapter must implement."""

    @abstractmethod
    async def get_account(self) -> Account: ...

    @abstractmethod
    async def get_positions(self) -> list[Position]: ...

    @abstractmethod
    async def submit_order(self, order: Order) -> OrderResult: ...

    @abstractmethod
    async def close_position(self, symbol: str) -> OrderResult: ...
