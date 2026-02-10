"""
Backend runner for executing diagnosis tasks asynchronously.
"""

import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Global registry for running tasks
_running_tasks: Dict[str, Dict] = {}
_tasks_lock = threading.Lock()


def run_diagnosis_async(
    scenario: Optional[str] = None,
    message: Optional[str] = None,
    llm_provider: str = "mock",
    llm_model: str = "",
    llm_api_key: str = "",
    llm_api_base: str = "",
    llm_adapter_path: str = "",
    llm_base_model_path: str = "",
    use_real_tools: bool = False,
    execute_mode: bool = False,
    prometheus_url: str = "",
    loki_url: str = "",
    cmdb_url: str = "",
) -> str:
    """
    Run diagnosis asynchronously in background.

    Args:
        scenario: Predefined scenario (latency_spike, cpu_thrash) or None for custom
        message: Custom message for chat-based diagnosis
        llm_provider: LLM provider (mock, local_model, qwen, siliconflow)
        llm_model: Model name
        llm_api_key: API key for API-based providers
        llm_api_base: API base URL
        llm_adapter_path: Adapter path for local_model
        llm_base_model_path: Base model path for local_model
        use_real_tools: Use real data sources
        execute_mode: Execute write operations (vs dry-run)
        prometheus_url: Prometheus URL
        loki_url: Loki URL
        cmdb_url: CMDB URL

    Returns:
        task_id: Unique task identifier
    """
    # Generate task ID and output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = f"webui_{timestamp}"
    output_dir = Path("./runs") / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = ["python", "main.py"]

    # Scenario or message
    if message:
        cmd.extend(["--message", message])
    elif scenario:
        cmd.extend(["--scenario", scenario])
    else:
        raise ValueError("Either scenario or message must be provided")

    # Output directory
    cmd.extend(["--output-dir", str(output_dir)])

    # Data sources
    if use_real_tools:
        cmd.append("--use-real-tools")
        if prometheus_url:
            cmd.extend(["--prometheus-url", prometheus_url])
        if loki_url:
            cmd.extend(["--loki-url", loki_url])
        if cmdb_url:
            cmd.extend(["--cmdb-url", cmdb_url])

    # Execute mode
    if execute_mode:
        cmd.append("--execute")

    # Build environment variables for LLM config
    env = {}
    if llm_provider:
        env["SENTINEL_LLM_PROVIDER"] = llm_provider
    if llm_model:
        env["SENTINEL_LLM_MODEL"] = llm_model
    if llm_api_key:
        if llm_provider == "qwen":
            env["DASHSCOPE_API_KEY"] = llm_api_key
        elif llm_provider == "siliconflow":
            env["SILICONFLOW_API_KEY"] = llm_api_key
        else:
            env["OPENAI_API_KEY"] = llm_api_key
    if llm_api_base:
        if llm_provider == "qwen":
            env["DASHSCOPE_API_BASE"] = llm_api_base
        elif llm_provider == "siliconflow":
            env["SILICONFLOW_API_BASE"] = llm_api_base
        else:
            env["OPENAI_API_BASE"] = llm_api_base
    if llm_adapter_path:
        env["SENTINEL_ADAPTER_PATH"] = llm_adapter_path
    if llm_base_model_path:
        env["SENTINEL_BASE_MODEL_PATH"] = llm_base_model_path

    # Register task
    with _tasks_lock:
        _running_tasks[task_id] = {
            "task_id": task_id,
            "output_dir": str(output_dir),
            "status": "starting",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "error": None,
            "process": None,
        }

    # Start process in background thread
    def _run_process():
        try:
            # Update status
            with _tasks_lock:
                _running_tasks[task_id]["status"] = "running"

            # Run process
            process = subprocess.Popen(
                cmd,
                env={**subprocess.os.environ, **env},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Store process
            with _tasks_lock:
                _running_tasks[task_id]["process"] = process

            # Wait for completion
            stdout, stderr = process.communicate()

            # Update status
            with _tasks_lock:
                if process.returncode == 0:
                    _running_tasks[task_id]["status"] = "completed"
                else:
                    _running_tasks[task_id]["status"] = "failed"
                    _running_tasks[task_id]["error"] = stderr
                _running_tasks[task_id]["end_time"] = datetime.now().isoformat()
                _running_tasks[task_id]["process"] = None

        except Exception as e:
            with _tasks_lock:
                _running_tasks[task_id]["status"] = "failed"
                _running_tasks[task_id]["error"] = str(e)
                _running_tasks[task_id]["end_time"] = datetime.now().isoformat()

    # Start thread
    thread = threading.Thread(target=_run_process, daemon=True)
    thread.start()

    return task_id


def get_task_status(task_id: str) -> Optional[Dict]:
    """
    Get status of a running or completed task.

    Args:
        task_id: Task identifier

    Returns:
        Task status dict or None if not found
    """
    with _tasks_lock:
        return _running_tasks.get(task_id, None)


def get_running_tasks() -> Dict[str, Dict]:
    """
    Get all running tasks.

    Returns:
        Dict of task_id -> task_info
    """
    with _tasks_lock:
        return {
            tid: info
            for tid, info in _running_tasks.items()
            if info["status"] in ("starting", "running")
        }


def get_trace_events(output_dir: str) -> list:
    """
    Read trace events from trace.jsonl file.

    Args:
        output_dir: Output directory path

    Returns:
        List of trace events
    """
    trace_file = Path(output_dir) / "trace.jsonl"
    if not trace_file.exists():
        return []

    events = []
    try:
        with open(trace_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except Exception:
        pass

    return events


def get_workflow_progress(output_dir: str) -> Dict:
    """
    Get workflow progress from trace events.

    Args:
        output_dir: Output directory path

    Returns:
        Dict with stage progress information
    """
    events = get_trace_events(output_dir)

    stages = {
        "detect": {"status": "pending", "start": None, "end": None},
        "triage": {"status": "pending", "start": None, "end": None},
        "investigate": {"status": "pending", "start": None, "end": None},
        "plan": {"status": "pending", "start": None, "end": None},
        "approve": {"status": "pending", "start": None, "end": None},
        "execute": {"status": "pending", "start": None, "end": None},
        "verify": {"status": "pending", "start": None, "end": None},
        "report": {"status": "pending", "start": None, "end": None},
    }

    for event in events:
        event_type = event.get("event_type", "")
        stage = event.get("stage", "")

        if stage in stages:
            if event_type == "stage_start":
                stages[stage]["status"] = "running"
                stages[stage]["start"] = event.get("timestamp")
            elif event_type == "stage_end":
                stages[stage]["status"] = "completed"
                stages[stage]["end"] = event.get("timestamp")
            elif event_type == "stage_error":
                stages[stage]["status"] = "error"
                stages[stage]["end"] = event.get("timestamp")

    return stages
