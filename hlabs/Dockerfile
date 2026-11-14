FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY seed ./seed
COPY templates ./templates
COPY static ./static
COPY entrypoint.sh .
# The template every non-real instance copies on start and on reset.
RUN python -m app.seed --role pod --out /templates/pod.db
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["./entrypoint.sh"]
