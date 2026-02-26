from __future__ import annotations

import structlog

from bluegold_trading.brokers.base import Broker
from bluegold_trading.config import AppConfig
from bluegold_trading.core.models import (
    Order,
    OrderResult,
    OrderSide,
    RebalanceResult,
    TargetAllocations,
)
from bluegold_trading.signals.base import AllocationSource

logger = structlog.get_logger()


class TradingEngine:
    """Orchestrates the fetch-diff-execute rebalance pipeline."""

    def __init__(
        self,
        broker: Broker,
        allocation_source: AllocationSource,
        *,
        min_order_value: float = 1.0,
        max_position_drift: float = 0.02,
        dry_run: bool = True,
    ) -> None:
        self.broker = broker
        self.allocation_source = allocation_source
        self.min_order_value = min_order_value
        self.max_position_drift = max_position_drift
        self.dry_run = dry_run

    @classmethod
    def from_config(cls, cfg: AppConfig) -> TradingEngine:
        broker = _create_broker(cfg)
        source = _create_allocation_source(cfg)
        return cls(
            broker=broker,
            allocation_source=source,
            min_order_value=cfg.trading.min_order_value,
            max_position_drift=cfg.trading.max_position_drift,
            dry_run=cfg.trading.dry_run,
        )

    async def rebalance(self) -> RebalanceResult:
        try:
            target = await self.allocation_source.get_target_allocations()
            logger.info(
                "fetched target allocations",
                strategy=target.strategy,
                date=target.evaluation_date,
                num_symbols=len(target.allocations),
            )
        except Exception as exc:
            logger.error("failed to fetch allocations", error=str(exc))
            return RebalanceResult(
                target=TargetAllocations(allocations={}),
                orders_planned=[],
                orders_executed=[],
                skipped_symbols=[],
                dry_run=self.dry_run,
                error=f"Failed to fetch allocations: {exc}",
            )

        try:
            account = await self.broker.get_account()
            positions = await self.broker.get_positions()
        except Exception as exc:
            logger.error("failed to get broker state", error=str(exc))
            return RebalanceResult(
                target=target,
                orders_planned=[],
                orders_executed=[],
                skipped_symbols=[],
                dry_run=self.dry_run,
                error=f"Failed to get broker state: {exc}",
            )

        portfolio_value = account.portfolio_value
        if portfolio_value <= 0:
            return RebalanceResult(
                target=target,
                orders_planned=[],
                orders_executed=[],
                skipped_symbols=[],
                dry_run=self.dry_run,
                error="Portfolio value is zero or negative",
            )

        orders, skipped = self._compute_orders(target, positions, portfolio_value)

        logger.info(
            "orders computed",
            planned=len(orders),
            skipped=len(skipped),
            dry_run=self.dry_run,
        )

        executed: list[OrderResult] = []
        if not self.dry_run:
            executed = await self._execute_orders(orders)

        return RebalanceResult(
            target=target,
            orders_planned=orders,
            orders_executed=executed,
            skipped_symbols=skipped,
            dry_run=self.dry_run,
        )

    def _compute_orders(
        self,
        target: TargetAllocations,
        positions: list,
        portfolio_value: float,
    ) -> tuple[list[Order], list[str]]:
        pos_value: dict[str, float] = {p.symbol: p.market_value for p in positions}

        all_symbols = set(target.allocations.keys()) | set(pos_value.keys())

        sells: list[Order] = []
        buys: list[Order] = []
        skipped: list[str] = []

        for symbol in sorted(all_symbols):
            target_weight = target.allocations.get(symbol, 0.0)
            current_value = pos_value.get(symbol, 0.0)
            current_weight = current_value / portfolio_value

            drift = abs(current_weight - target_weight)
            if drift <= self.max_position_drift:
                skipped.append(symbol)
                continue

            target_value = target_weight * portfolio_value
            diff = target_value - current_value

            if abs(diff) < self.min_order_value:
                skipped.append(symbol)
                continue

            if diff < 0:
                sells.append(
                    Order(symbol=symbol, side=OrderSide.SELL, notional=abs(diff))
                )
            else:
                buys.append(Order(symbol=symbol, side=OrderSide.BUY, notional=diff))

        # Sell first, then buy — frees up cash for purchases
        return sells + buys, skipped

    async def _execute_orders(self, orders: list[Order]) -> list[OrderResult]:
        results: list[OrderResult] = []
        for order in orders:
            result = await self.broker.submit_order(order)
            results.append(result)
        return results


def _create_broker(cfg: AppConfig) -> Broker:
    if cfg.broker.type == "alpaca":
        from bluegold_trading.brokers.alpaca import AlpacaBroker

        return AlpacaBroker(cfg.broker)

    raise ValueError(f"Unsupported broker type: {cfg.broker.type!r}")


def _create_allocation_source(cfg: AppConfig) -> AllocationSource:
    from bluegold_trading.signals.bluegold_api import BlueGoldAPI

    return BlueGoldAPI(cfg.strategy)
