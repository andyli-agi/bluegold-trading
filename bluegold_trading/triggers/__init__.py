from __future__ import annotations

from bluegold_trading.config import TriggerConfig
from bluegold_trading.core.engine import TradingEngine
from bluegold_trading.triggers.base import Trigger


def create_trigger(config: TriggerConfig, engine: TradingEngine) -> Trigger:
    if config.type == "scheduled":
        from bluegold_trading.triggers.scheduled import ScheduledTrigger

        return ScheduledTrigger(config, engine)

    raise ValueError(f"Unsupported trigger type: {config.type!r}")
