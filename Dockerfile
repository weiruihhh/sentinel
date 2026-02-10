FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /home/user/app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy project files
COPY sentinel/ ./sentinel/
COPY web_ui/ ./web_ui/
COPY main.py .
COPY app.py .

# Create necessary directories
RUN mkdir -p /home/user/app/runs /home/user/app/logs

# Expose port (ModelScope standard port)
EXPOSE 7860

# Set environment variables
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV SENTINEL_LLM_PROVIDER=mock

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/_stcore/health || exit 1

# Run application
ENTRYPOINT ["python", "-u", "app.py"]
