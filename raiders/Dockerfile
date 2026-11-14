FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.34.0" httpx==0.28.1
COPY runner.py .
EXPOSE 8060
CMD ["uvicorn", "runner:app", "--host", "0.0.0.0", "--port", "8060", "--no-server-header"]
