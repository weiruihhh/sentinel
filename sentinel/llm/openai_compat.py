"""
OpenAI 兼容协议的 LLM 客户端（通用，不限于 OpenAI 一家）。

使用 Python 包 openai 作为「协议客户端」：请求发往谁由 base_url 决定，例如：
- OpenAI / Azure：base_url 指向其 API
- 硅基流动、DashScope、本地 LLaMA-Factory / vLLM / Ollama 等：base_url 指向对应服务即可
"""

import os
from typing import Optional

from sentinel.llm.base import LLMClient
from sentinel.types import LLMMessage, LLMResponse


def _get_openai_client():
    """因为在mock的时候不需要openai，所以使用lazy惰性加载"""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "Using real LLM requires the 'openai' package. Install with: pip install openai"
        ) from e
    return OpenAI


class OpenAICompatLLM(LLMClient):
    """
    LLM client 
    设置api_base为你的endpoint（例如OpenAI，Azure，或者http://localhost:8000/v1 for vLLM/Ollama）。
    设置api_key通过init或者环境变量OPENAI_API_KEY（使用一个占位符like 'sk-local'用于本地）。
    """

    def __init__(
        self,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._api_base = (api_base or os.environ.get("OPENAI_API_BASE", "")).rstrip("/") or None
        self._client = None

    def _client_or_build(self):
        """
        如果client已经存在，直接返回；否则创建一个新的client。
        """
        if self._client is not None:
            return self._client
        # "OpenAI" 是 Python 包 openai 里的客户端类，用来请求任意「OpenAI 兼容」的 HTTP 接口。
        # 实际请求发到哪由 base_url 决定（硅基流动、DashScope、本地 LLaMA-Factory 等均可）。
        OpenAI = _get_openai_client()
        kw: dict = {}
        if self._api_base:
            kw["base_url"] = self._api_base
        if self._api_key:
            kw["api_key"] = self._api_key
        self._client = OpenAI(**kw)
        return self._client

    def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        msgs: list[dict] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})

        client = self._client_or_build()
        resp = client.chat.completions.create(
            model=self.model,
            messages=msgs,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        choice = resp.choices[0]
        content = (choice.message.content or "").strip()
        usage = getattr(resp, "usage", None)
        tokens_used = int(usage.total_tokens) if usage and hasattr(usage, "total_tokens") else 0
        return LLMResponse(
            content=content,
            tokens_used=tokens_used,
            metadata={
                "model": self.model,
                "finish_reason": getattr(choice, "finish_reason", None),
            },
        )
