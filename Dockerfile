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

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# artefacts and the database are mounted as volumes so data survives restarts
RUN mkdir -p artefacts

EXPOSE 5098

CMD ["python3", "app.py"]
