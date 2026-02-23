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

# App factory fix: Gunicorn needs a WSGI app instance, not the factory. wsgi.py does application = create_app().
# Using app:create_app would make Gunicorn call create_app(environ, start_response) -> TypeError (0 args but 2 given).
# Using 'app:create_app()' is invalid: Gunicorn looks for an attribute named "create_app()", which does not exist.
CMD ["sh", "-c", "gunicorn wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120"]
