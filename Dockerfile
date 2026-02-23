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

# Gunicorn binds to PORT (Render sets this)
EXPOSE 10000
# Factory app: use "app:create_app" (callable name, no parentheses). Gunicorn calls it to get the WSGI app.
CMD gunicorn "app:create_app" --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120
