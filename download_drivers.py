#!/usr/bin/env python3
"""
Pre-download browser drivers on the host before Docker build.
Run this before building the Docker image.
"""
import os
import sys

# Set cache directory
os.environ['WDM_LOCAL'] = '1'
os.environ['WDM_CACHE_DIR'] = './webdrivers'

print("Downloading browser drivers to ./webdrivers/...")
print("=" * 60)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    
    print("\n[1/3] Downloading ChromeDriver...")
    chrome_path = ChromeDriverManager().install()
    print(f"✓ ChromeDriver installed: {chrome_path}")
    
    print("\n[2/3] Downloading GeckoDriver (Firefox)...")
    firefox_path = GeckoDriverManager().install()
    print(f"✓ GeckoDriver installed: {firefox_path}")
    
    print("\n[3/3] Downloading EdgeDriver...")
    edge_path = EdgeChromiumDriverManager().install()
    print(f"✓ EdgeDriver installed: {edge_path}")
    
    print("\n" + "=" * 60)
    print("✓ All drivers downloaded successfully!")
    print("You can now build the Docker image.")
    
except Exception as e:
    print(f"\n✗ Error downloading drivers: {e}")
    print("\nMake sure you have installed the requirements:")
    print("  pip install -r requirements.txt")
    sys.exit(1)
