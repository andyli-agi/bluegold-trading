from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"


@dataclass(frozen=True)
class Account:
    portfolio_value: float
    cash: float
    buying_power: float


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    market_value: float
    current_price: float
    avg_entry_price: float


@dataclass(frozen=True)
class Order:
    symbol: str
    side: OrderSide
    notional: float | None = None
    qty: float | None = None
    order_type: OrderType = OrderType.MARKET

    @property
    def display_value(self) -> float:
        return self.notional if self.notional is not None else (self.qty or 0.0)


@dataclass(frozen=True)
class OrderResult:
    symbol: str
    side: OrderSide
    filled_qty: float | None = None
    filled_avg_price: float | None = None
    status: str = "pending"
    broker_order_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class TargetAllocations:
    """The target portfolio weights returned by an allocation source."""

    allocations: dict[str, float]
    strategy: str = ""
    evaluation_date: str = ""
    evaluation_time: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def total_weight(self) -> float:
        return sum(self.allocations.values())


@dataclass
class RebalanceResult:
    target: TargetAllocations
    orders_planned: list[Order]
    orders_executed: list[OrderResult]
    skipped_symbols: list[str]
    dry_run: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error: str | None = None
