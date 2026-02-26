from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class StrategyConfig(BaseModel):
    name: str = "galaxy"
    api_url: str = "http://localhost:3000/api/strategies/galaxy/live"
    api_access_key: str = ""


class BrokerConfig(BaseModel):
    type: Literal["alpaca"] = "alpaca"
    api_key: str = ""
    api_secret: str = ""
    paper: bool = True


class TriggerConfig(BaseModel):
    type: Literal["scheduled"] = "scheduled"
    time: str = "16:05"
    timezone: str = "America/New_York"


class TradingConfig(BaseModel):
    min_order_value: float = Field(default=1.0, ge=0)
    max_position_drift: float = Field(default=0.02, ge=0, le=1.0)
    dry_run: bool = True


class AppConfig(BaseModel):
    strategy: StrategyConfig = StrategyConfig()
    broker: BrokerConfig = BrokerConfig()
    trigger: TriggerConfig = TriggerConfig()
    trading: TradingConfig = TradingConfig()


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig(**raw)
