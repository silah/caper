# Selenium Test Builder - Installation Guide

This application is designed to run on a headless Linux server. Firefox runs in
`--headless` mode so no display server (X11/Xvfb) is required, but Firefox still
needs its GTK/X11 shared libraries even when running headless.

## Prerequisites

### 1. Install Firefox and its headless dependencies

```bash
sudo apt update
sudo apt install -y firefox \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libx11-xcb1 \
    libxt6 \
    libnss3 \
    libxss1 \
    libasound2
```

Verify it works headlessly:
```bash
firefox --headless --screenshot /tmp/test.png https://example.com && echo "OK"
```

### 2. Install GeckoDriver

GeckoDriver is the WebDriver for Firefox. `webdriver-manager` (installed via pip)
downloads it automatically on first test run. No manual action needed.

If `webdriver-manager` cannot reach the internet, install it manually:

```bash
GECKO_VERSION=$(curl -sI https://github.com/mozilla/geckodriver/releases/latest \
    | grep -i location | sed 's/.*\/v//' | tr -d '\r\n')
wget "https://github.com/mozilla/geckodriver/releases/download/v${GECKO_VERSION}/geckodriver-v${GECKO_VERSION}-linux64.tar.gz"
tar -xzf "geckodriver-v${GECKO_VERSION}-linux64.tar.gz"
sudo mv geckodriver /usr/local/bin/
sudo chmod +x /usr/local/bin/geckodriver
geckodriver --version
```

### 3. Install ffmpeg

ffmpeg is required to stitch screenshots into an MP4 video after each test run.

```bash
sudo apt install -y ffmpeg
ffmpeg -version
```

### 4. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the Application

```bash
source venv/bin/activate
python app.py
```

The app listens on `0.0.0.0:5098` by default. Access it from your local machine via:

```
http://<server-ip>:5098
```

To run persistently in the background:

```bash
nohup python app.py > caper.log 2>&1 &
```

## Troubleshooting

### Firefox fails to start

On a minimal server image some libraries may be missing. Run:

```bash
ldd $(which firefox) | grep "not found"
```

Install any missing libraries reported, then re-run the headless smoke test from step 1.

### GeckoDriver issues

1. Confirm Firefox is installed: `firefox --version`
2. The first test run is slower — GeckoDriver is being downloaded
3. Ensure the server has outbound internet access for the download
4. Fall back to the manual install in step 2 if needed

### Permission errors

```bash
chmod +x venv/bin/activate
```

### Database errors

If you see errors about missing columns, the schema is out of date. Delete the
database and restart (all test data will be lost):

```bash
rm tests.db
python3 app.py
```
