# ColdChain AI — Dockerfile
# Phase 2: Containerization

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (Docker layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and assets
COPY api/ ./api/
COPY frontend/ ./frontend/
COPY models/ ./models/
COPY data/ ./data/

# Expose Flask port
EXPOSE 5000

# Health check for Docker / Kubernetes
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

# Run with Gunicorn in production (not Flask dev server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "api.app:app"]
