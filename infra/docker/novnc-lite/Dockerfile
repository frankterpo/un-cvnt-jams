FROM python:3.9-slim

# Install system dependencies
# xvfb: Virtual display
# openbox: Lightweight window manager
# x11vnc: VNC server
# curl/wget: Utilities
# chromium/chromium-driver: Browser stack
# procps: Process monitoring
# tini: Init process
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    openbox \
    x11vnc \
    chromium \
    chromium-driver \
    curl \
    wget \
    procps \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies for noVNC/websockify
# leveraging python-slim image directly
RUN pip install --no-cache-dir websockify numpy

# Setup noVNC
RUN mkdir -p /opt/novnc/utils/websockify && \
    wget -qO- https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.tar.gz | tar xz -C /opt/novnc --strip-components=1 && \
    ln -s /usr/local/lib/python3.9/site-packages/websockify /opt/novnc/utils/websockify

# Create app directory
WORKDIR /app

# Copy startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Environment defaults
ENV DISPLAY=:99
ENV SCREEN_RESOLUTION=1920x1080x24
ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-features=TranslateUI --disable-background-networking --disable-background-timer-throttling --disable-renderer-backgrounding"

# Expose ports
# 4444: WebDriver
# 7900: noVNC (web)
# 5900: VNC (raw)
EXPOSE 4444 7900 5900

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
