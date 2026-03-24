from abc import ABC, abstractmethod
from typing import Type

import asyncpg

from src.models.events import BaseEvent

class BaseProjector(ABC):
    """
    Abstract base class for a projector.

    Each projector is responsible for handling a specific set of events
    and updating a corresponding read model (a database table).
    """
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    @property
    @abstractmethod
    def event_types(self) -> list[Type[BaseEvent]]:
        """
        Returns a list of event types that this projector is interested in.
        """
        pass

    @abstractmethod
    async def handle(self, event: BaseEvent) -> None:
        """
        Processes a single event and updates the read model.
        This method must be idempotent.
        """
        pass

