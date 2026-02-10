#!/usr/bin/env python
"""
Sentinel Web UI - ModelScope Entry Point

This is the main entry point for running Sentinel on ModelScope.
"""

import os
import sys
import subprocess

# Set environment variables for Streamlit
os.environ['STREAMLIT_SERVER_PORT'] = '7860'
os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'

# Set default LLM provider to mock if not specified
if 'SENTINEL_LLM_PROVIDER' not in os.environ:
    os.environ['SENTINEL_LLM_PROVIDER'] = 'mock'

# Map environment variables from ModelScope format (XXX_KEY) to Sentinel format
# ModelScope uses: MODELSCOPE_KEY, DASHSCOPE_KEY, SILICONFLOW_KEY
# Sentinel uses: MODELSCOPE_API_KEY, DASHSCOPE_API_KEY, SILICONFLOW_API_KEY

if 'MODELSCOPE_KEY' in os.environ and 'MODELSCOPE_API_KEY' not in os.environ:
    os.environ['MODELSCOPE_API_KEY'] = os.environ['MODELSCOPE_KEY']
    print(f"✓ Loaded MODELSCOPE_API_KEY from MODELSCOPE_KEY")

if 'DASHSCOPE_KEY' in os.environ and 'DASHSCOPE_API_KEY' not in os.environ:
    os.environ['DASHSCOPE_API_KEY'] = os.environ['DASHSCOPE_KEY']
    print(f"✓ Loaded DASHSCOPE_API_KEY from DASHSCOPE_KEY")

if 'SILICONFLOW_KEY' in os.environ and 'SILICONFLOW_API_KEY' not in os.environ:
    os.environ['SILICONFLOW_API_KEY'] = os.environ['SILICONFLOW_KEY']
    print(f"✓ Loaded SILICONFLOW_API_KEY from SILICONFLOW_KEY")

if 'OPENAI_KEY' in os.environ and 'OPENAI_API_KEY' not in os.environ:
    os.environ['OPENAI_API_KEY'] = os.environ['OPENAI_KEY']
    print(f"✓ Loaded OPENAI_API_KEY from OPENAI_KEY")

# Print configuration
print("=" * 80)
print("🚀 Starting Sentinel Web UI on ModelScope")
print("=" * 80)
print(f"Server: 0.0.0.0:7860")
print(f"LLM Provider: {os.environ.get('SENTINEL_LLM_PROVIDER', 'mock')}")
print(f"LLM Model: {os.environ.get('SENTINEL_LLM_MODEL', 'N/A')}")
print("=" * 80)

# Create necessary directories
os.makedirs('runs', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Run Streamlit
if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "web_ui/app.py",
        "--server.port=7860",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ])
