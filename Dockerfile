FROM python:3.11-slim

# Optional build flag to skip heavy deep-learning deps (torch, etc.)
# Build with: docker build --build-arg INSTALL_DL=0 .
ARG INSTALL_DL=1

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
COPY requirements-pg.txt .
COPY requirements-dl-train.txt .
COPY requirements-dl.txt .

# Use BuildKit cache to avoid re-downloading wheels on rebuilds.
# (Docker Desktop / modern Docker enables BuildKit by default; otherwise set DOCKER_BUILDKIT=1)
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install -r requirements.txt \
  && pip install -r requirements-pg.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "${INSTALL_DL}" = "1" ]; then \
      pip install -r requirements-dl-train.txt; \
    else \
      echo "[INFO] Skipping DL deps (INSTALL_DL=${INSTALL_DL})"; \
    fi

# Copy application files
COPY app.py .
COPY modules ./modules
COPY static ./static

# Create directory for database
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE=/app/data/currency_monitor.db

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/api/monitoring/status', timeout=5)"

# Run the application
CMD ["python", "-u", "app.py"]
