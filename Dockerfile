# ── Super-MCP Production Dockerfile ─────────────────
# Multi-stage build for minimal image size (<500MB)
# Usage:
#   docker build -t super-mcp .
#   docker run -it --rm super-mcp
# ────────────────────────────────────────────────────

# ── Stage 1: Build ──────────────────────────────────

FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy only dependency specification first (cache layer)
COPY pyproject.toml README.md LICENSE ./

# Install dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy source code
COPY src/ ./src/
COPY skills/ ./skills/
COPY README.md LICENSE ./

# Install the package itself
RUN pip install --no-cache-dir .

# ── Stage 2: Runtime ────────────────────────────────

FROM python:3.12-slim AS runtime

# Security: run as non-root
RUN groupadd -r smcp && useradd -r -g smcp -d /app -s /sbin/nologin smcp

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --from=builder /build/src/ ./src/
COPY --from=builder /build/skills/ ./skills/
COPY --from=builder /build/pyproject.toml ./
COPY --from=builder /build/README.md ./
COPY --from=builder /build/LICENSE ./

# Create data directories
RUN mkdir -p /app/data/checkpoints /app/data/exports /app/data/replays && \
    chown -R smcp:smcp /app

# Environment defaults
ENV SMCP_ENV=production \
    SMCP_LOG_LEVEL=INFO \
    SMCP_LOG_FORMAT=json \
    SMCP_DATA_DIR=/app/data \
    SMCP_SKILLS_DIR=/app/skills \
    SMCP_METRICS_ENABLED=true \
    SMCP_SAFETY_ENABLED=true

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "from src.kernel.kernel import Kernel; print('ok')"]

# Expose metrics port
EXPOSE 9090

# Switch to non-root user
USER smcp

# Default: launch the TUI
ENTRYPOINT ["smcp"]
CMD ["tui"]
