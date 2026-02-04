#!/usr/bin/env python3
"""
Sentinel main entry point.

Run a complete workflow with a simulated alert/task.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from sentinel.config import SentinelConfig, get_config
from sentinel.eval.episode import Episode
from sentinel.eval.evaluator import Evaluator
from sentinel.ingestion import ingest
from sentinel.llm import get_llm_client
from sentinel.observability.tracer import TraceRecorder
from sentinel.orchestration.orchestrator import Orchestrator
from sentinel.orchestration.policies import ApprovalPolicy, BudgetPolicy, RetryPolicy
from sentinel.tools.mock_tools import register_mock_tools
from sentinel.tools.real_tools import register_real_tools
from sentinel.tools.registry import ToolRegistry
from sentinel.types import Budget, PermissionLevel, Task


def create_latency_spike_task() -> Task:
    """Create a simulated latency spike alert task."""
    return Task(
        task_id=f"task-latency-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        source="alert",
        symptoms={
            "alert_name": "High API Latency",
            "service": "auth-service",
            "metric": "request_latency_p99",
            "current_value": 850,
            "threshold": 200,
            "duration": "7 minutes",
            "severity": "high",
        },
        context={
            "service_owner": "auth-team",
            "slo": {"latency_p99": 200, "availability": 99.9},
            "recent_changes": "v2.3.1 deployed 3 minutes before alert",
            "affected_users": "~15% of requests",
        },
        constraints={
            "read_only": False,  # Allow safe writes
            "no_restart": False,
            "max_downtime_seconds": 30,
        },
        goal="Diagnose high latency issue, identify root cause, and recommend remediation",
        budget=Budget(
            max_tokens=50000,
            max_time_seconds=180,
            max_tool_calls=20,
        ),
    )


def create_cpu_thrash_task() -> Task:
    """Create a simulated CPU thrashing task."""
    return Task(
        task_id=f"task-cpu-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        source="alert",
        symptoms={
            "alert_name": "High CPU Usage",
            "service": "auth-service",
            "metric": "cpu_percent",
            "current_value": 95.7,
            "threshold": 80.0,
            "duration": "10 minutes",
            "severity": "high",
        },
        context={
            "service_owner": "auth-team",
            "slo": {"cpu_percent": 80, "availability": 99.9},
            "recent_changes": "v2.3.1 deployed 3 minutes before alert",
            "affected_users": "Service still available but slow",
        },
        constraints={
            "read_only": False,
            "no_restart": False,
            "max_downtime_seconds": 60,
        },
        goal="Diagnose CPU thrashing, identify root cause, and recommend remediation",
        budget=Budget(
            max_tokens=50000,
            max_time_seconds=180,
            max_tool_calls=20,
        ),
    )


def setup_output_dir() -> Path:
    """Create output directory for this run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("./runs") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def main():
    """Main entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Sentinel - Industrial DataCenter Operations LLM Agent System"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["latency_spike", "cpu_thrash"],
        help="Demo scenario (ignored if --input is set)",
    )
    parser.add_argument(
        "--input",
        type=str,
        metavar="FILE",
        help="Input JSON file (or '-' for stdin); requires --source. Normalized to Task via entry layer.",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["alert", "ticket", "chat", "cron"],
        help="Source type for --input (alert/ticket/chat/cron)",
    )
    parser.add_argument(
        "--message",
        type=str,
        metavar="TEXT",
        help="Free-form question/chat: run as chat task without JSON (e.g. --message \"auth-service CPU 很高怎么办\")",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory (default: ./runs/YYYYMMDD_HHMMSS)",
    )
    parser.add_argument(
        "--use-real-tools",
        action="store_true",
        help="Use real data sources (Prometheus, Loki, CMDB, etc.) instead of mock data",
    )
    parser.add_argument(
        "--prometheus-url",
        type=str,
        help="Prometheus server URL (default: http://localhost:9091)",
    )
    parser.add_argument(
        "--loki-url",
        type=str,
        help="Loki server URL (default: http://localhost:3100)",
    )
    parser.add_argument(
        "--cmdb-url",
        type=str,
        help="CMDB API URL",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute write operations (scale, restart, etc.). Default is dry_run mode.",
    )

    args = parser.parse_args()

    # Create task: entry layer (--message / --input + --source) or demo scenario
    scenario_key: str
    if args.message is not None:
        task = ingest({"message": args.message}, "chat")
        scenario_key = "ingestion_chat"
        print(f"📥 Entry layer: chat (--message) -> Task {task.task_id}")
    elif args.input is not None:
        if args.source is None:
            print("❌ --input requires --source (alert|ticket|chat|cron)")
            sys.exit(1)
        raw = json.load(sys.stdin) if args.input == "-" else json.loads(Path(args.input).read_text())
        task = ingest(raw, args.source)
        scenario_key = f"ingestion_{args.source}"
        print(f"📥 Entry layer: {args.source} -> Task {task.task_id}")
    else:
        scenario_key = args.scenario or "latency_spike"
        if scenario_key == "latency_spike":
            task = create_latency_spike_task()
            print(f"🚨 Scenario: Latency Spike Alert")
        elif scenario_key == "cpu_thrash":
            task = create_cpu_thrash_task()
            print(f"🚨 Scenario: CPU Thrashing Alert")
        else:
            print(f"❌ Unknown scenario: {scenario_key}")
            sys.exit(1)

    print(f"📋 Task ID: {task.task_id}")
    print(f"🎯 Goal: {task.goal}")
    print()

    # Setup output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = setup_output_dir()

    print(f"📁 Output directory: {output_dir}")
    print()

    # Initialize components
    config = get_config()

    # Override data source config from command line args
    if args.use_real_tools:
        config.data_sources.use_real_tools = True
        # Enable real verification when using real tools
        config.orchestration.use_real_verification = True
    if args.prometheus_url:
        config.data_sources.prometheus_url = args.prometheus_url
    if args.loki_url:
        config.data_sources.loki_url = args.loki_url
    if args.cmdb_url:
        config.data_sources.cmdb_url = args.cmdb_url
    if args.execute:
        config.data_sources.execute_write_operations = True

    # LLM client: mock or real API/local from config (see config.llm.provider, api_base, api_key)
    llm_client = get_llm_client(config.llm)
    print(f"🤖 LLM: {llm_client}")

    # Tool registry
    tool_registry = ToolRegistry()
    if config.data_sources.use_real_tools:
        register_real_tools(tool_registry, config.data_sources)
        print(f"🔧 Tools registered: {len(tool_registry.list_tools())} (REAL data sources)")
        if config.data_sources.execute_write_operations:
            print(f"⚠️  Write operations: EXECUTE mode (will perform actual changes)")
        else:
            print(f"🔒 Write operations: DRY RUN mode (use --execute to perform actual changes)")
    else:
        register_mock_tools(tool_registry)
        print(f"🔧 Tools registered: {len(tool_registry.list_tools())} (MOCK data)")


    # Tracer
    tracer = TraceRecorder(output_dir=output_dir)
    print(f"📊 Tracer initialized")

    # Policies
    budget_policy = BudgetPolicy(
        max_tokens=50000,
        max_time_seconds=180,
        max_tool_calls=20,
    )
    retry_policy = RetryPolicy(max_retries=3)
    approval_policy = ApprovalPolicy(
        auto_approve_read_only=True,
        auto_approve_safe_write=True,  # M1: auto-approve safe writes
        require_approval_for_risky=True,
    )
    print(f"📜 Policies configured")
    print()

    # Create orchestrator
    orchestrator = Orchestrator(
        llm_client=llm_client,
        tool_registry=tool_registry,
        tracer=tracer,
        config=config,
        budget_policy=budget_policy,
        retry_policy=retry_policy,
        approval_policy=approval_policy,
        caller_permission=PermissionLevel.OPERATOR,
    )
    print(f"🎭 Orchestrator ready")
    if config.orchestration.use_real_verification:
        print(f"✅ Real verification enabled")
    else:
        print(f"⚠️  Mock verification (use --use-real-tools for real verification)")
    print()

    # Run workflow
    print("=" * 80)
    print("🚀 Starting workflow execution...")
    print("=" * 80)
    print()

    try:
        start_time = datetime.now()

        # Execute
        report = orchestrator.run(task)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print()
        print("=" * 80)
        print("✅ Workflow completed successfully!")
        print("=" * 80)
        print()

        # Print report summary
        print("📄 REPORT SUMMARY")
        print("-" * 80)
        print(report.summary)
        print()

        print("🔍 ROOT CAUSE HYPOTHESES")
        print("-" * 80)
        for i, hypothesis in enumerate(report.root_cause_hypotheses, 1):
            print(f"{i}. {hypothesis}")
        print()

        print("💡 RECOMMENDED ACTIONS")
        print("-" * 80)
        for i, action in enumerate(report.recommended_actions, 1):
            print(f"{i}. {action}")
        print()

        print("📊 METRICS")
        print("-" * 80)
        for key, value in report.metrics.items():
            print(f"  {key}: {value}")
        print()

        # Save outputs
        print("💾 Saving outputs...")

        # Save report
        report_file = output_dir / "report.json"
        with open(report_file, "w") as f:
            json.dump(report.model_dump(), f, indent=2, default=str)
        print(f"  ✓ Report: {report_file}")

        # Create episode
        episode = Episode.from_execution(
            task=task,
            report=report,
            trace_file=str(output_dir / "trace.jsonl"),
            config={
                "llm_model": llm_client.model,
                "scenario": scenario_key,
                "policies": {
                    "budget": budget_policy.model_dump(),
                    "retry": retry_policy.model_dump(),
                    "approval": approval_policy.model_dump(),
                },
            },
        )

        # Save episode
        episode_file = output_dir / "episode.json"
        with open(episode_file, "w") as f:
            json.dump(episode.to_dict(), f, indent=2, default=str)
        print(f"  ✓ Episode: {episode_file}")

        # Trace is already written
        print(f"  ✓ Trace: {output_dir / 'trace.jsonl'}")

        # Evaluate episode
        evaluator = Evaluator()
        scores = evaluator.evaluate(episode)

        print()
        print("🏆 EVALUATION SCORES")
        print("-" * 80)
        print(f"  Overall:      {scores.overall_score:.2f}")
        print(f"  Correctness:  {scores.correctness:.2f}")
        print(f"  Completeness: {scores.completeness:.2f}")
        print(f"  Efficiency:   {scores.efficiency:.2f}")
        print(f"  Safety:       {scores.safety:.2f}")
        print()

        print("=" * 80)
        print(f"✨ Total execution time: {duration:.2f}s")
        print(f"📂 All outputs saved to: {output_dir}")
        print("=" * 80)

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ Workflow failed: {e}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
