FROM node:18-alpine as frontend-builder
WORKDIR /app/web_ui/frontend
COPY web_ui/frontend/package.json web_ui/frontend/package-lock.json ./
RUN npm install -q
COPY web_ui/frontend/src ./src
COPY web_ui/frontend/*.jsx ./
COPY web_ui/frontend/index.html ./
COPY web_ui/frontend/vite.config.js ./
COPY web_ui/frontend/tailwind.config.js ./
COPY web_ui/frontend/postcss.config.js ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY web_ui/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application
COPY . .

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/web_ui/frontend/dist ./web_ui/frontend/dist

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=10000
ENV PYTHONPATH=/app
ENV WEB_CONCURRENCY=1

# Run FastAPI with Gunicorn
CMD gunicorn -w ${WEB_CONCURRENCY} -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --chdir /app/web_ui/backend api_main:app
