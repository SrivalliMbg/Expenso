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
COPY wsgi.py .
COPY app ./app
COPY templates ./templates
COPY static ./static

# Render sets PORT at runtime; container must bind to 0.0.0.0:$PORT for port detection.
EXPOSE 10000

# wsgi:application is the WSGI app instance (create_app() called in wsgi.py). Do not use app:create_app
# or Gunicorn will call create_app(environ, start_response) and raise "takes 0 positional arguments but 2 were given".
CMD ["sh", "-c", "gunicorn wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120"]
