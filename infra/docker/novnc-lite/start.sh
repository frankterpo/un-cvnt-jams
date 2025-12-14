#!/bin/bash
set -e

echo "[STARTUP] Starting novnc-lite stack..."

# 1. Start Xvfb
echo "[1/5] Starting Xvfb on $DISPLAY ($SCREEN_RESOLUTION)..."
rm -f /tmp/.X99-lock
Xvfb $DISPLAY -screen 0 $SCREEN_RESOLUTION &
PID_XVFB=$!
sleep 2

# 2. Start Openbox
echo "[2/5] Starting Openbox..."
export DISPLAY=$DISPLAY
openbox-session &
PID_OPENBOX=$!

# 3. Start x11vnc
echo "[3/5] Starting x11vnc..."
x11vnc -display $DISPLAY -forever -shared -bg -nopw -quiet -listen 0.0.0.0 -xkb

# 4. Start noVNC (websockify)
echo "[4/5] Starting noVNC on port 7900..."
/opt/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 7900 &
PID_NOVNC=$!

# 5. Start ChromeDriver
echo "[5/5] Starting ChromeDriver on port 4444..."
# Ensure we bind to all interfaces so host can access it
# Passing common flags via env var is handled by the client using options, 
# but we can try to force some if needed. For now, just launch the driver.
chromedriver --port=4444 --whitelisted-ips="" --allowed-origins="*" --url-base=/wd/hub &
PID_DRIVER=$!

# Wait for driver to be ready
echo "[WAIT] Waiting for ChromeDriver readiness..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:4444/wd/hub/status > /dev/null; then
        echo "[READY] noVNC-lite stack is fully operational."
        break
    fi
    sleep 1
done

# Keep container alive by waiting on critical processes
wait $PID_XVFB $PID_DRIVER
