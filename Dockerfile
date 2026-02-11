# Multi-stage build for minimal image size
FROM python:3.13-slim AS builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user cryptography

# Final stage
FROM python:3.13-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy only necessary files for server
COPY server.py .
COPY protocol.py .

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Expose IRC port
EXPOSE 6667

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 6667)); s.close()" || exit 1

# Run server
CMD ["python", "-u", "server.py", "--host", "0.0.0.0", "--port", "6667"]
