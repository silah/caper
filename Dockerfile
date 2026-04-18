FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    wget \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright browsers and their OS-level dependencies
RUN playwright install --with-deps chromium firefox

COPY . .

# these directories are bind-mounted as volumes at runtime
RUN mkdir -p artefacts data

EXPOSE 5098

CMD ["python3", "app.py"]
