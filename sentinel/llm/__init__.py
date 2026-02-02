"""
LLM client abstraction layer.
"""

import os

from sentinel.config import LLMConfig
from sentinel.llm.base import LLMClient
from sentinel.llm.local_model import LocalModelLLM
from sentinel.llm.mock import MockLLM
from sentinel.llm.openai_compat import OpenAICompatLLM

__all__ = ["LLMClient", "MockLLM", "OpenAICompatLLM", "LocalModelLLM", "get_llm_client"]

# 阿里云 DashScope 的 OpenAI 兼容 endpoint，用于通义千问 / Qwen 系列（含 Qwen3）
DASHSCOPE_OPENAI_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# 硅基流动 SiliconFlow 的 OpenAI 兼容 endpoint
SILICONFLOW_OPENAI_BASE = "https://api.siliconflow.com/v1"


def get_llm_client(llm_config: LLMConfig) -> LLMClient:
    """
    按 config 构建 LLM 客户端。

    仅支持以下 provider，其他会直接报错：
    - provider "mock" -> MockLLM，虚拟数据，仅用于测试，无需额外依赖。
    - provider "qwen" -> OpenAICompatLLM，默认走 DashScope；api_key 可用 DASHSCOPE_API_KEY。
    - provider "siliconflow" -> 硅基流动，默认 base 为 api.siliconflow.com，api_key 用 SILICONFLOW_API_KEY。
    - provider "local_model" -> 本地 LoRA 进程内加载，adapter_path / SENTINEL_ADAPTER_PATH 必填。
    """
    if llm_config.provider == "mock":
        return MockLLM(
            model=llm_config.model or "mock-llm-v1",
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            deterministic=False,
        )
    if llm_config.provider == "qwen":
        api_key = llm_config.api_key or os.environ.get("DASHSCOPE_API_KEY") or None
        api_base = llm_config.api_base or os.environ.get("DASHSCOPE_API_BASE") or DASHSCOPE_OPENAI_BASE
        return OpenAICompatLLM(
            model=llm_config.model or "qwen-plus",
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            api_key=api_key,
            api_base=api_base,
        )
    if llm_config.provider == "siliconflow":
        api_key = llm_config.api_key or os.environ.get("SILICONFLOW_API_KEY") or None
        api_base = llm_config.api_base or os.environ.get("SILICONFLOW_API_BASE") or SILICONFLOW_OPENAI_BASE
        return OpenAICompatLLM(
            model=llm_config.model or "Qwen/Qwen2.5-7B-Instruct",
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            api_key=api_key,
            api_base=api_base,
        )
    if llm_config.provider == "local_model":
        adapter = llm_config.adapter_path or os.environ.get("SENTINEL_ADAPTER_PATH", "")
        base = llm_config.base_model_path or os.environ.get("SENTINEL_BASE_MODEL_PATH") or None
        if not adapter:
            raise ValueError("provider=local_model 需设置 adapter_path 或 SENTINEL_ADAPTER_PATH")
        return LocalModelLLM(
            adapter_path=adapter,
            base_model_path=base or None,
            model=llm_config.model or "local",
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
        )

    raise ValueError(
        f"不支持的 provider: {llm_config.provider!r}。"
        " 仅支持: mock, qwen, siliconflow, local_model"
    )
