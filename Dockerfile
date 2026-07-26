FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NMRCP_HOST=0.0.0.0 \
    NMRCP_PORT=8080 \
    NMRCP_SITE_DIR=/data/console-site

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples

RUN python -m pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin nmrcp \
    && mkdir -p /data \
    && chown -R nmrcp:nmrcp /data /app

USER nmrcp

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)); raise SystemExit(0 if data.get('status') == 'ok' else 1)"

CMD ["sh", "-c", "nmrcp serve --host ${NMRCP_HOST} --port ${NMRCP_PORT} --site-dir ${NMRCP_SITE_DIR}"]
