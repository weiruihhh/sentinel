# Sentinel - Industrial DataCenter Operations LLM Agent System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## 项目简介

Sentinel 是一个工业级数据中心运维 LLM Agent 系统骨架，具备以下特性：

- **可控**：基于图/状态机的编排引擎，支持风险分级和权限控制
- **可观测**：全链路 trace/log/metrics 记录（JSONL 格式）
- **可回滚**：预留回滚接口，计划生成包含回滚方案
- **模块化**：清晰的架构，支持多 Agent 协作工作流

## 架构概览

```
输入（告警/工单/提问）
    ↓
Task 标准化
    ↓
Orchestrator（状态机编排）
    ↓
Triage → Investigation → Plan → (Approve) → Execute → Verify → Report
    ↑                                                              ↓
Tools Registry（工具调用 + 权限控制）                    Observability（trace/metrics）
```

## 快速开始

### 安装依赖

```bash
cd sentinel
pip install pydantic python-dateutil
```

或使用 uv:

```bash
uv sync
```

### 运行示例

```bash
# 运行默认场景（latency spike）
python main.py

# 运行 CPU 飙升场景
python main.py --scenario cpu_thrash

# 查看帮助
python main.py --help
```

### 输出目录

运行后会在 `./runs/YYYYMMDD_HHMMSS/` 生成：

- `trace.jsonl`: 全链路跟踪记录
- `episode.json`: 完整的运行 episode（输入/输出/指标）
- `report.json`: 结构化运维报告

### 使用本地模型或 API（替代 Mock）

默认使用 Mock LLM（规则/模板输出）。要改为真实模型或 OpenAI 兼容 API：

1. **安装 API 依赖**（仅在使用真实 LLM 时需要）：

   ```bash
   uv sync --extra api
   # 或: pip install openai
   ```

2. **通过环境变量切换**（不改代码即可生效）：

   ```bash
   export SENTINEL_LLM_PROVIDER=openai
   export SENTINEL_LLM_MODEL=gpt-4          # 或本地模型名，如 qwen2.5、llama3.2
   export OPENAI_API_KEY=sk-xxx             # 云 API 必填；纯本地可填任意占位如 sk-local
   export OPENAI_API_BASE=https://api.openai.com/v1   # 本地/代理时改为你的 base URL
   python main.py
   ```

3. **Qwen3 / 通义千问**（无需记 base_url，用 provider=qwen 即可）：

   ```bash
   export SENTINEL_LLM_PROVIDER=qwen
   export SENTINEL_LLM_MODEL=qwen3-max   # 或 qwen-plus、qwen-turbo、qwen3-8b 等
   export DASHSCOPE_API_KEY=sk-xxx      # 阿里云 DashScope API Key
   python main.py
   ```

   底层仍走 DashScope 的 OpenAI 兼容接口，只是由 `provider=qwen` 自动填好 endpoint，无需再设 `OPENAI_API_BASE`。

4. **硅基流动 SiliconFlow**（provider=siliconflow，自动用硅基流动的 base_url）：

   ```bash
   export SENTINEL_LLM_PROVIDER=siliconflow
   export SENTINEL_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct   # 或硅基流动上其他模型名，如 deepseek-ai/DeepSeek-R1
   export SILICONFLOW_API_KEY=sk-xxx   # 硅基流动 API Key（云上创建）
   python main.py
   ```

5. **本地已保存模型（LoRA 进程内加载，如 LLaMA-Factory saves/Qwen3-4B-Base）**：  
   使用 `provider=local_model`，在进程内加载 LoRA，无需起本地 API 服务。

   ```bash
   export SENTINEL_LLM_PROVIDER=local_model
   export SENTINEL_ADAPTER_PATH=/path/to/LLaMA-Factory/saves/Qwen3-4B-Base/lora/train_2026-01-17-11-40-08
   # 可选: SENTINEL_BASE_MODEL_PATH=  不设则从 adapter 的 adapter_config.json 读取
   python main.py
   ```

6. **其他云端或本地 API**（OpenAI 兼容）：用 `provider=openai` 并设 `OPENAI_API_BASE`、`OPENAI_API_KEY`，例如 Ollama、vLLM、LM Studio 等。

7. **在代码里改配置**：在 `main.py` 运行前修改 `get_config()` 返回的 `config.llm`，或直接构造 `OpenAICompatLLM(...)` / `MockLLM(...)` 传给编排器；入口处已通过 `get_llm_client(config.llm)` 按 `config.llm.provider` 选择实现。

## Docker 部署

### 使用 Docker Compose（本地测试）

最简单的方式是使用 docker-compose：

```bash
# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f sentinel-web

# 停止服务
docker-compose down
```

访问 Web UI：http://localhost:7860

### 使用 Dockerfile（手动构建）

```bash
# 构建镜像
docker build -t sentinel:latest .

# 运行容器
docker run -d \
  -p 7860:7860 \
  -v $(pwd)/runs:/app/runs \
  -v $(pwd)/logs:/app/logs \
  -e SENTINEL_LLM_PROVIDER=mock \
  --name sentinel-web \
  sentinel:latest

# 查看日志
docker logs -f sentinel-web
```

### 环境变量配置

在 docker-compose.yml 或 docker run 命令中设置环境变量来配置 LLM：

```bash
# 使用 OpenAI
-e SENTINEL_LLM_PROVIDER=openai
-e SENTINEL_LLM_MODEL=gpt-4
-e OPENAI_API_KEY=sk-xxx
-e OPENAI_API_BASE=https://api.openai.com/v1

# 使用通义千问
-e SENTINEL_LLM_PROVIDER=qwen
-e SENTINEL_LLM_MODEL=qwen3-max
-e DASHSCOPE_API_KEY=sk-xxx

# 使用硅基流动
-e SENTINEL_LLM_PROVIDER=siliconflow
-e SENTINEL_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
-e SILICONFLOW_API_KEY=sk-xxx
```

### ModelScope（魔搭社区）部署

Sentinel 已针对 ModelScope 平台优化，可直接部署：

1. **准备代码**：将项目推送到 Git 仓库（GitHub/Gitee）

2. **创建应用**：
   - 登录 [ModelScope 创空间](https://modelscope.cn/studios)
   - 点击"创建应用" → 选择"从 Git 导入"
   - 填写仓库地址

3. **配置应用**：
   - **运行命令**：自动检测 Dockerfile
   - **端口**：7860（默认）
   - **环境变量**：在设置中添加 LLM 配置（如 `SENTINEL_LLM_PROVIDER`）

4. **部署**：点击"部署"，等待构建完成

5. **访问**：部署成功后，ModelScope 会提供公开访问链接

**注意事项**：
- ModelScope 免费版有资源限制（CPU/内存），建议使用轻量级 LLM 或 Mock 模式
- 如需使用本地模型（torch/transformers），建议升级到 GPU 实例
- 持久化数据（runs/logs）会在容器重启后丢失，建议定期导出

## 目录结构

```
sentinel/
├── sentinel/
│   ├── types.py              # 核心数据结构（Task/Evidence/Plan/Action等）
│   ├── config.py             # 配置项
│   ├── llm/                  # LLM 客户端抽象层
│   │   ├── base.py           # LLMClient 抽象基类
│   │   ├── mock.py           # Mock LLM 实现（规则/模板输出）
│   │   └── openai_compat.py  # OpenAI 兼容 API / 本地模型客户端
│   ├── tools/                # 工具层
│   │   ├── registry.py       # 工具注册、权限校验、风险分级
│   │   └── mock_tools.py     # 示例只读工具（metrics/logs/topology等）
│   ├── agents/               # Agent 实现
│   │   ├── base.py           # BaseAgent 抽象
│   │   ├── triage.py         # 分类/风险评估/路由
│   │   ├── investigation.py  # 调用工具收集证据
│   │   ├── planner.py        # 生成执行计划
│   │   └── executor.py       # 执行动作（M1 为桩）
│   ├── orchestration/        # 编排层
│   │   ├── graph.py          # 轻量状态机/图引擎
│   │   ├── orchestrator.py   # 主编排器（完整工作流）
│   │   └── policies.py       # 预算/重试/审批策略
│   ├── observability/        # 可观测性
│   │   └── tracer.py         # Trace 记录（JSONL）+ Metrics 聚合
│   └── eval/                 # 评测层
│       ├── episode.py        # Episode/Outcome 定义
│       └── evaluator.py      # 评测接口（stub）
└── main.py                   # 演示入口
```

## 核心概念

### Task（统一入口）

所有输入（告警/工单/提问）标准化为 Task：

- `task_id`: 唯一标识
- `source`: 来源类型（alert/ticket/chat/cron）
- `symptoms`: 症状描述（告警名、指标摘要等）
- `context`: 上下文（拓扑、变更历史、SLO、owner）
- `constraints`: 约束条件（只读模式、禁止重启等）
- `goal`: 任务目标
- `budget`: 预算限制（token/time/tool_calls）

### Evidence（调查证据）

Investigation Agent 收集的证据：

- `source`: 来源（工具名/文档/人工）
- `timestamp`: 时间戳
- `data`: 数据内容
- `confidence`: 置信度
- `notes`: 备注

### Plan（执行计划）

Planner Agent 生成的执行计划：

- `hypotheses`: 根因假设
- `actions`: 动作列表
- `expected_effect`: 预期效果
- `risks`: 风险点
- `rollback_plan`: 回滚计划（预留）
- `approval_required`: 是否需要审批

### 风险与权限模型

- **RiskLevel**: `READ_ONLY`, `SAFE_WRITE`, `RISKY_WRITE`
- **PermissionLevel**: `GUEST`, `OPERATOR`, `ADMIN`
- **ToolSpec**: 工具规范（schema、风险等级、权限要求）

所有工具调用必须经过 ToolRegistry 校验：

1. Schema 验证
2. 权限检查
3. 风险评估
4. 审计记录

## Milestone 路线图

### M1（当前）：骨架跑通 + 只读工具 + 报告产出

- ✅ 完整工作流：Detect → Triage → Investigation → Plan → Verify → Report
- ✅ 只读工具示例：query_metrics, query_logs, query_topology, get_change_history
- ✅ Mock LLM（规则/模板输出）
- ✅ 全链路 trace + Episode 记录
- ✅ 结构化 Report 输出

### M2（规划）：写操作 + 审批 + 真实 LLM

- [ ] 写操作工具（scale/restart/config update）
- [ ] 审批工作流（人工/自动）
- [ ] 接入真实 LLM（OpenAI/Qwen/Claude）
- [ ] Dry-run 模式实现
- [ ] 回滚机制完整实现

### M3（规划）：评测 + 优化 + 生产化

- [ ] Benchmark 数据集 + 自动评测
- [ ] 多轮对话支持
- [ ] 工具学习与优化
- [ ] 成本与性能优化
- [ ] 生产级部署方案

## 扩展指南

### 添加新 Agent

1. 继承 `BaseAgent`
2. 定义输入/输出 schema（Pydantic model）
3. 实现 `run()` 方法
4. 在 Orchestrator 中注册节点

### 添加新工具

1. 在 `mock_tools.py` 定义工具函数
2. 创建 `ToolSpec`（schema + risk + permission）
3. 注册到 `ToolRegistry`

### 接入真实 LLM

1. 在 `sentinel/llm/` 创建新文件（如 `openai.py`）
2. 继承 `LLMClient`
3. 实现 `generate()` 方法
4. 在 `config.py` 配置使用

## 技术栈

- **Python 3.11+**
- **Pydantic v2**: 数据验证和序列化
- **自研状态机引擎**: 无 LangChain 依赖
- **JSONL**: 可观测性数据格式

## License

MIT License

## 贡献指南

欢迎贡献！请确保：

1. 所有 public API 有类型标注
2. 关键模块有 docstring
3. 遵循现有代码风格
4. 新工具必须声明 schema 和风险等级

## 联系方式

- 项目负责人：Platform Engineering Team
- Issues: [GitHub Issues]
