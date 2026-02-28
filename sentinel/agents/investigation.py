"""
Investigation agent: 
证据收集代理：使用工具收集证据。
包含ReAct模式（LLM驱动的迭代工具调用）和传统模式（预定义规则和工作流）；主要是前一种模式。
流程：
1. 接收调查任务，包含目标、症状和上下文
2. 迭代收集证据（ReAct模式）：
   - LLM决定下一步行动（是否继续，调用哪个工具，使用什么参数）
   - 调用工具并记录结果作为证据
   - LLM基于新证据调整调查方向
3. 分析收集的证据，形成关键发现和下一步建议
"""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from sentinel.agents.base import BaseAgent
from sentinel.llm.base import LLMClient
from sentinel.tools.registry import ToolRegistry
from sentinel.types import Evidence, LLMMessage, PermissionLevel, Task

#自定义输入输出模型，确保输入输出结构清晰且类型安全
class InvestigationInput(BaseModel):
    """Input for investigation agent."""

    task: Task = Field(..., description="Task to investigate")
    caller_permission: PermissionLevel = Field(
        default=PermissionLevel.OPERATOR, description="Permission level for tool calls"
    )


class InvestigationOutput(BaseModel):
    """Output from investigation agent."""

    evidence: list[Evidence] = Field(default_factory=list, description="Collected evidence")
    key_findings: list[str] = Field(default_factory=list, description="Key findings summary")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Overall confidence in findings"
    )
    next_steps: list[str] = Field(
        default_factory=list, description="Recommended next steps"
    )
    tool_calls_made: int = Field(default=0, description="Number of tool calls executed")


class InvestigationAgent(BaseAgent[InvestigationInput, InvestigationOutput]): #这种继承的方式确保了输入输出
    """
    Investigation agent responsible for:
    - 调用只读工具收集证据
    - 分析指标、日志、拓扑、变化
    - 建立全面的证据基础
    - 形成假设
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        use_react_mode: bool = True,
        max_react_iterations: int = 5,
    ):
        """
        Initialize investigation agent.

        Args:
            llm_client: LLM推理客户端
            tool_registry: 工具注册以便于调用
            use_react_mode: 是否使用ReAct模式(否则就是硬规则编码) 
            max_react_iterations: 最大ReAct迭代次数，防止无限循环
        """
        super().__init__(
            name="investigation-agent",
            llm_client=llm_client,
            tool_registry=tool_registry,
        )
        self.use_react_mode = use_react_mode
        self.max_react_iterations = max_react_iterations

    def run(self, input_data: InvestigationInput) -> InvestigationOutput:
        """
        调查一个任务，通过收集证据。

        Args:
            input_data: 调查的输入，包含任务和权限信息

        Returns:
            调查结果(输出)，包含收集的证据、关键发现、置信度和推荐的下一步措施
        """
        task = input_data.task
        caller_permission = input_data.caller_permission

        # 选择调查模式
        if self.use_react_mode:
            # ReAct mode: 大模型语义判断驱动进行工具选择和调用以及接下来的调查。
            evidence_list = self._react_investigation(task, caller_permission)
        else:
            # Traditional mode: 工作流式的硬编码
            evidence_list = self._traditional_investigation(task, caller_permission)

        # 用LLM分析收集的证据，形成关键发现和下一步建议
        analysis = self._analyze_evidence(task, evidence_list)

        return InvestigationOutput(
            evidence=evidence_list,
            key_findings=analysis.get("key_findings", []),
            confidence=analysis.get("confidence", 0.5),
            next_steps=analysis.get("next_steps", []),
            tool_calls_made=len(evidence_list),
        )

    def _react_investigation(
        self, task: Task, caller_permission: PermissionLevel
    ) -> list[Evidence]:
        """
        ReAct mode: 大模型语义判断驱动进行工具选择和调用以及接下来的调查。

        Args:
            task: 要调查的任务
            caller_permission: 工具调用的权限级别

        Returns:
            返回收集的证据列表
        """
        evidence_list: list[Evidence] = []
        iteration = 0

        while iteration < self.max_react_iterations:
            iteration += 1

            # Think: LLM 决定下一步行动（是否继续，调用哪个工具，使用什么参数）
            decision = self._think_next_action(task, evidence_list)

            # 如果LLM决定停止调查，或者没有指定工具，就退出循环
            if decision.get("should_stop", False):
                break

            # Act: 根据LLM的决策调用工具
            tool_name = decision.get("tool_name")
            tool_args = decision.get("tool_args", {})

            # LLM没有指定工具，无法继续调查，记录为证据并停止
            if not tool_name:
                break

            try:
                # 调用工具并记录结果
                result = self.tool_registry.call(
                    tool_name=tool_name,
                    args=tool_args,
                    caller_permission=caller_permission,
                )

                # Observe: 记录工具调用结果作为证据
                evidence = Evidence(
                    source=tool_name,
                    timestamp=datetime.now(),
                    data=result,
                    confidence=0.8,
                    notes=decision.get("reasoning", ""),
                )
                evidence_list.append(evidence)

            except Exception as e:
                # 工具调用失败，记录错误信息作为证据
                evidence = Evidence(
                    source=tool_name,
                    timestamp=datetime.now(),
                    data={"error": str(e)},
                    confidence=0.1,
                    notes=f"Tool call failed: {e}",
                )
                evidence_list.append(evidence)

        return evidence_list

    def _think_next_action(
        self, task: Task, evidence_list: list[Evidence]
    ) -> dict[str, Any]:
        """
        LLM 思考下一步行动：是否继续调查，调用哪个工具，使用什么参数。

        Args:
            task: 要调查的任务
            evidence_list: 已收集的证据列表

        Returns:
            包含决策信息的字典：reasoning, should_stop, tool_name, tool_args
        """
        # 标准化可用工具列表
        tools_desc = self._format_tools_for_llm()

        # 标准化已收集的证据摘要
        evidence_summary = self._format_evidence_summary(evidence_list)

        # 构建系统提示词，指导LLM如何基于任务、症状和已收集的证据来决定下一步行动
        system_prompt = """You are an investigation agent for datacenter operations.

        Your task is to collect evidence by calling tools iteratively (ReAct pattern).

        Available tools:
        {tools}

        For each iteration, output JSON with:
        {{
        "reasoning": "Why I need this information...",
        "should_stop": false,
        "tool_name": "query_metrics",
        "tool_args": {{"service": "auth-service", "metric": "cpu_percent", "aggregation": "max"}}
        }}

        When you have enough evidence, set should_stop=true and omit tool_name/tool_args.

        Guidelines:
        1. Start with topology and change history
        2. Then query relevant metrics based on symptoms
        3. Check logs for errors
        4. Stop when you have sufficient evidence to form hypotheses
        """.format(tools=tools_desc)



        # 构建用户消息，包含任务目标、症状和已收集的证据摘要，询问LLM下一步行动
        user_message = f"""Task: {task.goal}

        Symptoms:
        {json.dumps(task.symptoms, indent=2)}

        Evidence collected so far ({len(evidence_list)} items):
        {evidence_summary}

        What should I do next?
        """

        # 调用LLM获取下一步行动决策
        messages = [LLMMessage(role="user", content=user_message)]
        response = self.llm_client.generate(messages, system_prompt=system_prompt)

        # 解析LLM响应，提取决策信息
        try:
            decision = json.loads(response.content)
            return decision
        except Exception:
            # Fallback: 如果LLM响应无法解析，记录原因并停止调查
            return {"reasoning": "Failed to parse LLM response", "should_stop": True}

    def _traditional_investigation(
        self, task: Task, caller_permission: PermissionLevel
    ) -> list[Evidence]:
        """
        Traditional mode: 基于预定义的规则和工作流进行调查，调用一系列工具来收集证据。

        Args:
            task: 要调查的任务
            caller_permission: 工具调用的权限级别
        Returns:
            返回收集的证据列表
        """
        # 基于任务的症状和上下文，预定义要调用的工具列表和参数
        tools_to_call = self._plan_investigation(task)

        evidence_list: list[Evidence] = []
        for tool_spec in tools_to_call:
            try:
                result = self.tool_registry.call(
                    tool_name=tool_spec["tool_name"],
                    args=tool_spec["args"],
                    caller_permission=caller_permission,
                )

                evidence = Evidence(
                    source=tool_spec["tool_name"],
                    timestamp=datetime.now(),
                    data=result,
                    confidence=0.8,
                    notes=tool_spec.get("notes", ""),
                )
                evidence_list.append(evidence)

            except Exception as e:
                evidence = Evidence(
                    source=tool_spec["tool_name"],
                    timestamp=datetime.now(),
                    data={"error": str(e)},
                    confidence=0.1,
                    notes=f"Tool call failed: {e}",
                )
                evidence_list.append(evidence)

        return evidence_list



    def _format_tools_for_llm(self) -> str:
        """标准化可用工具列表，供LLM理解和选择。"""
        tools = self.tool_registry.list_tools()
        lines = []
        for spec in tools:
            lines.append(f"- {spec.name}: {spec.description}")
            lines.append(f"  Args: {json.dumps(spec.input_schema)}")
        return "\n".join(lines)

    def _format_evidence_summary(self, evidence_list: list[Evidence]) -> str:
        """标准化已收集的证据摘要，供LLM理解当前调查状态。"""
        if not evidence_list:
            return "(No evidence collected yet)"

        lines = []
        for i, e in enumerate(evidence_list, 1):
            lines.append(f"{i}. {e.source}: {e.notes}")
        return "\n".join(lines)

    def _plan_investigation(self, task: Task) -> list[dict[str, Any]]:
        """
        计划要调用哪些工具基于任务。

        Args:
            task: 要调查的任务，包含症状和上下文

        Returns:
            要调用的工具列表，每个工具包含tool_name, args, notes
        """
        tools_to_call = []
        symptoms = task.symptoms
        context = task.context

        # 确定受影响的服务
        service = symptoms.get("service", "auth-service")  # 默认服务，实际应该从症状或上下文中提取

        # 总是收集基本信息
        tools_to_call.append(
            {
                "tool_name": "query_topology",
                "args": {"service": service},
                "notes": "Get service topology and dependencies",
            }
        )

        tools_to_call.append(
            {
                "tool_name": "get_change_history",
                "args": {"service": service, "since_hours": 24},
                "notes": "Check recent changes (deployments, config)",
            }
        )

        # 如果症状提到特定的指标，查询它们
        if "cpu" in str(symptoms).lower() or "latency" in str(symptoms).lower():
            tools_to_call.append(
                {
                    "tool_name": "query_metrics",
                    "args": {"service": service, "metric": "cpu_percent", "aggregation": "max"},
                    "notes": "Check CPU metrics",
                }
            )
            tools_to_call.append(
                {
                    "tool_name": "query_metrics",
                    "args": {
                        "service": service,
                        "metric": "request_latency_p99",
                        "aggregation": "max",
                    },
                    "notes": "Check latency metrics",
                }
            )

        # 总是检查错误日志，因为它们通常包含关键线索
        tools_to_call.append(
            {
                "tool_name": "query_logs",
                "args": {"service": service, "level": "ERROR", "limit": 50},
                "notes": "Check error logs",
            }
        )

        return tools_to_call

    def _analyze_evidence(
        self, task: Task, evidence_list: list[Evidence]
    ) -> dict[str, Any]:
        """
        用LLM分析收集的证据。

        Args:
            task: 初始任务，包含目标、症状和上下文
            evidence_list: 已收集的证据列表

        Returns:
            线索词典 with key_findings, confidence, next_steps
        """
        # 构建系统提示词
        system_prompt = """You are an investigation analyst for datacenter operations.

Analyze the collected evidence and provide:
1. Key findings (list of important observations)
2. Confidence level (0.0-1.0)
3. Recommended next steps

Output valid JSON with fields: key_findings, confidence, next_steps.

Example output (for a latency spike investigation):
{
  "key_findings": [
    "request_latency_p99 spiked to 850ms in the last 15 minutes",
    "No recent deployments in the past 24 hours; config change 6 hours ago",
    "Error logs show increased timeout errors from downstream auth-service"
  ],
  "confidence": 0.75,
  "next_steps": [
    "Generate remediation plan (scale or tune timeouts)",
    "Verify downstream health and capacity"
  ]
}
"""

        evidence_summary = "\n\n".join(
            [
                f"Evidence from {e.source}:\n{json.dumps(e.data, indent=2)}\nNotes: {e.notes}"
                for e in evidence_list
            ]
        )

        user_message = f"""Task: {task.goal}

Symptoms:
{json.dumps(task.symptoms, indent=2)}

Evidence collected:
{evidence_summary}

Analyze this evidence and provide structured findings.
"""

        # 调用LLM
        messages = [LLMMessage(role="user", content=user_message)]
        response = self.llm_client.generate(messages, system_prompt=system_prompt)

        # 解析响应
        try:
            analysis = json.loads(response.content)
            return analysis
        except Exception:
            # Fallback: extract key findings from evidence
            key_findings = []
            for e in evidence_list:
                if e.confidence > 0.5 and e.notes:
                    key_findings.append(e.notes)

            return {
                "key_findings": key_findings[:5],
                "confidence": 0.6,
                "next_steps": ["Generate remediation plan based on findings"],
            }
