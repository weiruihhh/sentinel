"""
Executor agent: execute planned actions (M1: stub for dry-run only).
"""

from datetime import datetime

from pydantic import BaseModel, Field

from sentinel.agents.base import BaseAgent
from sentinel.llm.base import LLMClient
from sentinel.tools.registry import ToolRegistry
from sentinel.types import Action, Plan, PermissionLevel


class ExecutorInput(BaseModel):
    """Input for executor agent."""

    plan: Plan = Field(..., description="Plan to execute")
    caller_permission: PermissionLevel = Field(
        default=PermissionLevel.OPERATOR, description="Permission level for execution"
    )
    dry_run: bool = Field(default=True, description="Dry-run mode (M1: always True)")


class ExecutorOutput(BaseModel):
    """Output from executor agent."""

    executed_actions: list[Action] = Field(
        default_factory=list, description="Actions that were executed"
    )
    success_count: int = Field(default=0, description="Number of successful actions")
    failure_count: int = Field(default=0, description="Number of failed actions")
    total_duration_seconds: float = Field(default=0.0, description="Total execution time")


class ExecutorAgent(BaseAgent[ExecutorInput, ExecutorOutput]):
    """
    Executor agent responsible for:
    - 执行计划的操作：Executing planned actions
    - 处理批准 (M2)
    - 管理回滚 (M2)
    - 记录执行结果

    M1: 占位符实现 - 只支持dry-run模式。
    """

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry):
        """初始化执行代理。"""
        super().__init__(
            name="executor-agent",
            llm_client=llm_client,
            tool_registry=tool_registry,
        )

    def run(self, input_data: ExecutorInput) -> ExecutorOutput:
        """
        执行计划 (M1: 只支持dry-run模式)。

        Args:
            input_data: ExecutorInput with plan and options

        Returns:
            ExecutorOutput with execution results
        """
        plan = input_data.plan
        caller_permission = input_data.caller_permission
        dry_run = input_data.dry_run

        executed_actions = []
        success_count = 0
        failure_count = 0
        start_time = datetime.now()

        for action in plan.actions:
            # M1: 所有操作都是dry-run，只是标记为“would execute”
            action.dry_run = True
            action.executed = True
            action.execution_time = datetime.now()

            if dry_run:
                # 模拟dry-run的成功
                action.result = {
                    "dry_run": True,
                    "message": f"Would execute {action.tool_name} with args: {action.args}",
                    "status": "simulated_success",
                }
                success_count += 1
            else:
                # M2: 通过工具注册表实际执行操作
                action.result = {
                    "error": "M1 does not support actual execution. Use M2 for real operations.",
                }
                action.error = "Not implemented in M1"
                failure_count += 1

            executed_actions.append(action)

        total_duration = (datetime.now() - start_time).total_seconds()

        return ExecutorOutput(
            executed_actions=executed_actions,
            success_count=success_count,
            failure_count=failure_count,
            total_duration_seconds=total_duration,
        )
