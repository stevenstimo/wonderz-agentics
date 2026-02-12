FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY web-ui/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=10000
ENV PYTHONPATH=/app
ENV WEB_CONCURRENCY=1

# Run FastAPI with Gunicorn
CMD gunicorn -w ${WEB_CONCURRENCY} -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --chdir /app/web-ui/backend api_main:app
