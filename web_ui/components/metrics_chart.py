"""
Metrics chart component for Sentinel Web UI.
Renders interactive time-series charts for metrics data.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import List, Dict
import pandas as pd


def render_metrics_section(evidence_list: List[Dict]):
    """
    Render metrics charts from evidence data.

    Args:
        evidence_list: List of evidence items from report
    """
    st.markdown("## 📈 指标分析")

    # Find metrics evidence
    metrics_evidence = [e for e in evidence_list if e.get('source') == 'query_metrics']

    if not metrics_evidence:
        st.info("暂无指标数据")
        return

    # Create tabs for different metrics
    metric_names = [e.get('data', {}).get('metric', 'Unknown') for e in metrics_evidence]
    tabs = st.tabs([f"📊 {name}" for name in metric_names])

    for i, evidence in enumerate(metrics_evidence):
        with tabs[i]:
            render_metric_chart(evidence)


def render_metric_chart(evidence: Dict):
    """
    Render a single metric chart.

    Args:
        evidence: Evidence item containing metric data
    """
    data = evidence.get('data', {})
    metric_name = data.get('metric', 'Unknown')
    service = data.get('service', 'Unknown')
    data_points = data.get('data', [])

    if not data_points:
        st.warning("无数据点")
        return

    # Convert to DataFrame
    df = pd.DataFrame(data_points)

    # Filter out NaN values
    df = df[df['value'].notna()]

    if df.empty:
        st.warning("所有数据点均为NaN")
        return

    # Create Plotly figure
    fig = go.Figure()

    # Add main trace
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['value'],
        mode='lines+markers',
        name=metric_name,
        line=dict(color='#FF6B6B', width=2),
        marker=dict(size=4),
        hovertemplate='<b>%{y:.2f}</b><br>%{x}<extra></extra>'
    ))

    # Add threshold line if available
    aggregation = data.get('aggregation', {})
    max_value = aggregation.get('max')

    if max_value:
        fig.add_hline(
            y=max_value,
            line_dash="dash",
            line_color="#4ECDC4",
            annotation_text=f"峰值: {max_value:.2f}",
            annotation_position="right"
        )

    # Update layout
    fig.update_layout(
        title=f"{service} - {metric_name}",
        xaxis_title="时间",
        yaxis_title=metric_name,
        hovermode='x unified',
        template='plotly_dark',
        height=400,
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )

    # Display chart
    st.plotly_chart(fig, use_container_width=True)

    # Display statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("最大值", f"{df['value'].max():.2f}")

    with col2:
        st.metric("最小值", f"{df['value'].min():.2f}")

    with col3:
        st.metric("平均值", f"{df['value'].mean():.2f}")

    with col4:
        st.metric("数据点", len(df))

    # Show notes
    notes = evidence.get('notes', '')
    if notes:
        st.info(f"💡 {notes}")
