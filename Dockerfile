# Production image for Render / any Docker host
FROM python:3.11-slim

# Prevent Python from writing pyc and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Production defaults; Render sets PORT at runtime
ENV FLASK_ENV=production
ENV DEBUG=False
ENV PORT=10000

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY config.py .
COPY app ./app
COPY templates ./templates
COPY static ./static

# Render sets PORT at runtime; container must bind to 0.0.0.0:$PORT for port detection.
# EXPOSE documents the typical Render port (actual port is $PORT at runtime).
EXPOSE 10000

# Use shell so $PORT is expanded from Render's environment at container start.
# App is a factory: "app:create_app" (no top-level "app" in this project).
CMD ["sh", "-c", "gunicorn app:create_app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120"]
