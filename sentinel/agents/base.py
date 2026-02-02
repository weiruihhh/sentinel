"""
Base agent class for Sentinel system.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from sentinel.llm.base import LLMClient
from sentinel.tools.registry import ToolRegistry

# Type variables for input/output schemas
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for all agents.

    All agents must:
    1. Define input/output schemas (Pydantic models)
    2. Implement run() method
    3. Use structured I/O (no raw strings)
    """

    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
    ):
        """
        Initialize base agent.

        Args:
            name: Agent name/identifier
            llm_client: LLM client for generation
            tool_registry: Tool registry for tool calls
        """
        self.name = name
        self.llm_client = llm_client
        self.tool_registry = tool_registry

    @abstractmethod
    def run(self, input_data: InputT) -> OutputT:
        """
        Run agent with structured input/output.

        Args:
            input_data: Structured input (Pydantic model)

        Returns:
            Structured output (Pydantic model)

        Raises:
            Exception: If execution fails
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
