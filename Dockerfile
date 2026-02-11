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

# Run FastAPI with Gunicorn
CMD gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT web_ui.backend.api_main:app
