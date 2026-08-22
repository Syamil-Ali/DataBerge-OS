FROM python:3.12.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATA_DIR=/data \
    DB_PATH=/data/app.db

WORKDIR /app
COPY requirements.lock.txt ./requirements.lock.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.lock.txt

COPY app ./app
COPY data_berge_core ./data_berge_core
COPY scripts ./scripts
COPY run.py ./run.py
COPY entrypoint.sh ./entrypoint.sh

RUN addgroup --system --gid 10001 appgroup \
    && adduser --system --uid 10001 --ingroup appgroup appuser \
    && mkdir -p /data/uploads /data/artifacts \
    && chown -R appuser:appgroup /app /data \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health/ready',timeout=3)"
ENTRYPOINT ["/app/entrypoint.sh"]
