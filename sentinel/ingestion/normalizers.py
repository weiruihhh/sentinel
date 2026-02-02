"""
Normalizers: 将各种风格的输入原始数据转换为统一标准Task格式。
输入数据格式非常灵活（dict）；我们提取已知字段并将其余字段放入symptoms/context中。
"""

from datetime import datetime
from typing import Any, Literal

from sentinel.types import Budget, Task

SourceType = Literal["alert", "ticket", "chat", "cron"]


def _task_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _default_budget() -> Budget:
    return Budget(max_tokens=50000, max_time_seconds=180, max_tool_calls=20)


def _normalize_alert(raw: dict[str, Any]) -> Task:
    """将类似Prometheus webhook, PagerDuty风格的告警数据转换为Task格式。"""
    # Prometheus返回格式: 
    #     {
    #   "alerts": [{
    #     "labels": {"alertname": "HighLatency", "service": "auth-service", "severity": "high"},
    #     "annotations": {"summary": "Diagnose high latency and recommend remediation"}
    #   }],
    #   "commonLabels": {"alertname": "HighLatency"},
    #   "receiver": "sentinel"
    # }
    alerts = raw.get("alerts", [raw])
    first = alerts[0] if isinstance(alerts[0], dict) else {}
    labels = first.get("labels", raw.get("commonLabels", first))
    annotations = first.get("annotations", raw.get("commonAnnotations", {}))
    if isinstance(labels, dict):
        symptoms = {**labels, **annotations}
    else:
        symptoms = {"labels": labels, "annotations": annotations, "_raw": raw}
    context = {
        "receiver": raw.get("receiver"),
        "groupLabels": raw.get("groupLabels"),
        "externalURL": raw.get("externalURL"),
        "_raw_keys": list(raw.keys()),
    }
    context = {k: v for k, v in context.items() if v is not None}
    goal = annotations.get("summary", str(symptoms.get("alertname", "Investigate alert")))
    budget = _default_budget()
    if "budget" in raw and isinstance(raw["budget"], dict):
        budget = Budget(**_default_budget().model_dump() | raw["budget"])
    return Task(
        task_id=raw.get("task_id") or _task_id("alert"),
        source="alert",
        symptoms=symptoms,
        context=context,
        constraints=raw.get("constraints", {}),
        goal=goal,
        budget=budget,
    )


def _normalize_ticket(raw: dict[str, Any]) -> Task:
    """对类似Jira, ServiceNow风格的工单数据转换为Task格式。"""
    task_id = raw.get("task_id") or raw.get("id") or raw.get("key") or _task_id("ticket")
    title = raw.get("title") or raw.get("summary") or raw.get("subject") or ""
    desc = raw.get("description") or raw.get("body") or raw.get("content") or raw.get("text") or ""
    symptoms = {
        "title": title or None,
        "description": desc or None,
        "priority": raw.get("priority"),
        "status": raw.get("status"),
        "assignee": raw.get("assignee"),
    }
    symptoms = {k: v for k, v in symptoms.items() if v is not None}
    context = {
        "project": raw.get("project"),
        "labels": raw.get("labels", raw.get("tags", [])),
        "created": raw.get("created", raw.get("createdAt")),
        "updated": raw.get("updated", raw.get("updatedAt")),
    }
    context = {k: v for k, v in context.items() if v is not None}
    goal = raw.get("goal") or symptoms.get("title") or "Resolve ticket"
    budget = _default_budget()
    if "budget" in raw and isinstance(raw["budget"], dict):
        budget = Budget(**_default_budget().model_dump() | raw["budget"])
    return Task(
        task_id=str(task_id),
        source="ticket",
        symptoms=symptoms,
        context=context,
        constraints=raw.get("constraints", {}),
        goal=goal,
        budget=budget,
    )


def _normalize_chat(raw: dict[str, Any]) -> Task:
    """将类似ChatGPT风格的聊天数据转换为Task格式。转换非常宽松"""
    task_id = raw.get("task_id") or _task_id("chat")
    message = (
        raw.get("message")
        or raw.get("query")
        or raw.get("text")
        or raw.get("question")
        or raw.get("prompt")
        or raw.get("content")
        or ""
    )
    if not message and isinstance(raw.get("body"), str):
        message = raw["body"]
    symptoms = {"message": message, "user": raw.get("user", raw.get("userId"))}
    symptoms = {k: v for k, v in symptoms.items() if v is not None}
    _skip = ("message", "query", "text", "question", "prompt", "content", "body", "task_id", "budget", "constraints")
    context = {k: v for k, v in raw.items() if k not in _skip}
    goal = raw.get("goal") or f"Answer or act on: {message[:200]}"
    budget = _default_budget()
    if "budget" in raw and isinstance(raw["budget"], dict):
        budget = Budget(**_default_budget().model_dump() | raw["budget"])
    return Task(
        task_id=task_id,
        source="chat",
        symptoms=symptoms,
        context=context,
        constraints=raw.get("constraints", {}),
        goal=goal,
        budget=budget,
    )


def _normalize_cron(raw: dict[str, Any]) -> Task:
    """将类似Cron风格的定时任务数据转换为Task格式。"""
    task_id = raw.get("task_id") or _task_id("cron")
    symptoms = {
        "job": raw.get("job", raw.get("job_name", raw.get("name", ""))),
        "schedule": raw.get("schedule", raw.get("cron")),
        "params": raw.get("params", raw.get("args", {})),
    }
    symptoms = {k: v for k, v in symptoms.items() if v is not None}
    context = {k: v for k, v in raw.items() if k not in ("task_id", "budget", "constraints", "job", "job_name", "name", "schedule", "cron", "params", "args")}
    goal = raw.get("goal") or f"Run scheduled job: {symptoms.get('job', 'cron')}"
    budget = _default_budget()
    if "budget" in raw and isinstance(raw["budget"], dict):
        budget = Budget(**_default_budget().model_dump() | raw["budget"])
    return Task(
        task_id=task_id,
        source="cron",
        symptoms=symptoms,
        context=context,
        constraints=raw.get("constraints", {}),
        goal=goal,
        budget=budget,
    )

#将输入数据类型和对应的函数对应起来，方便后续使用。
_NORMALIZERS: dict[SourceType, Any] = {
    "alert": _normalize_alert,
    "ticket": _normalize_ticket,
    "chat": _normalize_chat,
    "cron": _normalize_cron,
}


def ingest(raw: dict[str, Any], source: SourceType) -> Task:
    """
    入口函数，将原始输入数据（alert告警, ticket工单, chat聊天, cron定时任务）转换为统一标准Task格式。
    raw: JSON-like dict from webhook/API/CLI.
    source: 输入数据类型，可以是alert, ticket, chat, cron。
    """
    if source not in _NORMALIZERS:
        raise ValueError(f"Unknown source: {source}. Must be one of {list(_NORMALIZERS.keys())}")
    return _NORMALIZERS[source](raw)
