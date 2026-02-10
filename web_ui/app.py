"""
Sentinel Web UI - Main Application
AI-powered datacenter operations diagnosis system
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from web_ui.utils.data_loader import list_episodes, load_episode, get_latest_episode, format_timestamp
from web_ui.components.workflow_viz import render_workflow
from web_ui.components.evidence_card import render_evidence_section
from web_ui.components.action_card import render_actions_section
from web_ui.components.metrics_chart import render_metrics_section


# Page configuration
st.set_page_config(
    page_title="Sentinel - AI运维诊断系统",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-color: #FF6B6B;
        --secondary-color: #4ECDC4;
        --success-color: #95E1D3;
        --warning-color: #F38181;
    }

    /* Header styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(120deg, #FF6B6B, #4ECDC4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }

    .sub-header {
        font-size: 1.2rem;
        color: #888;
        margin-bottom: 2rem;
    }

    /* Card styling */
    .stCard {
        border-radius: 10px;
        padding: 1.5rem;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 1rem;
    }

    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }

    .status-success {
        background: #95E1D3;
        color: #1a1a1a;
    }

    .status-running {
        background: #4ECDC4;
        color: #1a1a1a;
    }

    .status-error {
        background: #F38181;
        color: #1a1a1a;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, rgba(255, 107, 107, 0.1), rgba(78, 205, 196, 0.1));
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #FF6B6B;
    }

    .metric-label {
        font-size: 0.9rem;
        color: #888;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def render_sidebar():
    """Render sidebar with episode selection."""
    with st.sidebar:
        st.markdown('<div class="main-header">🛡️ Sentinel</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">AI运维诊断系统</div>', unsafe_allow_html=True)

        st.divider()

        # Quick actions
        st.subheader("🚀 快速操作")
        if st.button("🆕 新建诊断", use_container_width=True, type="primary"):
            st.switch_page("pages/1_🆕_新建诊断.py")
        if st.button("📊 实时监控", use_container_width=True):
            st.switch_page("pages/2_📊_实时监控.py")

        st.divider()

        # Historical episodes
        st.subheader("📚 历史案例")
        episodes = list_episodes()

        if not episodes:
            st.warning("暂无历史案例")
            st.info("💡 点击上方「新建诊断」创建任务")
            return None

        # Display episode list
        selected_idx = st.selectbox(
            "案例列表",
            range(len(episodes)),
            format_func=lambda i: f"{episodes[i]['service']} - {episodes[i]['scenario']} ({format_timestamp(episodes[i]['timestamp'])})",
            label_visibility="collapsed"
        )

        selected_episode = episodes[selected_idx]

        # Show episode info
        with st.expander("📋 案例信息", expanded=False):
            st.write(f"**ID**: {selected_episode['episode_id']}")
            st.write(f"**服务**: {selected_episode['service']}")
            st.write(f"**场景**: {selected_episode['scenario']}")
            st.write(f"**时间**: {format_timestamp(selected_episode['timestamp'])}")

        # Load button
        if st.button("🔍 加载案例", type="secondary", use_container_width=True):
            return load_episode(selected_episode['path'])

        # Auto-load latest
        if 'current_episode' not in st.session_state:
            st.session_state.current_episode = load_episode(selected_episode['path'])

        return st.session_state.current_episode


def render_task_overview(data: dict):
    """Render task overview section."""
    episode = data.get('episode', {})
    task = episode.get('task', {})
    symptoms = task.get('symptoms', {})

    st.markdown("## 📋 任务概览")

    # Key metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{symptoms.get('service', 'N/A')}</div>
            <div class="metric-label">服务名称</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        severity = symptoms.get('severity', 'unknown')
        severity_color = {'high': '#F38181', 'medium': '#F9CA24', 'low': '#95E1D3'}.get(severity, '#888')
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: {severity_color};">{severity.upper()}</div>
            <div class="metric-label">严重程度</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        current_value = symptoms.get('current_value', 0)
        threshold = symptoms.get('threshold', 0)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{current_value}</div>
            <div class="metric-label">{symptoms.get('metric', 'Metric')} (阈值: {threshold})</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        outcome = episode.get('outcome', {})
        duration = outcome.get('total_time_seconds', 0)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{duration:.1f}s</div>
            <div class="metric-label">诊断耗时</div>
        </div>
        """, unsafe_allow_html=True)

    # Task details
    with st.expander("🔍 详细信息", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**告警名称**:", symptoms.get('alert_name', 'N/A'))
            st.write("**持续时间**:", symptoms.get('duration', 'N/A'))
            st.write("**任务目标**:", task.get('goal', 'N/A'))

        with col2:
            context = task.get('context', {})
            st.write("**服务负责人**:", context.get('service_owner', 'N/A'))
            st.write("**近期变更**:", context.get('recent_changes', 'N/A'))
            st.write("**影响范围**:", context.get('affected_users', 'N/A'))


def main():
    """Main application entry point."""

    # Render sidebar and get selected episode
    data = render_sidebar()

    if not data:
        # Show welcome screen
        st.markdown('<div class="main-header">🛡️ Sentinel AI运维诊断系统</div>', unsafe_allow_html=True)
        st.markdown("""
        ### 欢迎使用 Sentinel

        Sentinel 是一个基于 Multi-Agent 的智能运维诊断系统，能够:

        - 🔍 **自动诊断**: 分析告警、收集证据、定位根因
        - 🤖 **Multi-Agent协同**: Triage → Investigation → Planning → Execution
        - 📊 **可视化展示**: 实时展示诊断过程和结果
        - 🛡️ **安全可控**: 风险分级、权限控制、审批流程

        ---

        **快速开始**:
        1. 👈 点击侧边栏「🆕 新建诊断」创建新任务
        2. 或在侧边栏选择「📚 历史案例」查看已有诊断
        3. 支持自定义问题输入和 LLM 选择（本地模型/API）
        """)

        # Show architecture diagram
        st.image("https://via.placeholder.com/800x400/1a1a1a/ffffff?text=Sentinel+Architecture",
                 caption="Sentinel 系统架构")

        return

    # Main content area
    render_task_overview(data)

    st.divider()

    # Workflow visualization
    if 'trace' in data:
        render_workflow(data['trace'])

    st.divider()

    # Evidence and metrics
    if 'report' in data:
        report = data['report']

        # Metrics charts
        render_metrics_section(report.get('evidence', []))

        st.divider()

        # Evidence cards
        render_evidence_section(report.get('evidence', []))

        st.divider()

        # Recommended actions
        render_actions_section(report.get('plan', {}))

    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #888; padding: 2rem 0;">
        🛡️ Sentinel AI运维诊断系统 | Powered by Multi-Agent Architecture
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
