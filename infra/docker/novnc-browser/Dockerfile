
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    xfce4 \
    xfce4-goodies \
    tigervnc-standalone-server \
    tigervnc-xorg-extension \
    novnc \
    websockify \
    net-tools \
    curl \
    unzip \
    gnupg \
    python3 \
    python3-pip \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_VER=$(google-chrome --version | awk '{print $3}') && \
    CHROME_MAJOR=$(echo $CHROME_VER | cut -d . -f 1) && \
    # Fetch latest matching driver version logic or simple 'latest' if unstable
    # Using LATEST_RELEASE for safety
    DRIVER_VER=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_$CHROME_MAJOR") || DRIVER_VER="latest" && \
    echo "Installing ChromeDriver $DRIVER_VER for Chrome $CHROME_VER" && \
    curl -sS -o chromedriver_linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/$DRIVER_VER/linux64/chromedriver-linux64.zip" && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Environment defaults
ENV DISPLAY=:1
ENV VNC_PORT=5901
ENV NOVNC_PORT=6080
ENV WEBDRIVER_PORT=9515
ENV SCREEN_RESOLUTION=1920x1080

# Create user
RUN useradd -m -s /bin/bash browser_user
USER browser_user
WORKDIR /home/browser_user

# Setup directories
RUN mkdir -p ~/.vnc ~/.browser_profile

# Scripts
COPY start.sh /usr/local/bin/start.sh
# Fix permission (requires switching back to root effectively or doing it before USER switch)
USER root
RUN chmod +x /usr/local/bin/start.sh
USER browser_user

EXPOSE 6080 9515

CMD ["/usr/local/bin/start.sh"]
