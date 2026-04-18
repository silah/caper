FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

# System dependencies and Firefox runtime libraries
# xz-utils needed to extract Mozilla's tarball (they switched from bz2 to xz)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wget \
    xz-utils \
    ffmpeg \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libx11-xcb1 \
    libxt6 \
    libnss3 \
    libxss1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Firefox — download tarball directly from Mozilla to avoid Ubuntu's snap redirect
# Use -xf (auto-detect compression) in case Mozilla change format again
RUN wget -qO /tmp/firefox.tar \
        "https://download.mozilla.org/?product=firefox-latest&os=linux64&lang=en-US" \
    && tar -xf /tmp/firefox.tar -C /opt/ \
    && ln -sf /opt/firefox/firefox /usr/local/bin/firefox \
    && rm /tmp/firefox.tar

# GeckoDriver — pre-install so tests don't need internet at run time
ARG GECKO_VERSION=0.35.0
RUN wget -qO /tmp/geckodriver.tar.gz \
        "https://github.com/mozilla/geckodriver/releases/download/v${GECKO_VERSION}/geckodriver-v${GECKO_VERSION}-linux64.tar.gz" \
    && tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/geckodriver \
    && rm /tmp/geckodriver.tar.gz

# Chrome + ChromeDriver — use Google's stable .deb (avoids Ubuntu 22.04 snap redirect)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libgbm1 libxshmfence1 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    && wget -qO /tmp/chrome.deb \
        "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# these directories are bind-mounted as volumes at runtime
RUN mkdir -p artefacts data

EXPOSE 5098

CMD ["python3", "app.py"]
