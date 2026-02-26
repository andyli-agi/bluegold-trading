from __future__ import annotations

import asyncio

import structlog

from bluegold_trading.config import TriggerConfig
from bluegold_trading.core.engine import TradingEngine
from bluegold_trading.triggers.base import Trigger

logger = structlog.get_logger()


class PollingTrigger(Trigger):
    """Polls the allocation source and fires when a new date appears."""

    def __init__(self, config: TriggerConfig, engine: TradingEngine) -> None:
        self._engine = engine
        self._interval = config.poll_interval_seconds
        self._last_date: str | None = None
        self._running = False

    async def start(self) -> None:
        logger.info("starting polling trigger", interval_s=self._interval)
        self._running = True

        while self._running:
            try:
                target = await self._engine.allocation_source.get_target_allocations()
                current_date = target.evaluation_date

                if current_date and current_date != self._last_date:
                    logger.info(
                        "new allocation detected",
                        date=current_date,
                        previous=self._last_date,
                    )
                    self._last_date = current_date
                    result = await self._engine.rebalance()
                    if result.error:
                        logger.error("polling rebalance failed", error=result.error)
                    else:
                        logger.info(
                            "polling rebalance complete",
                            orders=len(result.orders_planned),
                            executed=len(result.orders_executed),
                        )
                else:
                    logger.debug("no new allocation", date=current_date)

            except Exception as exc:
                logger.error("polling error", error=str(exc))

            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("polling trigger stopped")
