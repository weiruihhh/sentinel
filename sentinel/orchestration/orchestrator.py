"""
Main orchestrator for Sentinel system.

Implements the complete workflow: Detect -> Triage -> Investigate -> Plan -> Verify -> Report
"""

from datetime import datetime
from typing import Any, Optional

from sentinel.agents.executor import ExecutorAgent, ExecutorInput
from sentinel.agents.investigation import InvestigationAgent, InvestigationInput
from sentinel.agents.planner import PlannerAgent, PlannerInput
from sentinel.agents.triage import TriageAgent, TriageInput
from sentinel.config import SentinelConfig
from sentinel.llm.base import LLMClient
from sentinel.observability.tracer import TraceRecorder
from sentinel.orchestration.graph import ExecutionContext, Graph
from sentinel.orchestration.policies import ApprovalPolicy, BudgetPolicy, RetryPolicy
from sentinel.orchestration.verifier import Verifier
from sentinel.tools.registry import ToolRegistry
from sentinel.types import Evidence, PermissionLevel, Plan, Report, Task


class Orchestrator:
    """
    主协调器，驱动完整的流程。
    Workflow:
    1. DETECT: 标准化输入为 Task
    2. TRIAGE: 分类和评估风险
    3. INVESTIGATE: 使用工具收集证据
    4. PLAN: 生成执行计划
    5. APPROVE: 检查计划是否需要批准 (M1: 自动批准)
    6. EXECUTE: 执行计划 (M1: 仅模拟执行)
    7. VERIFY: 验证结果 (M1: 模拟验证/M2: 真实验证)
    8. REPORT: 生成最终报告
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        tracer: TraceRecorder,
        config: SentinelConfig,
        budget_policy: Optional[BudgetPolicy] = None,
        retry_policy: Optional[RetryPolicy] = None,
        approval_policy: Optional[ApprovalPolicy] = None,
        caller_permission: PermissionLevel = PermissionLevel.OPERATOR,
    ):
        """
        初始化协调器。

        Args:
            llm_client: LLM 客户端，用于代理
            tool_registry: 工具注册表，用于查询指标和日志
            tracer: 追踪器，用于记录追踪信息
            config: Sentinel 配置
            budget_policy: 预算策略 (可选)
            retry_policy: 重试策略 (可选)
            approval_policy: 批准策略 (可选)
            caller_permission: 默认权限级别
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.tracer = tracer
        self.config = config
        self.caller_permission = caller_permission

        # Policies
        self.budget_policy = budget_policy or BudgetPolicy()
        self.retry_policy = retry_policy or RetryPolicy()
        self.approval_policy = approval_policy or ApprovalPolicy()

        # Initialize verifier
        self.verifier = Verifier(
            tool_registry=tool_registry,
            config=config,
            use_real_verification=config.orchestration.use_real_verification,
        )

        # Initialize agents
        self.triage_agent = TriageAgent(llm_client, tool_registry)
        self.investigation_agent = InvestigationAgent(llm_client, tool_registry)
        self.planner_agent = PlannerAgent(llm_client, tool_registry)
        self.executor_agent = ExecutorAgent(llm_client, tool_registry)

        # Build execution graph
        self.graph = self._build_graph()

    def _build_graph(self) -> Graph:
        """Build execution graph."""
        graph = Graph()

        # Add nodes
        graph.add_node("detect", self._node_detect, "Standardize input to Task")
        graph.add_node("triage", self._node_triage, "Classify and assess risk")
        graph.add_node("investigate", self._node_investigate, "Gather evidence")
        graph.add_node("plan", self._node_plan, "Generate execution plan")
        graph.add_node("approve", self._node_approve, "Approval check")
        graph.add_node("execute", self._node_execute, "Execute plan (M1: dry-run)")
        graph.add_node("verify", self._node_verify, "Verify outcome")
        graph.add_node("report", self._node_report, "Generate report")

        # Add edges (linear workflow for M1)
        graph.add_edge("detect", "triage")
        graph.add_edge("triage", "investigate")
        graph.add_edge("investigate", "plan")
        graph.add_edge("plan", "approve")
        graph.add_edge("approve", "execute")
        graph.add_edge("execute", "verify")
        graph.add_edge("verify", "report")

        return graph

    def run(self, task: Task) -> Report:
        """
        Run complete orchestration workflow.

        Args:
            task: Task to execute

        Returns:
            Final report

        Raises:
            Exception: If execution fails
        """
        # Start trace
        workflow_span_id = self.tracer.start_span(
            component="orchestrator",
            name="workflow",
            parent_span_id=None,
            metadata={"task_id": task.task_id, "source": task.source},
        )

        # Create execution context
        context = ExecutionContext(
            task_id=task.task_id,
            state={"task": task, "permission": self.caller_permission},
        )

        try:
            # Execute workflow
            start_node = "detect"
            current_node = start_node

            while current_node:
                # 检查预算是否超出
                if task.budget.is_exceeded():
                    raise RuntimeError(
                        f"Budget exceeded: {task.budget.tokens_used}/{task.budget.max_tokens} tokens, "
                        f"{task.budget.time_used:.1f}/{task.budget.max_time_seconds}s time, "
                        f"{task.budget.tool_calls_used}/{task.budget.max_tool_calls} tool calls"
                    )

                # Execute node
                node_start = datetime.now()
                success, result, error = self.graph.execute_node(current_node, context)
                node_duration = (datetime.now() - node_start).total_seconds()

                # Record budget
                task.budget.record_time_usage(node_duration)

                if not success:
                    raise RuntimeError(f"Node '{current_node}' failed: {error}")

                # Get next node
                next_nodes = self.graph.get_next_nodes(current_node, context)
                current_node = next_nodes[0] if next_nodes else None

            # Get final report
            report = context.get_node_result("report")
            if report is None:
                raise RuntimeError("No report generated")

            # End trace
            self.tracer.end_span(
                span_id=workflow_span_id,
                status="success",
                metadata={
                    "execution_path": context.execution_path,
                    "total_time": task.budget.time_used,
                },
            )

            return report

        except Exception as e:
            # End trace with error
            self.tracer.end_span(
                span_id=workflow_span_id,
                status="failed",
                error=str(e),
            )
            raise

    # ===== Node Handlers =====

    def _node_detect(self, context: ExecutionContext) -> Task:
        """Detect node: 标准化输入为 Task."""
        span_id = self.tracer.start_span(
            component="orchestrator",
            name="detect",
            parent_span_id=None,
        )

        task = context.state["task"]

        # 因为在入口层的时候就已经标准化了，所以这里直接返回

        self.tracer.end_span(span_id, status="success")
        return task

    def _node_triage(self, context: ExecutionContext) -> dict[str, Any]:
        """Triage node: 分类和评估风险."""
        span_id = self.tracer.start_span(
            component="agent",
            name="triage",
            parent_span_id=None,
        )

        task = context.state["task"]

        try:
            # 运行分类和评估风险代理
            triage_input = TriageInput(task=task)
            triage_output = self.triage_agent.run(triage_input)

            # Update task
            task.risk_level = triage_output.risk_level
            task.status = "triaged"

            self.tracer.end_span(
                span_id,
                status="success",
                metadata={
                    "severity": triage_output.severity,
                    "category": triage_output.category,
                    "risk_level": triage_output.risk_level.value,
                },
            )

            return triage_output.model_dump()

        except Exception as e:
            self.tracer.end_span(span_id, status="failed", error=str(e))
            raise

    def _node_investigate(self, context: ExecutionContext) -> dict[str, Any]:
        """Investigate node: gather evidence."""
        span_id = self.tracer.start_span(
            component="agent",
            name="investigate",
            parent_span_id=None,
        )

        task = context.state["task"]
        permission = context.state["permission"]

        try:
            # Run investigation agent
            investigation_input = InvestigationInput(
                task=task, caller_permission=permission
            )
            investigation_output = self.investigation_agent.run(investigation_input)

            # Record tool calls in budget
            task.budget.tool_calls_used += investigation_output.tool_calls_made

            # Store evidence in context
            context.state["evidence"] = investigation_output.evidence

            self.tracer.end_span(
                span_id,
                status="success",
                metadata={
                    "evidence_count": len(investigation_output.evidence),
                    "tool_calls": investigation_output.tool_calls_made,
                    "confidence": investigation_output.confidence,
                },
            )

            return investigation_output.model_dump()

        except Exception as e:
            self.tracer.end_span(span_id, status="failed", error=str(e))
            raise

    def _node_plan(self, context: ExecutionContext) -> dict[str, Any]:
        """Plan node: generate execution plan."""
        span_id = self.tracer.start_span(
            component="agent",
            name="plan",
            parent_span_id=None,
        )

        task = context.state["task"]
        evidence = context.state.get("evidence", [])

        try:
            # Run planner agent
            planner_input = PlannerInput(task=task, evidence=evidence)
            planner_output = self.planner_agent.run(planner_input)

            # Store plan in context
            context.state["plan"] = planner_output.plan

            self.tracer.end_span(
                span_id,
                status="success",
                metadata={
                    "hypotheses_count": len(planner_output.plan.hypotheses),
                    "actions_count": len(planner_output.plan.actions),
                    "approval_required": planner_output.plan.approval_required,
                },
            )

            return planner_output.model_dump()

        except Exception as e:
            self.tracer.end_span(span_id, status="failed", error=str(e))
            raise

    def _node_approve(self, context: ExecutionContext) -> dict[str, Any]:
        """Approve node: check if plan needs approval."""
        span_id = self.tracer.start_span(
            component="policy",
            name="approve",
            parent_span_id=None,
        )

        plan = context.state.get("plan")

        if plan is None:
            self.tracer.end_span(span_id, status="failed", error="No plan to approve")
            raise RuntimeError("No plan to approve")

        try:
            # Check approval policy
            approved, reason = self.approval_policy.approve_plan(plan)

            context.state["approval"] = {
                "approved": approved,
                "reason": reason,
            }

            self.tracer.end_span(
                span_id,
                status="success",
                metadata={"approved": approved, "reason": reason},
            )

            return {"approved": approved, "reason": reason}

        except Exception as e:
            self.tracer.end_span(span_id, status="failed", error=str(e))
            raise

    def _node_execute(self, context: ExecutionContext) -> dict[str, Any]:
        """Execute node: execute plan (M1: dry-run only)."""
        span_id = self.tracer.start_span(
            component="agent",
            name="execute",
            parent_span_id=None,
        )

        plan = context.state.get("plan")
        permission = context.state["permission"]
        approval = context.state.get("approval", {})

        if not approval.get("approved", False):
            self.tracer.end_span(span_id, status="skipped", error="Plan not approved")
            return {"status": "skipped", "reason": "Plan not approved"}

        try:
            # Run executor agent
            executor_input = ExecutorInput(
                plan=plan,
                caller_permission=permission,
                dry_run=True,  # M1: always dry-run
            )
            executor_output = self.executor_agent.run(executor_input)

            self.tracer.end_span(
                span_id,
                status="success",
                metadata={
                    "success_count": executor_output.success_count,
                    "failure_count": executor_output.failure_count,
                },
            )

            return executor_output.model_dump()

        except Exception as e:
            self.tracer.end_span(span_id, status="failed", error=str(e))
            raise

    def _node_verify(self, context: ExecutionContext) -> dict[str, Any]:
        """验证节点：使用真实指标/日志或模拟验证结果。目前已经改成真实"""
        span_id = self.tracer.start_span(
            component="orchestrator",
            name="verify",
            parent_span_id=None,
        )

        try:
            task = context.state["task"]

            # 使用验证器检查问题是否已解决
            verification_result = self.verifier.verify(task, context.state)

            # 转换为字典用于存储
            verification_dict = {
                "verified": verification_result.verified,
                "status": verification_result.status,
                "checks": verification_result.checks,
                "notes": verification_result.notes,
            }

            # 存储验证结果
            context.state["verification"] = verification_dict

            self.tracer.end_span(
                span_id,
                status="success",
                metadata=verification_dict,
            )

            return verification_dict

        # 处理异常
        except Exception as e:
            error_result = {
                "verified": False,
                "status": "error",
                "checks": [],
                "notes": f"Verification failed with error: {str(e)}",
            }
            context.state["verification"] = error_result

            self.tracer.end_span(
                span_id,
                status="failed",
                error=str(e),
                metadata=error_result,
            )

            return error_result

    def _node_report(self, context: ExecutionContext) -> Report:
        """Report node: generate final report."""
        span_id = self.tracer.start_span(
            component="orchestrator",
            name="report",
            parent_span_id=None,
        )

        task = context.state["task"]
        triage_result = context.get_node_result("triage") or {}
        investigation_result = context.get_node_result("investigate") or {}
        planner_result = context.get_node_result("plan") or {}
        executor_result = context.get_node_result("execute") or {}
        verification_result = context.get_node_result("verify") or {}

        # Build report
        evidence = context.state.get("evidence", [])
        plan = context.state.get("plan")

        # Generate summary
        summary = self._generate_summary(
            task, triage_result, investigation_result, verification_result
        )

        # Extract hypotheses
        hypotheses = plan.hypotheses if plan else []

        # Generate recommendations
        recommendations = []
        if plan:
            for action in plan.actions:
                desc = action.args.get("description", action.tool_name)
                recommendations.append(f"[{action.risk_level.value}] {desc}")

        # Determine status
        if verification_result.get("verified", False):
            status = "success"
        elif executor_result.get("failure_count", 0) > 0:
            status = "partial"
        else:
            status = "success"

        # Collect metrics
        metrics = {
            "tokens_used": task.budget.tokens_used,
            "time_used": task.budget.time_used,
            "tool_calls_used": task.budget.tool_calls_used,
            "evidence_count": len(evidence),
            "actions_planned": len(plan.actions) if plan else 0,
            "actions_executed": executor_result.get("success_count", 0),
        }

        report = Report(
            task_id=task.task_id,
            summary=summary,
            root_cause_hypotheses=hypotheses,
            recommended_actions=recommendations,
            evidence=evidence,
            plan=plan,
            metrics=metrics,
            status=status,
        )

        self.tracer.end_span(
            span_id,
            status="success",
            metadata={"report_status": status},
        )

        return report

    def _generate_summary(
        self,
        task: Task,
        triage_result: dict,
        investigation_result: dict,
        verification_result: dict,
    ) -> str:
        """Generate executive summary."""
        severity = triage_result.get("severity", "unknown")
        category = triage_result.get("category", "unknown")
        key_findings = investigation_result.get("key_findings", [])
        verified = verification_result.get("verified", False)

        summary = f"Task {task.task_id}: {task.goal}\n\n"
        summary += f"Severity: {severity}, Category: {category}\n\n"

        if key_findings:
            summary += "Key Findings:\n"
            for finding in key_findings[:3]:
                summary += f"- {finding}\n"

        if verified:
            summary += "\nVerification: Issue appears to be resolved."
        else:
            summary += "\nVerification: Issue requires further monitoring."

        return summary
