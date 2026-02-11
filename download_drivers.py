#!/usr/bin/env python3
"""
Pre-download browser drivers on the host before Docker build.
Run this before building the Docker image.
"""
import os
import sys
import requests
import zipfile
import tarfile
import shutil
from pathlib import Path

# Set cache directory
cache_dir = Path('./webdrivers')
cache_dir.mkdir(exist_ok=True)

print("Downloading browser drivers to ./webdrivers/...")
print("=" * 60)

def download_file(url, dest):
    """Download a file with progress"""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

try:
    # ChromeDriver - get latest stable version
    print("\n[1/3] Downloading ChromeDriver (latest stable)...")
    chrome_version_url = "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE"
    chrome_version = requests.get(chrome_version_url).text.strip()
    chrome_url = f"https://storage.googleapis.com/chrome-for-testing-public/{chrome_version}/linux64/chromedriver-linux64.zip"
    chrome_zip = cache_dir / "chromedriver.zip"
    download_file(chrome_url, chrome_zip)
    
    # Extract chromedriver
    with zipfile.ZipFile(chrome_zip, 'r') as zip_ref:
        zip_ref.extractall(cache_dir)
    
    # Move binary to expected location
    chrome_bin = cache_dir / "chromedriver-linux64" / "chromedriver"
    chrome_dest = cache_dir / "drivers" / "chromedriver" / "linux64" / chrome_version / "chromedriver"
    chrome_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(chrome_bin), str(chrome_dest))
    chrome_dest.chmod(0o755)
    shutil.rmtree(cache_dir / "chromedriver-linux64")
    chrome_zip.unlink()
    print(f"✓ ChromeDriver {chrome_version} installed")
    
    # GeckoDriver (Firefox)
    print("\n[2/3] Downloading GeckoDriver (Firefox, latest)...")
    gecko_api = "https://api.github.com/repos/mozilla/geckodriver/releases/latest"
    gecko_data = requests.get(gecko_api).json()
    gecko_version = gecko_data['tag_name']
    gecko_url = f"https://github.com/mozilla/geckodriver/releases/download/{gecko_version}/geckodriver-{gecko_version}-linux64.tar.gz"
    gecko_tar = cache_dir / "geckodriver.tar.gz"
    download_file(gecko_url, gecko_tar)
    
    # Extract geckodriver
    with tarfile.open(gecko_tar, 'r:gz') as tar_ref:
        tar_ref.extractall(cache_dir)
    
    gecko_bin = cache_dir / "geckodriver"
    gecko_dest = cache_dir / "drivers" / "geckodriver" / "linux64" / gecko_version / "geckodriver"
    gecko_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(gecko_bin), str(gecko_dest))
    gecko_dest.chmod(0o755)
    gecko_tar.unlink()
    print(f"✓ GeckoDriver {gecko_version} installed")
    
    # EdgeDriver
    print("\n[3/3] Downloading EdgeDriver (latest stable)...")
    try:
        # Correct Microsoft EdgeDriver domain
        edge_version_url = "https://msedgedriver.microsoft.com/LATEST_STABLE"
        edge_version = requests.get(edge_version_url, timeout=10).text.strip()
        edge_url = f"https://msedgedriver.microsoft.com/{edge_version}/edgedriver_linux64.zip"
        edge_zip = cache_dir / "edgedriver.zip"
        download_file(edge_url, edge_zip)
        
        # Extract edgedriver
        with zipfile.ZipFile(edge_zip, 'r') as zip_ref:
            zip_ref.extractall(cache_dir)
        
        edge_bin = cache_dir / "msedgedriver"
        edge_dest = cache_dir / "drivers" / "edgedriver" / "linux64" / edge_version / "msedgedriver"
        edge_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(edge_bin), str(edge_dest))
        edge_dest.chmod(0o755)
        edge_zip.unlink()
        print(f"✓ EdgeDriver {edge_version} installed")
    except Exception as edge_error:
        print(f"⚠ EdgeDriver download failed: {edge_error}")
        print("  Edge browser tests will download driver at runtime (slower first run)")
    
    print("\n" + "=" * 60)
    print("✓ Chrome and Firefox drivers ready!")
    if 'edge_error' in locals():
        print("⚠ Edge driver will be downloaded at runtime")
    print("You can now build the Docker image.")
    
except Exception as e:
    print(f"\n✗ Error downloading drivers: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
