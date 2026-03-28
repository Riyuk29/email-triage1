# Email Triage OpenEnv - Dockerfile
# Compatible with Hugging Face Spaces (port 7860)

FROM python:3.11-slim

# Metadata
LABEL maintainer="openenv-email-triage"
LABEL description="Email Triage OpenEnv - Real-world RL environment for email classification"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY server/ ./server/
COPY baseline.py .
COPY data.py .
COPY environment.py .
COPY graders.py .
COPY models.py .
COPY openenv.yaml .

# Create non-root user for security
RUN useradd -m -u 1000 appuser
USER appuser

# Expose port (7860 for HF Spaces, 8000 for local)
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Environment variables with defaults
ENV PORT=7860
ENV HOST=0.0.0.0
ENV WORKERS=2

# Start server
CMD uvicorn app:app \
    --host ${HOST} \
    --port ${PORT} \
    --workers ${WORKERS} \
    --log-level info
