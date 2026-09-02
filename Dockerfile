# All comments are strictly in English.
# Lines are wrapped to stay within the 88-character limit.

# Builder stage - Reverted to stable Python 3.12 to ensure Docker Hub image availability
FROM python:3.12-slim-bookworm AS builder

# Install uv binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (removed cache mount for Google Cloud Build compatibility)
RUN uv sync --frozen --no-install-project --no-dev

# Runner stage - Reverted to stable Python 3.12
FROM python:3.12-slim-bookworm AS runner

# Create a secure non-root user for production execution
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/bash appuser

# Set the working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy the migrations and configuration files needed for Alembic
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/

# Copy the source code
COPY src/ /app/src/

# Create the SQLite data directory and set ownership to the non-root user
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Add the virtual environment binaries to the system PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Configure SRE environment variables
ENV PYTHONUNBUFFERED=1
ENV ALEMBIC_CONFIG_PATH="/app/alembic.ini"

# Switch to the non-root user for secure, least-privilege runtime execution
USER appuser

# Expose port 8080 (GCP Cloud Run default)
EXPOSE 8080

# Start the production server dynamically binding to the PORT environment variable
CMD ["sh", "-c", "exec uvicorn portfolio_assistant.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
