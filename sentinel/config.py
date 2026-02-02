"""
Centralized configuration for Sentinel system.
"""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM client configuration."""

    provider: Literal["mock", "openai", "qwen", "claude", "siliconflow", "local_model"] = Field(
        default="mock", description="LLM provider"
    )
    model: str = Field(default="gpt-4", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=2000, description="Max tokens per generation")
    timeout: int = Field(default=30, description="Request timeout in seconds")

    api_key: str = Field(default="", description="API key")
    api_base: str = Field(default="", description="API base URL")
    adapter_path: str = Field(default="", description="LoRA adapter path for provider=local_model")
    base_model_path: str = Field(default="", description="Base model path for provider=local_model, optional if adapter has adapter_config.json")


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    trace_enabled: bool = Field(default=True, description="Enable trace recording")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    output_dir: Path = Field(default=Path("./runs"), description="Output directory for traces")

    # Sampling
    trace_sample_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Trace sampling rate"
    )

    # Verbosity
    log_tool_inputs: bool = Field(default=True, description="Log tool inputs")
    log_tool_outputs: bool = Field(default=True, description="Log tool outputs")
    log_llm_prompts: bool = Field(default=True, description="Log LLM prompts")
    log_llm_responses: bool = Field(default=True, description="Log LLM responses")


class OrchestrationConfig(BaseModel):
    """Orchestration configuration."""

    max_retries: int = Field(default=3, description="Max retries for failed nodes")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries")

    # Approval
    auto_approve_read_only: bool = Field(
        default=True, description="Auto-approve read-only actions"
    )
    auto_approve_safe_write: bool = Field(
        default=False, description="Auto-approve safe write actions"
    )


class SentinelConfig(BaseModel):
    """Global Sentinel configuration."""

    # Sub-configs
    llm: LLMConfig = Field(default_factory=LLMConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)

    # System
    default_permission_level: str = Field(
        default="operator", description="Default permission level for tasks"
    )


# Global config instance (can be overridden)
DEFAULT_CONFIG = SentinelConfig()


def get_config() -> SentinelConfig:
    """Get global config instance. LLM fields are overridden by env if set:
    SENTINEL_LLM_PROVIDER, SENTINEL_LLM_MODEL, OPENAI_API_KEY, OPENAI_API_BASE.
    """
    cfg = DEFAULT_CONFIG.model_copy(deep=True)
    p = os.environ.get("SENTINEL_LLM_PROVIDER", "").strip().lower()
    if p in ("mock", "openai", "qwen", "claude", "siliconflow", "local_model"):
        cfg.llm.provider = p  # type: ignore[assignment]
    if os.environ.get("SENTINEL_LLM_MODEL"):
        cfg.llm.model = os.environ.get("SENTINEL_LLM_MODEL", "")
    if os.environ.get("OPENAI_API_KEY") is not None:
        cfg.llm.api_key = os.environ.get("OPENAI_API_KEY", "")
    if os.environ.get("OPENAI_API_BASE") is not None:
        cfg.llm.api_base = os.environ.get("OPENAI_API_BASE", "")
    if os.environ.get("SENTINEL_ADAPTER_PATH"):
        cfg.llm.adapter_path = os.environ.get("SENTINEL_ADAPTER_PATH", "")
    if os.environ.get("SENTINEL_BASE_MODEL_PATH"):
        cfg.llm.base_model_path = os.environ.get("SENTINEL_BASE_MODEL_PATH", "")
    return cfg
