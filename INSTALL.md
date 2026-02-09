# Selenium Test Builder - Installation Guide

## Prerequisites

### Install Chrome/Chromium Browser

The application requires Chrome or Chromium to run Selenium tests. Install one of the following:

#### Option 1: Google Chrome (Recommended)
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f
```

#### Option 2: Chromium
```bash
sudo apt install chromium-browser
```

### Install Python Dependencies

```bash
# Using virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

OR

```bash
# System-wide (if venv not available)
pip3 install -r requirements.txt
```

## Running the Application

```bash
# If using virtual environment
source venv/bin/activate
python app.py
```

OR

```bash
# Direct execution
python3 app.py
```

Then open your browser to: `http://localhost:5000`

## Troubleshooting

### ChromeDriver Issues

The application uses `webdriver-manager` which automatically downloads and manages ChromeDriver. However, if you encounter issues:

1. Ensure Chrome/Chromium is installed (see above)
2. The first test execution may take longer as it downloads ChromeDriver
3. Check that you have internet connectivity for the initial ChromeDriver download

### Permission Errors

If you get permission errors when running tests:
```bash
chmod +x venv/bin/activate
```

### Database Errors

If you see database errors about missing columns, delete the database and restart:
```bash
rm tests.db
python3 app.py
```
