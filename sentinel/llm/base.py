"""
Abstract base class for LLM clients.
"""

from abc import ABC, abstractmethod
from typing import Optional

from sentinel.types import LLMMessage, LLMResponse


class LLMClient(ABC):
    """
    Abstract LLM client interface.

    All LLM implementations (mock, OpenAI, Qwen, Claude, etc.) should inherit from this class.
    """

    def __init__(self, model: str = "default", temperature: float = 0.7, max_tokens: int = 2000):
        """
        Initialize LLM client.

        Args:
            model: Model name/identifier
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    #强制子类实现generate方法
    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate response from messages.

        Args:
            messages: List of messages (conversation history)
            system_prompt: Optional system prompt
            **kwargs: Additional provider-specific arguments

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            Exception: If generation fails
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model}, temperature={self.temperature})"
