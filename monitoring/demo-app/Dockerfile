FROM python:3.11-slim
# 安装 curl 供健康检查与 exec 测试用
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制app.py文件到/app目录
COPY app.py .

# Create logs directory
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8080

# Run application
CMD ["python", "app.py"]
