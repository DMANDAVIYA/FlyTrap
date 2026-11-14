FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
RUN mkdir -p /app/runs

EXPOSE 8090
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz', timeout=2)"

# Live mode (events-db). For the no-database mock: CMD ["python", "mock_feed.py", "--host", "0.0.0.0"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
