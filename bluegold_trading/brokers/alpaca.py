from __future__ import annotations

import asyncio
from functools import partial
from typing import Iterable, cast

import structlog
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from bluegold_trading.brokers.base import Broker
from bluegold_trading.config import BrokerConfig
from bluegold_trading.core.models import (
    Account,
    Order,
    OrderResult,
    OrderSide,
    Position,
)

logger = structlog.get_logger()


def _to_float(value: object | None, default: float = 0.0) -> float:
    if value is None:
        return default
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class AlpacaBroker(Broker):
    """Alpaca brokerage adapter using the alpaca-py SDK.

    The alpaca-py TradingClient is synchronous, so we wrap calls with
    asyncio.to_thread to keep the event loop responsive.
    """

    def __init__(self, config: BrokerConfig) -> None:
        self._client = TradingClient(
            api_key=config.api_key,
            secret_key=config.api_secret,
            paper=config.paper,
        )

    async def get_account(self) -> Account:
        acct = await asyncio.to_thread(self._client.get_account)
        return Account(
            portfolio_value=_to_float(getattr(acct, "portfolio_value", None)),
            cash=_to_float(getattr(acct, "cash", None)),
            buying_power=_to_float(getattr(acct, "buying_power", None)),
        )

    async def get_positions(self) -> list[Position]:
        raw_positions = cast(
            Iterable[object],
            await asyncio.to_thread(self._client.get_all_positions),
        )
        positions: list[Position] = []
        for raw in raw_positions:
            symbol = str(getattr(raw, "symbol", "")).strip()
            if not symbol:
                continue
            positions.append(
                Position(
                    symbol=symbol,
                    qty=_to_float(getattr(raw, "qty", None)),
                    market_value=_to_float(getattr(raw, "market_value", None)),
                    current_price=_to_float(getattr(raw, "current_price", None)),
                    avg_entry_price=_to_float(getattr(raw, "avg_entry_price", None)),
                )
            )
        return positions

    async def submit_order(self, order: Order) -> OrderResult:
        side = (
            AlpacaOrderSide.BUY if order.side == OrderSide.BUY else AlpacaOrderSide.SELL
        )

        req_kwargs: dict = {
            "symbol": order.symbol,
            "side": side,
            "time_in_force": TimeInForce.DAY,
            "type": "market",
        }

        if order.notional is not None:
            req_kwargs["notional"] = round(order.notional, 2)
        elif order.qty is not None:
            req_kwargs["qty"] = order.qty
        else:
            return OrderResult(
                symbol=order.symbol,
                side=order.side,
                status="rejected",
                error="Order must have notional or qty",
            )

        request = MarketOrderRequest(**req_kwargs)

        try:
            result = await asyncio.to_thread(self._client.submit_order, request)
            order_id = getattr(result, "id", None)
            status = getattr(result, "status", "submitted")
            logger.info(
                "order submitted",
                symbol=order.symbol,
                side=order.side.value,
                order_id=str(order_id),
            )
            return OrderResult(
                symbol=order.symbol,
                side=order.side,
                status=str(status),
                broker_order_id=str(order_id) if order_id is not None else None,
            )
        except Exception as exc:
            logger.error("order failed", symbol=order.symbol, error=str(exc))
            return OrderResult(
                symbol=order.symbol,
                side=order.side,
                status="error",
                error=str(exc),
            )

    async def close_position(self, symbol: str) -> OrderResult:
        try:
            result = await asyncio.to_thread(
                partial(self._client.close_position, symbol)
            )
            order_id = getattr(result, "id", None)
            return OrderResult(
                symbol=symbol,
                side=OrderSide.SELL,
                status="closed",
                broker_order_id=str(order_id) if order_id is not None else None,
            )
        except Exception as exc:
            logger.error("close position failed", symbol=symbol, error=str(exc))
            return OrderResult(
                symbol=symbol,
                side=OrderSide.SELL,
                status="error",
                error=str(exc),
            )
