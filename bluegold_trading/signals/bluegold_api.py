from __future__ import annotations

from typing import Any

import httpx
import structlog

from bluegold_trading.config import StrategyConfig
from bluegold_trading.core.models import TargetAllocations
from bluegold_trading.signals.base import AllocationSource

logger = structlog.get_logger()


class BlueGoldAPI(AllocationSource):
    """Fetches target allocations from the BlueGold live strategy API."""

    def __init__(self, config: StrategyConfig) -> None:
        self._config = config

    async def get_target_allocations(self) -> TargetAllocations:
        params: dict[str, str] = {}
        if self._config.api_access_key:
            params["api-access-key"] = self._config.api_access_key

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self._config.api_url, params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> TargetAllocations:
        results: list[dict[str, Any]] = data.get("results", [])

        if results:
            latest = results[-1]
            live_alloc = latest.get("live_allocation", {})
            return TargetAllocations(
                allocations=live_alloc.get("allocations", {}),
                strategy=live_alloc.get("strategy", data.get("strategy", "")),
                evaluation_date=latest.get("date", ""),
                evaluation_time=live_alloc.get("evaluation_time_et", ""),
                raw=data,
            )

        # Single-date response (when result_date query param is used)
        live_alloc = data.get("live_allocation", {})
        if live_alloc:
            return TargetAllocations(
                allocations=live_alloc.get("allocations", {}),
                strategy=live_alloc.get("strategy", data.get("strategy", "")),
                evaluation_date=data.get("date", ""),
                evaluation_time=live_alloc.get("evaluation_time_et", ""),
                raw=data,
            )

        raise ValueError(
            "Unexpected API response: no 'results' or 'live_allocation' found. "
            f"Keys present: {list(data.keys())}"
        )
