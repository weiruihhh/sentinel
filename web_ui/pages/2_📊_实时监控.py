"""
实时监控 - 诊断任务执行监控页面
"""

import streamlit as st
import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web_ui.backend.runner import get_task_status, get_running_tasks, get_workflow_progress

st.set_page_config(
    page_title="实时监控 - Sentinel",
    page_icon="📊",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .stage-box {
        background: rgba(78, 205, 196, 0.1);
        border-left: 4px solid #4ECDC4;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    .stage-pending {
        border-left-color: #ccc;
        background: rgba(200, 200, 200, 0.1);
    }
    .stage-running {
        border-left-color: #4ECDC4;
        background: rgba(78, 205, 196, 0.2);
        animation: pulse 2s infinite;
    }
    .stage-completed {
        border-left-color: #95E1D3;
        background: rgba(149, 225, 211, 0.1);
    }
    .stage-error {
        border-left-color: #F38181;
        background: rgba(243, 129, 129, 0.1);
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.9rem;
        font-weight: 600;
    }
    .status-running {
        background: #4ECDC4;
        color: white;
    }
    .status-completed {
        background: #95E1D3;
        color: #333;
    }
    .status-failed {
        background: #F38181;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">📊 实时监控</div>', unsafe_allow_html=True)

# Check if there's a current task
if "current_task_id" not in st.session_state:
    st.info("ℹ️ 当前没有正在执行的任务")

    # Show all running tasks
    running_tasks = get_running_tasks()
    if running_tasks:
        st.markdown("### 🔄 正在运行的任务")
        for task_id, task_info in running_tasks.items():
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**Task ID**: {task_id}")
            with col2:
                st.write(f"**状态**: {task_info['status']}")
            with col3:
                if st.button("查看", key=f"view_{task_id}"):
                    st.session_state.current_task_id = task_id
                    st.rerun()
    else:
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; padding: 2rem;">
            <p style="font-size: 1.2rem; color: #888;">
                👈 请前往 <strong>🆕 新建诊断</strong> 页面创建新任务
            </p>
        </div>
        """, unsafe_allow_html=True)
    st.stop()

# Get current task
task_id = st.session_state.current_task_id
task_info = get_task_status(task_id)

if not task_info:
    st.error(f"❌ 任务不存在: {task_id}")
    if st.button("返回"):
        del st.session_state.current_task_id
        st.rerun()
    st.stop()

# Task header
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown(f"### 任务 ID: `{task_id}`")
with col2:
    status = task_info["status"]
    if status == "running":
        st.markdown('<span class="status-badge status-running">🔄 运行中</span>', unsafe_allow_html=True)
    elif status == "completed":
        st.markdown('<span class="status-badge status-completed">✅ 已完成</span>', unsafe_allow_html=True)
    elif status == "failed":
        st.markdown('<span class="status-badge status-failed">❌ 失败</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="status-badge">{status}</span>', unsafe_allow_html=True)
with col3:
    if st.button("🔄 刷新"):
        st.rerun()

st.markdown("---")

# Get workflow progress
output_dir = task_info["output_dir"]
workflow_progress = get_workflow_progress(output_dir)

# Calculate overall progress
stage_names = ["detect", "triage", "investigate", "plan", "approve", "execute", "verify", "report"]
completed_stages = sum(1 for stage in stage_names if workflow_progress[stage]["status"] == "completed")
total_stages = len(stage_names)
progress_percent = completed_stages / total_stages

# Overall progress bar
st.markdown("### 📈 整体进度")
st.progress(progress_percent)
st.markdown(f"**{completed_stages}/{total_stages}** 阶段已完成 ({progress_percent*100:.0f}%)")

st.markdown("---")

# Workflow stages
st.markdown("### 🔄 工作流阶段")

stage_display = {
    "detect": {"name": "DETECT", "icon": "🔍", "desc": "标准化输入"},
    "triage": {"name": "TRIAGE", "icon": "🏷️", "desc": "分类和评估"},
    "investigate": {"name": "INVESTIGATE", "icon": "🔬", "desc": "收集证据"},
    "plan": {"name": "PLAN", "icon": "📋", "desc": "生成计划"},
    "approve": {"name": "APPROVE", "icon": "✅", "desc": "审批检查"},
    "execute": {"name": "EXECUTE", "icon": "⚡", "desc": "执行计划"},
    "verify": {"name": "VERIFY", "icon": "🔍", "desc": "验证结果"},
    "report": {"name": "REPORT", "icon": "📄", "desc": "生成报告"},
}

# Display stages in 2 columns
col1, col2 = st.columns(2)

for idx, stage in enumerate(stage_names):
    stage_info = workflow_progress[stage]
    display_info = stage_display[stage]

    status = stage_info["status"]
    status_class = f"stage-{status}"

    # Status icon
    if status == "completed":
        status_icon = "✅"
    elif status == "running":
        status_icon = "🔄"
    elif status == "error":
        status_icon = "❌"
    else:
        status_icon = "⏳"

    # Calculate duration
    duration_text = ""
    if stage_info["start"] and stage_info["end"]:
        try:
            start = datetime.fromisoformat(stage_info["start"])
            end = datetime.fromisoformat(stage_info["end"])
            duration = (end - start).total_seconds()
            duration_text = f" ({duration:.1f}s)"
        except:
            pass

    # Display in appropriate column
    target_col = col1 if idx % 2 == 0 else col2

    with target_col:
        st.markdown(f"""
        <div class="stage-box {status_class}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 1.5rem;">{display_info['icon']}</span>
                    <strong style="margin-left: 0.5rem;">{display_info['name']}</strong>
                    <span style="color: #888; margin-left: 0.5rem;">- {display_info['desc']}</span>
                </div>
                <div>
                    <span style="font-size: 1.2rem;">{status_icon}</span>
                    <span style="color: #888; font-size: 0.9rem;">{duration_text}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# Task timing information
st.markdown("### ⏱️ 执行时间")
col1, col2, col3 = st.columns(3)

with col1:
    start_time = task_info.get("start_time", "")
    if start_time:
        st.metric("开始时间", start_time.split("T")[1][:8] if "T" in start_time else start_time)

with col2:
    end_time = task_info.get("end_time", "")
    if end_time:
        st.metric("结束时间", end_time.split("T")[1][:8] if "T" in end_time else "运行中")
    else:
        st.metric("结束时间", "运行中")

with col3:
    if start_time and end_time:
        try:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)
            duration = (end - start).total_seconds()
            st.metric("总耗时", f"{duration:.1f}s")
        except:
            st.metric("总耗时", "计算中")
    else:
        st.metric("总耗时", "运行中")

# Error information
if task_info["status"] == "failed" and task_info.get("error"):
    st.markdown("---")
    st.markdown("### ❌ 错误信息")
    st.error(task_info["error"])

# Action buttons
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if task_info["status"] == "completed":
        if st.button("📄 查看完整报告", use_container_width=True, type="primary"):
            # Navigate to main page with this episode
            st.session_state.selected_episode = Path(output_dir).name
            st.switch_page("app.py")

with col2:
    if st.button("🔙 返回任务列表", use_container_width=True):
        del st.session_state.current_task_id
        st.rerun()

with col3:
    if st.button("🆕 创建新任务", use_container_width=True):
        del st.session_state.current_task_id
        st.switch_page("pages/1_🆕_新建诊断.py")

# Auto-refresh for running tasks
if task_info["status"] in ("starting", "running"):
    st.markdown("---")
    st.info("🔄 页面将每 3 秒自动刷新...")
    time.sleep(3)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9rem;">
    💡 提示：任务完成后可以在主页查看完整的诊断报告
</div>
""", unsafe_allow_html=True)
