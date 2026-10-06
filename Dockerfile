FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/nucleo-ia \
    NUCLEO_DATA_DIR=/data \
    NUCLEO_STATE_DIR=/state \
    PROXY_HOST=0.0.0.0 \
    PROXY_PORT=8080

WORKDIR /opt/nucleo-ia
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 10001 nucleo \
    && useradd --system --uid 10001 --gid nucleo --home-dir /nonexistent --shell /usr/sbin/nologin nucleo \
    && install -d -o nucleo -g nucleo -m 0700 /data /state

COPY --chown=10001:10001 . .
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" || exit 1
CMD ["python", "-m", "proxy.servidor"]
