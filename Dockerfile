# Builder stage
FROM python:3.12-slim-bookworm AS builder

# Install uv binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (removed cache mount for Google Cloud Build compatibility)
RUN uv sync --frozen --no-install-project --no-dev

# Runner stage
FROM python:3.12-slim-bookworm AS runner

# Set the working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy the source code
COPY src/ /app/src/

# Add the virtual environment binaries to the system PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Ensure standard Python optimization variables are set
ENV PYTHONUNBUFFERED=1

# Expose port 8080 (GCP Cloud Run default)
EXPOSE 8080

# Start the production server dynamically binding to the PORT environment variable
CMD ["sh", "-c", "exec uvicorn portfolio_assistant.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
