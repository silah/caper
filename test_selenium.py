#!/usr/bin/env python3
"""
Debug script to test Selenium execution
"""
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
import json

def test_firefox():
    print("Testing Firefox/Selenium setup...")
    
    firefox_options = Options()
    firefox_options.add_argument('--headless')
    
    try:
        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=firefox_options)
        
        print("✓ Firefox driver initialized")
        
        driver.get("https://www.example.com")
        print(f"✓ Navigated to example.com")
        print(f"  Page title: {driver.title}")
        
        step_results = [
            {'step': 1, 'action': 'navigate', 'status': 'success', 'message': 'Test successful'}
        ]
        
        print(f"STEP_RESULTS: {json.dumps(step_results)}")
        
        driver.quit()
        print("✓ Test completed successfully")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_firefox()
