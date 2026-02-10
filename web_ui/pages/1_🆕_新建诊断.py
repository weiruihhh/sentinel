"""
新建诊断 - 交互式表单页面
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web_ui.backend.runner import run_diagnosis_async

st.set_page_config(
    page_title="新建诊断 - Sentinel",
    page_icon="🆕",
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
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #4ECDC4;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #4ECDC4;
        padding-bottom: 0.5rem;
    }
    .info-box {
        background: rgba(78, 205, 196, 0.1);
        border-left: 4px solid #4ECDC4;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🆕 新建诊断任务</div>', unsafe_allow_html=True)
st.markdown("配置并启动一个新的故障诊断任务")

# Initialize session state
if "diagnosis_started" not in st.session_state:
    st.session_state.diagnosis_started = False

# Main form
with st.form("diagnosis_form"):
    # Section 1: Task Configuration
    st.markdown('<div class="section-header">📋 任务配置</div>', unsafe_allow_html=True)

    # 问题来源：预定义 = 只选场景，不描述；自定义 = 自己描述问题
    input_mode = st.radio(
        "问题来源",
        ["预定义场景", "自定义问题"],
        help="预定义场景：从下列场景中选择，无需再描述；自定义问题：需要自己描述遇到的问题。"
    )

    if input_mode == "预定义场景":
        st.markdown("**选择预定义场景**（选择后无需再描述问题）")
        scenario = st.selectbox(
            "选择场景",
            ["latency_spike", "cpu_thrash"],
            format_func=lambda x: {
                "latency_spike": "🐌 API 延迟飙升",
                "cpu_thrash": "🔥 CPU 使用率过高"
            }[x],
            label_visibility="collapsed"
        )
        message = None
    else:
        st.markdown("**描述你的问题**（请尽量写清现象与环境）")
        scenario = None
        message = st.text_area(
            "问题描述",
            placeholder="例如：auth-service 的 CPU 使用率突然升高到 95%，请帮我诊断原因",
            height=100,
            help="仅在选择「自定义问题」时需要填写；选择预定义场景时不会出现本框。",
            label_visibility="collapsed"
        )

    # Section 2: LLM Configuration
    st.markdown('<div class="section-header">🤖 LLM 配置</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        llm_provider = st.selectbox(
            "LLM Provider",
            ["mock", "local_model", "qwen", "siliconflow", "modelscope"],
            format_func=lambda x: {
                "mock": "🎭 Mock (测试用)",
                "local_model": "💻 本地模型 (LoRA)",
                "qwen": "☁️ 通义千问 (API)",
                "siliconflow": "🌊 硅基流动 (API)",
                "modelscope": "🚀 ModelScope (API)"
            }[x],
            help="选择 LLM 提供商"
        )

    with col2:
        if llm_provider == "mock":
            llm_model = st.text_input("模型名称", value="mock-llm-v1", disabled=True)
        elif llm_provider == "local_model":
            llm_model = st.text_input("模型名称", value="local", help="本地模型标识")
        elif llm_provider == "qwen":
            llm_model = st.text_input("模型名称", value="qwen-plus", help="例如: qwen-plus, qwen-turbo")
        elif llm_provider == "siliconflow":
            llm_model = st.text_input("模型名称", value="Qwen/Qwen2.5-7B-Instruct", help="例如: Qwen/Qwen2.5-7B-Instruct")
        else:  # modelscope
            llm_model = st.text_input("模型名称", value="Qwen/Qwen3-Coder-480B-A35B-Instruct", help="例如: Qwen/Qwen3-Coder-480B-A35B-Instruct")

    # Provider-specific configuration
    if llm_provider == "local_model":
        st.markdown("**本地模型配置**")
        col1, col2 = st.columns(2)
        with col1:
            llm_adapter_path = st.text_input(
                "Adapter Path",
                placeholder="/path/to/lora/adapter",
                help="LoRA adapter 目录路径（必填）"
            )
        with col2:
            llm_base_model_path = st.text_input(
                "Base Model Path",
                placeholder="/path/to/base/model (可选)",
                help="基础模型路径，如果 adapter 目录有 adapter_config.json 则可省略"
            )
        llm_api_key = ""
        llm_api_base = ""

    elif llm_provider in ["qwen", "siliconflow", "modelscope"]:
        st.markdown("**API 配置**")
        col1, col2 = st.columns(2)
        with col1:
            api_key_help = {
                "qwen": "DASHSCOPE_API_KEY",
                "siliconflow": "SILICONFLOW_API_KEY",
                "modelscope": "MODELSCOPE_API_KEY"
            }
            llm_api_key = st.text_input(
                "API Key",
                type="password",
                help=api_key_help.get(llm_provider, "API Key")
            )
        with col2:
            llm_api_base = st.text_input(
                "API Base URL (可选)",
                placeholder="留空使用默认值",
                help="自定义 API endpoint"
            )
        llm_adapter_path = ""
        llm_base_model_path = ""

    else:  # mock
        llm_api_key = ""
        llm_api_base = ""
        llm_adapter_path = ""
        llm_base_model_path = ""

    # Section 3: Data Sources
    st.markdown('<div class="section-header">🔧 数据源配置</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        use_real_tools = st.checkbox(
            "使用真实数据源",
            value=False,
            help="启用后将连接真实的 Prometheus、Loki 等数据源，否则使用模拟数据"
        )

    with col2:
        execute_mode = st.checkbox(
            "执行写操作",
            value=False,
            help="启用后将真实执行 scale、restart 等操作，否则仅模拟（Dry Run）"
        )

    if use_real_tools:
        st.markdown("**数据源 URLs**")
        col1, col2, col3 = st.columns(3)
        with col1:
            prometheus_url = st.text_input(
                "Prometheus URL",
                value="http://localhost:9091",
                help="Prometheus 服务器地址"
            )
        with col2:
            loki_url = st.text_input(
                "Loki URL",
                value="http://localhost:3100",
                help="Loki 日志服务器地址"
            )
        with col3:
            cmdb_url = st.text_input(
                "CMDB URL",
                placeholder="http://cmdb.example.com",
                help="CMDB API 地址（可选）"
            )
    else:
        prometheus_url = ""
        loki_url = ""
        cmdb_url = ""

    # Warning boxes
    if execute_mode:
        st.markdown("""
        <div class="info-box" style="border-left-color: #F38181; background: rgba(243, 129, 129, 0.1);">
            ⚠️ <strong>警告</strong>: 已启用写操作执行模式，系统将真实执行 scale、restart 等操作！
        </div>
        """, unsafe_allow_html=True)

    if not use_real_tools:
        st.markdown("""
        <div class="info-box">
            ℹ️ <strong>提示</strong>: 当前使用模拟数据源，诊断结果仅供演示参考
        </div>
        """, unsafe_allow_html=True)

    # Submit button
    st.markdown("---")
    submitted = st.form_submit_button(
        "🚀 开始诊断",
        use_container_width=True,
        type="primary"
    )

# Handle form submission
if submitted:
    # Validation
    errors = []

    if input_mode == "自定义问题" and not message:
        errors.append("请输入问题描述")

    if llm_provider == "local_model" and not llm_adapter_path:
        errors.append("本地模型需要提供 Adapter Path")

    if llm_provider in ["qwen", "siliconflow"] and not llm_api_key:
        errors.append(f"{llm_provider.upper()} 需要提供 API Key")

    if errors:
        for error in errors:
            st.error(f"❌ {error}")
    else:
        # Start diagnosis
        with st.spinner("正在启动诊断任务..."):
            try:
                task_id = run_diagnosis_async(
                    scenario=scenario,
                    message=message,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    llm_api_key=llm_api_key,
                    llm_api_base=llm_api_base,
                    llm_adapter_path=llm_adapter_path,
                    llm_base_model_path=llm_base_model_path,
                    use_real_tools=use_real_tools,
                    execute_mode=execute_mode,
                    prometheus_url=prometheus_url,
                    loki_url=loki_url,
                    cmdb_url=cmdb_url,
                )

                # Store task_id in session state
                st.session_state.current_task_id = task_id
                st.session_state.diagnosis_started = True

                st.success(f"✅ 诊断任务已启动！Task ID: {task_id}")
                st.info("👉 请前往 **📊 实时监控** 页面查看执行进度")

                # Show link to monitoring page
                st.markdown("""
                <div style="text-align: center; margin-top: 2rem;">
                    <a href="/2_📊_实时监控" target="_self" style="
                        display: inline-block;
                        padding: 1rem 2rem;
                        background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
                        color: white;
                        text-decoration: none;
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 1.2rem;
                    ">
                        📊 查看实时监控
                    </a>
                </div>
                """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"❌ 启动失败: {str(e)}")
                import traceback
                with st.expander("查看详细错误"):
                    st.code(traceback.format_exc())

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9rem;">
    💡 提示：诊断任务将在后台异步执行，你可以在实时监控页面查看进度
</div>
""", unsafe_allow_html=True)
