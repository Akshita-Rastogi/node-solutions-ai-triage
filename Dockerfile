FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY ui ./ui
COPY scripts ./scripts
COPY data ./data
COPY tests ./tests

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "triage.main:app", "--host", "0.0.0.0", "--port", "8000"]
