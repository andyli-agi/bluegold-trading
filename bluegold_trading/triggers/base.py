from __future__ import annotations

from abc import ABC, abstractmethod


class Trigger(ABC):
    """Interface for event sources that fire rebalance runs."""

    @abstractmethod
    async def start(self) -> None:
        """Begin the trigger loop (blocks until stopped or interrupted)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shut down the trigger."""
        ...
