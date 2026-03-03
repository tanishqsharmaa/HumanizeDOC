# Build context: repository root
# docker build -f humanizedoc/backend/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

COPY humanizedoc/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY humanizedoc/ humanizedoc/

EXPOSE 8000

CMD ["uvicorn", "humanizedoc.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source
COPY . .

# Create /tmp with correct permissions (writable by non-root user)
RUN mkdir -p /tmp && chmod 1777 /tmp

# Create a non-root user for security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
