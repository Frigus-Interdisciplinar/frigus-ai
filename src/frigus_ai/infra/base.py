from abc import ABC, abstractmethod

from frigus_ai.infra.logging import DebugLevel, Logging


class Connector[T](ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Logging.log_classe(level=DebugLevel.DEBUG)(cls)

    @abstractmethod
    def connect(self) -> T: ...
