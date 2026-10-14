FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive DISPLAY=:99 HOME=/home/browser LANG=C.UTF-8 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb x11vnc x11-utils xdotool openbox novnc websockify \
    nginx-light apache2-utils python3 python3-venv gosu tini ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 browser \
    && mkdir -p /data/profile /app \
    && chown -R browser:browser /data /home/browser
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python3 -m venv /opt/agent-venv \
    && /opt/agent-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY app/ /app/
COPY scripts/ /app/scripts/
RUN chmod +x /app/entrypoint.sh
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
