
# --- Multi-stage build: Frontend (Vite) + Backend (FastAPI) ---
FROM node:18-alpine as frontend-builder
WORKDIR /app/web_ui/frontend
COPY web_ui/frontend/package.json web_ui/frontend/package-lock.json ./
RUN npm install --silent
COPY web_ui/frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# Install git for repo-aware backend context features.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY web_ui/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy backend code
COPY web_ui/backend ./web_ui/backend
COPY models ./models
COPY tools ./tools
COPY app ./app
COPY config.py ./config.py

# Copy built frontend
COPY --from=frontend-builder /app/web_ui/frontend/dist ./web_ui/frontend/dist

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8090
ENV PYTHONPATH=/app
ENV WEB_CONCURRENCY=1

# Start FastAPI (app.main = full stack: GTM, knowledge, governance, events, etc.)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
