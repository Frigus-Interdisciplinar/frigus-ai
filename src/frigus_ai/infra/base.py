from abc import ABC, abstractmethod
from typing import Any

from frigus_ai.logging import DebugLevel, Logging


class Connector[T](ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Logging.log_classe(level=DebugLevel.DEBUG)(cls)

    @abstractmethod
    def connect(self) -> T: ...


class Repository(ABC):
    """Base marker for repositories that own an infrastructure connector."""

    connector: Any
