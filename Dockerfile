# HyperSwipe Server Dockerfile
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Create non-root user
RUN groupadd --gid 1000 hyperswipe && \
    useradd --uid 1000 --gid hyperswipe --shell /bin/bash --create-home hyperswipe

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=hyperswipe:hyperswipe . .

# Create logs directory
RUN mkdir -p logs && chown hyperswipe:hyperswipe logs

# Switch to non-root user
USER hyperswipe

# Expose port
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Default command
CMD ["python", "run.py"]