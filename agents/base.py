from abc import ABC, abstractmethod
from enum import Enum


class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    HEAVY = "heavy"


class BaseAgent(ABC):
    name: str = "base"
    complexity: Complexity = Complexity.MEDIUM

    @abstractmethod
    def process(self, message: str) -> str:
        """Process a user message and return a response string."""
        ...
