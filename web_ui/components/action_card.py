"""
Action card component for Sentinel Web UI.
Displays recommended actions and execution plans.
"""

import streamlit as st
from typing import Dict, List


def render_actions_section(plan: Dict):
    """
    Render recommended actions section.

    Args:
        plan: Plan object from report
    """
    st.markdown("## 💡 推荐动作")

    # Display hypotheses first
    hypotheses = plan.get('hypotheses', [])
    if hypotheses:
        st.markdown("### 🔍 根因假设")
        for i, hypothesis in enumerate(hypotheses, 1):
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(255, 107, 107, 0.1), rgba(78, 205, 196, 0.1));
                        border-radius: 10px; padding: 1rem; margin-bottom: 0.5rem;
                        border-left: 4px solid #4ECDC4;">
                <div style="font-weight: 600;">假设 {i}</div>
                <div style="margin-top: 0.5rem;">{hypothesis}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Display actions
    actions = plan.get('actions', [])
    if not actions:
        st.info("暂无推荐动作")
        return

    st.markdown("### ⚡ 执行计划")

    # Render action cards in columns
    cols_per_row = 3
    for i in range(0, len(actions), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(actions):
                with col:
                    render_action_card(actions[i + j], i + j)

    # Display risks
    risks = plan.get('risks', [])
    if risks:
        st.markdown("### ⚠️ 风险提示")
        for risk in risks:
            st.warning(f"⚠️ {risk}")

    # Display plan metadata
    with st.expander("📋 计划详情", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**预期效果**: {plan.get('expected_effect', 'N/A')}")
            st.write(f"**置信度**: {plan.get('confidence', 0) * 100:.0f}%")

        with col2:
            st.write(f"**需要审批**: {'是' if plan.get('approval_required') else '否'}")
            st.write(f"**预计耗时**: {plan.get('estimated_duration_seconds', 0)}秒")


def render_action_card(action: Dict, index: int):
    """
    Render a single action card.

    Args:
        action: Action object
        index: Card index
    """
    tool_name = action.get('tool_name', 'Unknown')
    risk_level = action.get('risk_level', 'unknown')
    executed = action.get('executed', False)
    dry_run = action.get('dry_run', True)

    # Risk level styling
    risk_colors = {
        'read_only': '#95E1D3',
        'safe_write': '#4ECDC4',
        'risky_write': '#F38181',
    }
    risk_color = risk_colors.get(risk_level, '#888')

    risk_labels = {
        'read_only': '只读',
        'safe_write': '安全写入',
        'risky_write': '高风险写入',
    }
    risk_label = risk_labels.get(risk_level, risk_level)

    # Tool icon mapping
    tool_icons = {
        'rollback': '🔄',
        'scale': '📈',
        'restart': '🔁',
        'monitor': '🔍',
        'deploy': '🚀',
    }
    icon = tool_icons.get(tool_name, '⚙️')

    # Card styling
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(255, 107, 107, 0.1), rgba(78, 205, 196, 0.1));
                border-radius: 10px; padding: 1.5rem;
                border: 2px solid {risk_color}; height: 100%;">
        <div style="text-align: center;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">{icon}</div>
            <div style="font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem;">{tool_name}</div>
            <div style="background: {risk_color}; color: #1a1a1a; padding: 0.25rem 0.75rem;
                        border-radius: 12px; font-size: 0.85rem; font-weight: 600; display: inline-block;">
                {risk_label}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action details
    with st.expander(f"📋 动作详情", expanded=False):
        args = action.get('args', {})
        if args:
            st.write("**参数**:")
            st.json(args)

        if executed:
            result = action.get('result', {})
            st.write("**执行结果**:")

            if dry_run:
                st.info(f"🔒 Dry-run模式: {result.get('message', 'N/A')}")
            else:
                status = result.get('status', 'unknown')
                if status == 'success':
                    st.success(f"✅ 执行成功")
                else:
                    st.error(f"❌ 执行失败")

            if result:
                st.write("**完整结果**:")
                st.json(result)

        error = action.get('error')
        if error:
            st.error(f"❌ 错误: {error}")

    # Action button (disabled for now)
    if not executed:
        st.button(
            "🚀 执行动作",
            key=f"action_{index}",
            disabled=True,
            help="执行功能开发中",
            use_container_width=True
        )
    else:
        if dry_run:
            st.success("✓ 已模拟执行", icon="🔒")
        else:
            st.success("✓ 已执行", icon="✅")
