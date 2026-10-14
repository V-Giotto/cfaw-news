FROM node:24-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.lock pyproject.toml LICENSE NOTICE ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ backend/
COPY data/ data/
COPY frontend/public/ frontend/public/
COPY --from=web /web/dist/ frontend/dist/
RUN pip install --no-deps -e .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "cfaw_news.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
