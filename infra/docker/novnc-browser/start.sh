#!/bin/bash
set -e

# Default env vars
VNC_PORT=${VNC_PORT:-5901}
NOVNC_PORT=${NOVNC_PORT:-6080}
WEBDRIVER_PORT=${WEBDRIVER_PORT:-9515}
DISPLAY=${DISPLAY:-:1}
SCREEN_RESOLUTION=${SCREEN_RESOLUTION:-1920x1080x24}

echo "Starting XFCE + VNC + Chrome..."

# 1. Start Xvfb / VNC
# We use tigervnc directly which creates the display
# Remove lock files if any
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

vncserver $DISPLAY -geometry $SCREEN_RESOLUTION -depth 24 -SecurityTypes None -localhost no --I-KNOW-THIS-IS-INSECURE

# 2. Start Window Manager
export DISPLAY=$DISPLAY
# Wait for X
sleep 2
xfce4-session &

# 3. Start Websockify (noVNC)
# Pointing to local VNC port
websockify --web=/usr/share/novnc --wrap-mode=ignore $NOVNC_PORT localhost:$VNC_PORT &

# 4. Start Chrome (Browser)
# If using Selenium/undetected-chromedriver from OUTSIDE, we might not want to start Chrome here 
# IF the external script spawns it. 
# BUT, undetected_chromedriver typically spawns the process itself locally.
# If we want a REMOTE driver, we have two options:
# A) Run a Selenium Standalone Server (Java) here.
# B) Start Chrome with --remote-debugging-port and use CDP or connect minimal webdriver.

# The prompt requirement: "Expose a remote WebDriver / CDP endpoint".
# And "automation flows... should behave like local ChromeDriver".

# If we run regular Chrome with debugging port:
echo "Starting Chrome with remote debugging on $WEBDRIVER_PORT..."

# Optional: Proxy
PROXY_ARGS=""
if [ ! -z "$BROWSER_PROXY_URL" ]; then
    PROXY_ARGS="--proxy-server=$BROWSER_PROXY_URL"
fi

# Profile dir
# Start ChromeDriver
# ChromeDriver will spawn Chrome. We need to point it to correct display.
# Also ensure it listens on 0.0.0.0 for external connection.
echo "Starting ChromeDriver on $WEBDRIVER_PORT..."

chromedriver \
  --port=$WEBDRIVER_PORT \
  --whitelisted-ips="" \
  --allowed-origins="*" \
  --url-base=/wd/hub \
  --verbose &
# Chromedriver needs to know about user-data-dir?
# Usually clients pass options. But if we want persistence, we rely on client passing args or default.
# For this basic image, client options rule.

# Keep container alive
wait
