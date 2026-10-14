FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY pyproject.toml ./
COPY sql_analytics ./sql_analytics
RUN pip install --no-deps . && useradd --uid 10001 --create-home appuser
COPY scripts ./scripts
COPY sql ./sql
COPY ui ./ui
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "sql_analytics.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
