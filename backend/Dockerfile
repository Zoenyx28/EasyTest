FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (git for project sync, openssh-client for git over SSH, curl for healthcheck)
RUN sed -i 's|deb.debian.org|mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create directories for project data and logs
RUN mkdir -p /data /app/logs && chmod 777 /data /app/logs

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /data

# Configure SSH for Git operations
RUN mkdir -p /home/appuser/.ssh && chmod 700 /home/appuser/.ssh && chown appuser:appuser /home/appuser/.ssh
RUN echo "Host *\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null" > /home/appuser/.ssh/config && chown appuser:appuser /home/appuser/.ssh/config

USER appuser

# Set Python env
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Default: start API server
# Override CMD for celery worker: celery -A app.scheduler.celery_app worker --loglevel=info --concurrency=2
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]