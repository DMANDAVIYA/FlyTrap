FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Pod template database; pods copy it to /data/pod.db on start and on /_edge/reset.
RUN python -m app.seed --role pod --seed 1001 --out /templates/pod.db && mkdir -p /data
# Tests ride along so `docker run --rm flytrap-hlabs python -m pytest -q` works.
COPY pytest.ini ./
COPY tests ./tests
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
