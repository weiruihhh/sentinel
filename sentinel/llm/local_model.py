"""
进程内加载 LoRA 微调模型并直接推理，不依赖外部 API 服务。
"""

import json
from pathlib import Path
from typing import Optional

from sentinel.llm.base import LLMClient
from sentinel.types import LLMMessage, LLMResponse


def _get_base_model_path(adapter_path: str) -> Optional[str]:
    p = Path(adapter_path) / "adapter_config.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("base_model_name_or_path")


class LocalModelLLM(LLMClient):
    """从本地 LoRA 目录加载模型并在进程内推理。"""

    def __init__(
        self,
        adapter_path: str,
        base_model_path: Optional[str] = None,
        model: str = "local",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self._adapter_path = str(Path(adapter_path).expanduser().resolve())
        self._base_model_path = base_model_path or _get_base_model_path(self._adapter_path)
        if not self._base_model_path:
            raise ValueError("base_model_path 未指定且 adapter 目录下无 adapter_config.json")
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        if self._model is not None:
            return
        #惰性加载，只在第一次调用generate时加载模型
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel
        except ImportError as e:
            raise ImportError(
                "本地模型需要: pip install torch transformers peft"
            ) from e
        tok_path = self._adapter_path if (Path(self._adapter_path) / "tokenizer.json").exists() else self._base_model_path
        self._tokenizer = AutoTokenizer.from_pretrained(tok_path, trust_remote_code=True)
        base = AutoModelForCausalLM.from_pretrained(
            self._base_model_path,
            trust_remote_code=True,
            device_map="auto",
        )
        self._model = PeftModel.from_pretrained(base, self._adapter_path)
        self._model.eval() #设置模型为评估模式

    def generate(
        self,
        messages: list[LLMMessage],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        self._load_model()
        if system_prompt:
            msgs = [{"role": "system", "content": system_prompt}]
        else:
            msgs = []
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})

        # Log prompt (optional, for debugging)
        import os
        if os.environ.get("SENTINEL_DEBUG_LLM") == "1":
            print("\n" + "="*80)
            print("🤖 LLM PROMPT")
            print("="*80)
            if system_prompt:
                print(f"System: {system_prompt[:200]}...")
            for msg in messages:
                print(f"{msg.role}: {msg.content[:500]}...")
            print("="*80 + "\n")

        text = self._tokenizer.apply_chat_template(
            msgs,
            tokenize=False,
            add_generation_prompt=True,
        )
        #这里一大串操作的目的就是为了获取新生成的文本。
        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)
        max_new = kwargs.get("max_tokens", self.max_tokens)
        out = self._model.generate(
            **inputs,
            max_new_tokens=max_new,
            temperature=kwargs.get("temperature", self.temperature),
            do_sample=max(kwargs.get("temperature", self.temperature), 1e-6) > 1e-6,
            pad_token_id=self._tokenizer.pad_token_id or self._tokenizer.eos_token_id,
        )
        gen = out[:, inputs["input_ids"].shape[1] :][0]
        content = self._tokenizer.decode(gen, skip_special_tokens=True).strip()
        tokens_used = out.shape[1] - inputs["input_ids"].shape[1]

        # Log response (optional, for debugging)
        if os.environ.get("SENTINEL_DEBUG_LLM") == "1":
            print("\n" + "="*80)
            print("🤖 LLM RESPONSE")
            print("="*80)
            print(content)
            print(f"\nTokens used: {tokens_used}")
            print("="*80 + "\n")

        return LLMResponse(
            content=content,
            tokens_used=int(tokens_used),
            metadata={"model": self.model, "adapter_path": self._adapter_path},
        )
