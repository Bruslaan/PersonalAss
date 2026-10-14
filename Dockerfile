FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive DISPLAY=:99 HOME=/home/browser LANG=C.UTF-8 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb x11vnc x11-utils xdotool openbox novnc websockify \
    nginx-light apache2-utils python3 gosu tini ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 browser \
    && mkdir -p /data/profile /app \
    && chown -R browser:browser /data /home/browser
WORKDIR /app
COPY app/ /app/
RUN chmod +x /app/entrypoint.sh
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
