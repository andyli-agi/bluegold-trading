from __future__ import annotations

from abc import ABC, abstractmethod

from bluegold_trading.core.models import TargetAllocations


class AllocationSource(ABC):
    """Interface for fetching target portfolio allocations."""

    @abstractmethod
    async def get_target_allocations(self) -> TargetAllocations:
        """Return the latest target allocations."""
        ...
