FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.34.0" httpx==0.28.1 docker==7.1.0
COPY app.py .
EXPOSE 8050
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8050", "--no-server-header"]
