from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bluegold_trading.config import TriggerConfig
from bluegold_trading.core.engine import TradingEngine
from bluegold_trading.triggers.base import Trigger

logger = structlog.get_logger()


class ScheduledTrigger(Trigger):
    """Fires a rebalance at a fixed daily time using APScheduler."""

    def __init__(self, config: TriggerConfig, engine: TradingEngine) -> None:
        self._engine = engine
        self._config = config
        self._scheduler = AsyncIOScheduler()

        parts = config.time.split(":")
        hour, minute = int(parts[0]), int(parts[1])
        tz = ZoneInfo(config.timezone)

        self._scheduler.add_job(
            self._run_rebalance,
            CronTrigger(hour=hour, minute=minute, timezone=tz),
            id="rebalance",
            name="Daily rebalance",
        )

    async def _run_rebalance(self) -> None:
        logger.info("scheduled trigger fired", time=datetime.now().isoformat())
        result = await self._engine.rebalance()
        if result.error:
            logger.error("scheduled rebalance failed", error=result.error)
        else:
            logger.info(
                "scheduled rebalance complete",
                orders=len(result.orders_planned),
                executed=len(result.orders_executed),
            )

    async def start(self) -> None:
        logger.info(
            "starting scheduled trigger",
            time=self._config.time,
            timezone=self._config.timezone,
        )
        self._scheduler.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("scheduled trigger stopped")
