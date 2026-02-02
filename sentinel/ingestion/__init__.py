"""
入口函数，将原始输入数据（alert告警, ticket工单, chat聊天, cron定时任务）转换为统一标准Task格式。
"""

from sentinel.ingestion.normalizers import ingest

__all__ = ["ingest"]
