#!/usr/bin/env python3
"""
测试本地 LoRA 模型能否在 Sentinel 框架下被正常调用。
用法（二选一）：
  1. source script/set_environment.sh  且已设 SENTINEL_LLM_PROVIDER=local_model、SENTINEL_ADAPTER_PATH
  2. SENTINEL_LLM_PROVIDER=local_model SENTINEL_ADAPTER_PATH=/path/to/adapter python script/test_local_llm.py
可选: SENTINEL_BASE_MODEL_PATH=... 若不设则从 adapter 的 adapter_config.json 读取。
"""
import os
import sys

# 确保能 import sentinel（从项目根执行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    provider = os.environ.get("SENTINEL_LLM_PROVIDER", "").strip().lower()
    adapter = os.environ.get("SENTINEL_ADAPTER_PATH", "").strip()
    if provider != "local_model" or not adapter:
        print("请设置: SENTINEL_LLM_PROVIDER=local_model 和 SENTINEL_ADAPTER_PATH=/path/to/your/adapter")
        print("示例: SENTINEL_LLM_PROVIDER=local_model SENTINEL_ADAPTER_PATH=/home/hzw/LLaMA-Factory/saves/Qwen3-4B-Base/lora/train_2026-01-17-11-40-08 python script/test_local_llm.py")
        sys.exit(1)

    from sentinel.config import get_config
    from sentinel.llm import get_llm_client
    from sentinel.types import LLMMessage

    cfg = get_config()
    cfg.llm.provider = "local_model"
    cfg.llm.adapter_path = adapter
    cfg.llm.base_model_path = os.environ.get("SENTINEL_BASE_MODEL_PATH", "").strip() or None

    print("正在加载本地模型（首次较慢）...")
    llm = get_llm_client(cfg.llm)
    print("模型已加载，发起一次 generate 测试...")

    messages = [LLMMessage(role="user", content="你好，请用一句话介绍你自己。")]
    resp = llm.generate(messages, system_prompt="你是一个助手。")
    print("回复内容:", resp.content)
    print("消耗 token 数:", resp.tokens_used)
    print("本地 LLM 调用正常。")

if __name__ == "__main__":
    main()
