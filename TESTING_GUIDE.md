# Sentinel 测试指南

本文档帮助你在本地测试 Sentinel 的各种 LLM Provider 和功能。

---

## 📋 前置准备

### 1. 激活虚拟环境

```bash
cd /home/hzw/sentinel
source .venv/bin/activate
```

### 2. 安装依赖

```bash
# 核心依赖（已安装）
pip install pydantic python-dateutil

# API 依赖（测试真实 LLM 时需要）
pip install openai

# Web UI 依赖（已安装）
pip install streamlit plotly pandas streamlit-lottie

# 本地模型依赖（测试 local_model 时需要）
pip install torch transformers peft accelerate
```

---

## 🧪 测试 1: Mock LLM（无需 API Key）

Mock LLM 使用规则和模板生成响应，无需真实 LLM，适合快速测试。

### 运行测试

```bash
# 默认使用 Mock LLM
python main.py

# 或显式指定
export SENTINEL_LLM_PROVIDER=mock
python main.py
```

### 预期结果

- 在 `runs/YYYYMMDD_HHMMSS/` 生成 3 个文件：
  - `trace.jsonl` - 全链路追踪
  - `episode.json` - 完整 episode
  - `report.json` - 诊断报告
- 终端输出显示 8 个阶段的执行过程
- 整个流程约 5-10 秒完成

### 验证

```bash
# 查看最新的运行结果
ls -lt runs/ | head -5

# 查看报告
cat runs/$(ls -t runs/ | head -1)/report.json | python -m json.tool
```

---

## 🧪 测试 2: 通义千问 API（Qwen）

### 获取 API Key

1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 登录并创建 API Key
3. 复制 API Key（格式：`sk-xxx`）

### 运行测试

```bash
# 设置环境变量
export SENTINEL_LLM_PROVIDER=qwen
export SENTINEL_LLM_MODEL=qwen-plus  # 或 qwen-turbo, qwen-max
export DASHSCOPE_API_KEY=sk-your-api-key-here

# 运行
python main.py
```

### 预期结果

- 终端显示 "LLM Provider: qwen"
- 每个 Agent 调用真实 LLM 生成响应
- 整个流程约 30-60 秒（取决于网络和模型）
- 生成的报告质量更高（相比 Mock）

### 常见问题

**Q: 报错 "ModuleNotFoundError: No module named 'openai'"**
```bash
pip install openai
```

**Q: 报错 "Invalid API key"**
- 检查 API Key 是否正确
- 确认 API Key 有余额

**Q: 报错 "Connection timeout"**
- 检查网络连接
- 尝试设置代理（如需要）

---

## 🧪 测试 3: 硅基流动 API（SiliconFlow）

### 获取 API Key

1. 访问 [硅基流动](https://siliconflow.cn/)
2. 注册并创建 API Key
3. 复制 API Key

### 运行测试

```bash
# 设置环境变量
export SENTINEL_LLM_PROVIDER=siliconflow
export SENTINEL_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct  # 或其他模型
export SILICONFLOW_API_KEY=sk-your-api-key-here

# 运行
python main.py
```

### 可用模型

- `Qwen/Qwen2.5-7B-Instruct`
- `Qwen/Qwen2.5-14B-Instruct`
- `deepseek-ai/DeepSeek-R1`
- 更多模型见 [硅基流动文档](https://docs.siliconflow.cn/)

---

## 🧪 测试 4: ModelScope API（新增）

### 获取 API Key

1. 访问 [ModelScope](https://modelscope.cn/)
2. 登录并进入个人中心
3. 创建 API Key
4. 复制 API Key

### 运行测试

```bash
# 设置环境变量
export SENTINEL_LLM_PROVIDER=modelscope
export SENTINEL_LLM_MODEL=Qwen/Qwen3-Coder-480B-A35B-Instruct  # 注意：ModelScope 的模型名格式
export MODELSCOPE_API_KEY=ms-c6e4a7b5-f044-4bdf-9620-21ba17cbf092

# 运行
python main.py
```

### 可用模型

- `qwen/Qwen2.5-7B-Instruct`
- `qwen/Qwen2.5-14B-Instruct`
- `qwen/Qwen2-72B-Instruct`
- 更多模型见 [ModelScope 模型库](https://modelscope.cn/models)

### 注意事项

- ModelScope API 使用 OpenAI 兼容协议
- 模型名格式：`namespace/model-name`（如 `qwen/Qwen2.5-7B-Instruct`）
- 默认 endpoint: `https://api-inference.modelscope.cn/v1`

---

## 🧪 测试 5: 本地模型（LoRA）

### 前置条件

1. 已使用 LLaMA-Factory 训练好 LoRA adapter
2. Adapter 目录包含：
   - `adapter_model.safetensors` 或 `adapter_model.bin`
   - `adapter_config.json`
   - `tokenizer_config.json`

### 运行测试

```bash
# 设置环境变量
export SENTINEL_LLM_PROVIDER=local_model
export SENTINEL_ADAPTER_PATH=/path/to/your/lora/adapter
# 可选：如果 adapter_config.json 中没有 base_model_name_or_path
export SENTINEL_BASE_MODEL_PATH=/path/to/base/model

# 运行
python main.py
```

### 示例路径

```bash
# 假设你的 LLaMA-Factory 训练输出在：
export SENTINEL_ADAPTER_PATH=/home/hzw/LLaMA-Factory/saves/Qwen3-4B-Base/lora/train_2026-01-17-11-40-08

# 如果 adapter_config.json 中已包含 base_model，则无需设置 SENTINEL_BASE_MODEL_PATH
python main.py
```

### 预期结果

- 首次运行会加载模型（约 10-30 秒，取决于模型大小）
- 后续推理速度取决于硬件（GPU/CPU）
- 生成质量取决于训练数据和微调效果

### 常见问题

**Q: 报错 "ModuleNotFoundError: No module named 'transformers'"**
```bash
pip install torch transformers peft accelerate
```

**Q: 报错 "CUDA out of memory"**
- 使用更小的模型（如 Qwen2.5-1.5B）
- 减少 `max_tokens`（在 config.py 中设置）
- 使用 CPU 推理（较慢）

**Q: 加载速度很慢**
- 正常现象，首次加载需要读取模型文件
- 考虑使用量化模型（如 int8/int4）

---

## 🧪 测试 6: Web UI

### 启动 Web UI

```bash
# 确保在虚拟环境中
source .venv/bin/activate

# 启动 Streamlit
streamlit run web_ui/app.py
```

### 访问

浏览器自动打开 `http://localhost:8501`

### 测试功能

#### 1. 历史记录查看

- 侧边栏选择「📚 历史案例」
- 从列表中选择一个 episode
- 点击「🔍 加载案例」
- 验证：
  - ✅ 任务概览显示正确
  - ✅ 工作流可视化（8 个阶段）
  - ✅ 证据卡片展示
  - ✅ 推荐动作展示
  - ✅ 交互式图表可缩放

#### 2. 新建诊断

- 点击侧边栏「🆕 新建诊断」
- 选择输入模式：
  - **预定义场景**：选择 "Latency Spike" 或 "CPU Thrashing"
  - **自定义问题**：输入 "auth-service 的 CPU 使用率突然升高到 95%"
- 配置 LLM：
  - **Mock**：无需配置
  - **通义千问**：填写 API Key
  - **硅基流动**：填写 API Key
  - **ModelScope**：填写 API Key
  - **本地模型**：填写 Adapter Path
- 点击「🚀 开始诊断」
- 验证：
  - ✅ 自动跳转到「📊 实时监控」页面
  - ✅ 显示任务 ID 和开始时间
  - ✅ 工作流进度实时更新
  - ✅ 每 3 秒自动刷新

#### 3. 实时监控

- 观察工作流进度：
  - DETECT → TRIAGE → INVESTIGATE → PLAN → APPROVE → EXECUTE → VERIFY → REPORT
- 等待任务完成（Mock 约 5-10 秒，真实 LLM 约 30-60 秒）
- 点击「📄 查看完整报告」
- 验证：
  - ✅ 跳转回主页
  - ✅ 自动加载刚完成的 episode
  - ✅ 显示完整的诊断结果

### 常见问题

**Q: 报错 "ModuleNotFoundError: No module named 'streamlit'"**
```bash
pip install streamlit plotly pandas streamlit-lottie
```

**Q: 页面显示 "No episodes found"**
- 先运行 `python main.py` 生成至少一个 episode
- 确认 `runs/` 目录存在且有数据

**Q: 新建诊断后没有反应**
- 检查终端是否有错误信息
- 确认 LLM 配置正确（API Key 等）
- 查看 `runs/` 目录是否生成新的 episode

---

## 🧪 测试 7: Docker 构建

### 构建镜像

```bash
# 在项目根目录
docker build -t sentinel:latest .
```

### 运行容器

```bash
# 使用 Mock LLM
docker run -d \
  -p 7860:7860 \
  -v $(pwd)/runs:/app/runs \
  -e SENTINEL_LLM_PROVIDER=mock \
  --name sentinel-web \
  sentinel:latest

# 使用通义千问
docker run -d \
  -p 7860:7860 \
  -v $(pwd)/runs:/app/runs \
  -e SENTINEL_LLM_PROVIDER=qwen \
  -e SENTINEL_LLM_MODEL=qwen-plus \
  -e DASHSCOPE_API_KEY=sk-your-key \
  --name sentinel-web \
  sentinel:latest
```

### 访问

浏览器打开 `http://localhost:7860`

### 验证

- ✅ Web UI 正常显示
- ✅ 可以查看历史记录
- ✅ 可以新建诊断
- ✅ 实时监控正常工作

### 停止容器

```bash
docker stop sentinel-web
docker rm sentinel-web
```

---

## 🧪 测试 8: Docker Compose

### 启动服务

```bash
# 使用 docker-compose.yml 中的配置
docker-compose up -d

# 查看日志
docker-compose logs -f sentinel-web
```

### 修改配置

编辑 `docker-compose.yml`，修改环境变量：

```yaml
environment:
  - SENTINEL_LLM_PROVIDER=qwen  # 改为你想用的 provider
  - DASHSCOPE_API_KEY=sk-your-key  # 添加你的 API Key
```

### 重启服务

```bash
docker-compose down
docker-compose up -d
```

---

## 📊 测试结果对比

| Provider | 速度 | 质量 | 成本 | 适用场景 |
|----------|------|------|------|----------|
| **Mock** | ⚡️ 极快（5-10s） | ⭐️ 低（规则生成） | 💰 免费 | 快速测试、演示 |
| **Qwen** | 🐢 中等（30-60s） | ⭐️⭐️⭐️⭐️ 高 | 💰💰 按量付费 | 生产环境、高质量需求 |
| **SiliconFlow** | 🐢 中等（30-60s） | ⭐️⭐️⭐️⭐️ 高 | 💰💰 按量付费 | 生产环境、多模型选择 |
| **ModelScope** | 🐢 中等（30-60s） | ⭐️⭐️⭐️⭐️ 高 | 💰💰 按量付费 | ModelScope 生态、国产模型 |
| **Local Model** | 🐌 慢（首次加载 10-30s，推理 5-20s/token） | ⭐️⭐️⭐️ 中-高（取决于微调） | 💰 免费（需硬件） | 私有化部署、离线环境 |

---

## 🔍 调试技巧

### 1. 查看详细日志

```bash
# 运行时显示详细日志
python main.py --verbose

# 或设置环境变量
export SENTINEL_LOG_LEVEL=DEBUG
python main.py
```

### 2. 查看 Trace 文件

```bash
# 查看最新的 trace.jsonl
cat runs/$(ls -t runs/ | head -1)/trace.jsonl | jq .
```

### 3. 查看 Episode 文件

```bash
# 查看最新的 episode.json
cat runs/$(ls -t runs/ | head -1)/episode.json | python -m json.tool
```

### 4. 测试单个 Agent

```python
# 创建测试脚本 test_agent.py
from sentinel.config import get_config
from sentinel.llm import get_llm_client
from sentinel.agents.triage import TriageAgent
from sentinel.types import Task

config = get_config()
llm = get_llm_client(config.llm)
agent = TriageAgent(llm_client=llm)

task = Task(
    task_id="test-001",
    source="alert",
    symptoms={"alert_name": "HighCPU", "service": "auth-service"},
    context={},
    constraints={},
    goal="Diagnose high CPU usage",
    budget={}
)

result = agent.run(task)
print(result)
```

---

## ✅ 测试清单

完成以下测试以确保系统正常工作：

- [ ] Mock LLM 测试通过
- [ ] 至少一个真实 LLM API 测试通过（Qwen/SiliconFlow/ModelScope）
- [ ] Web UI 启动成功
- [ ] Web UI 历史记录查看正常
- [ ] Web UI 新建诊断功能正常
- [ ] Web UI 实时监控功能正常
- [ ] Docker 镜像构建成功
- [ ] Docker 容器运行正常
- [ ] Docker Compose 启动成功

---

## 🆘 获取帮助

如果遇到问题：

1. 查看本文档的「常见问题」部分
2. 查看 `DEPLOYMENT_GUIDE.md` 的故障排查部分
3. 查看项目 README.md
4. 查看 GitHub Issues

---

**祝测试顺利！🎉**
