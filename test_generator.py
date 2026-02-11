"""
Generate Selenium scripts from test steps
"""

def get_browser_config(browser='firefox'):
    """Generate browser-specific imports and setup code"""
    configs = {
        'firefox': {
            'imports': [
                "from selenium.webdriver.firefox.options import Options",
                "from selenium.webdriver.firefox.service import Service",
                "import glob",
                "import os",
            ],
            'setup': [
                "    # Setup headless Firefox",
                "    firefox_options = Options()",
                "    firefox_options.add_argument('--headless')",
                "    firefox_options.add_argument('--no-sandbox')",
                "    firefox_options.add_argument('--disable-dev-shm-usage')",
                "    # Find geckodriver in cache",
                "    driver_path = glob.glob('/opt/webdriver/drivers/geckodriver/linux64/*/geckodriver')[0]",
                "    service = Service(driver_path)",
                "    driver = webdriver.Firefox(service=service, options=firefox_options)",
            ]
        },
        'chrome': {
            'imports': [
                "from selenium.webdriver.chrome.options import Options",
                "from selenium.webdriver.chrome.service import Service",
                "import glob",
                "import os",
            ],
            'setup': [
                "    # Setup headless Chrome",
                "    chrome_options = Options()",
                "    chrome_options.add_argument('--headless=new')",
                "    chrome_options.add_argument('--no-sandbox')",
                "    chrome_options.add_argument('--disable-dev-shm-usage')",
                "    chrome_options.add_argument('--disable-gpu')",
                "    # Find chromedriver in cache",
                "    driver_path = glob.glob('/opt/webdriver/drivers/chromedriver/linux64/*/chromedriver')[0]",
                "    service = Service(driver_path)",
                "    driver = webdriver.Chrome(service=service, options=chrome_options)",
            ]
        },
        'edge': {
            'imports': [
                "from selenium.webdriver.edge.options import Options",
                "from selenium.webdriver.edge.service import Service",
                "import glob",
                "import os",
            ],
            'setup': [
                "    # Setup headless Edge",
                "    edge_options = Options()",
                "    edge_options.add_argument('--headless=new')",
                "    edge_options.add_argument('--no-sandbox')",
                "    edge_options.add_argument('--disable-dev-shm-usage')",
                "    edge_options.add_argument('--disable-gpu')",
                "    # Find msedgedriver in cache",
                "    driver_path = glob.glob('/opt/webdriver/drivers/edgedriver/linux64/*/msedgedriver')[0]",
                "    service = Service(driver_path)",
                "    driver = webdriver.Edge(service=service, options=edge_options)",
            ]
        },
        'chrome_mobile': {
            'imports': [
                "from selenium.webdriver.chrome.options import Options",
                "from selenium.webdriver.chrome.service import Service",
                "import glob",
                "import os",
            ],
            'setup': [
                "    # Setup Chrome with mobile emulation (Android)",
                "    chrome_options = Options()",
                "    chrome_options.add_argument('--headless=new')",
                "    chrome_options.add_argument('--no-sandbox')",
                "    chrome_options.add_argument('--disable-dev-shm-usage')",
                "    mobile_emulation = {",
                "        'deviceMetrics': {'width': 375, 'height': 812, 'pixelRatio': 3.0},",
                "        'userAgent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'",
                "    }",
                "    chrome_options.add_experimental_option('mobileEmulation', mobile_emulation)",
                "    # Find chromedriver in cache",
                "    driver_path = glob.glob('/opt/webdriver/drivers/chromedriver/linux64/*/chromedriver')[0]",
                "    service = Service(driver_path)",
                "    driver = webdriver.Chrome(service=service, options=chrome_options)",
            ]
        },
        'firefox_mobile': {
            'imports': [
                "from selenium.webdriver.firefox.options import Options",
                "from selenium.webdriver.firefox.service import Service",
                "import glob",
                "import os",
            ],
            'setup': [
                "    # Setup Firefox with mobile emulation (Android)",
                "    firefox_options = Options()",
                "    firefox_options.add_argument('--headless')",
                "    firefox_options.add_argument('--no-sandbox')",
                "    firefox_options.add_argument('--disable-dev-shm-usage')",
                "    # Mobile user agent",
                "    firefox_options.set_preference('general.useragent.override', 'Mozilla/5.0 (Android 13; Mobile; rv:120.0) Gecko/120.0 Firefox/120.0')",
                "    # Mobile viewport",
                "    firefox_options.set_preference('layout.css.devPixelsPerPx', '3.0')",
                "    # Find geckodriver in cache",
                "    driver_path = glob.glob('/opt/webdriver/drivers/geckodriver/linux64/*/geckodriver')[0]",
                "    service = Service(driver_path)",
                "    driver = webdriver.Firefox(service=service, options=firefox_options)",
                "    driver.set_window_size(375, 812)",
            ]
        }
    }
    
    return configs.get(browser, configs['firefox'])

def generate_selenium_script(steps, browser='firefox'):
    """
    Generate a Selenium Python script from a list of test steps
    """
    
    browser_config = get_browser_config(browser)
    
    script_lines = [
        "from selenium import webdriver",
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.common.keys import Keys",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
    ]
    
    # Add browser-specific imports
    script_lines.extend(browser_config['imports'])
    
    script_lines.extend([
        "import time",
        "import json",
        "",
        "def run_test():",
    ])
    
    # Add browser-specific setup
    script_lines.extend(browser_config['setup'])
    
    script_lines.extend([
        "    step_results = []",
        "    ",
        "    try:",
    ])
    
    for i, step in enumerate(steps, 1):
        action = step.get('action')
        
        if action == 'navigate':
            url = step.get('value', '')
            script_lines.append(f"        # Step {i}: Navigate to URL")
            script_lines.append(f"        try:")
            script_lines.append(f"            driver.get('{url}')")
            script_lines.append(f"            time.sleep(1)")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'navigate', 'status': 'success', 'message': 'Navigated to {url}'}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'navigate', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
            
        elif action == 'click':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            script_lines.append(f"        # Step {i}: Click element")
            by_type = get_by_type(selector_type)
            script_lines.append(f"        try:")
            script_lines.append(f"            element = WebDriverWait(driver, 10).until(")
            script_lines.append(f"                EC.element_to_be_clickable(({by_type}, '{selector}'))")
            script_lines.append(f"            )")
            script_lines.append(f"            element.click()")
            script_lines.append(f"            time.sleep(0.5)")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'click', 'status': 'success', 'message': 'Clicked element {selector}'}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'click', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
            
        elif action == 'type':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            text = step.get('value', '')
            script_lines.append(f"        # Step {i}: Type text into element")
            by_type = get_by_type(selector_type)
            script_lines.append(f"        try:")
            script_lines.append(f"            element = WebDriverWait(driver, 10).until(")
            script_lines.append(f"                EC.presence_of_element_located(({by_type}, '{selector}'))")
            script_lines.append(f"            )")
            script_lines.append(f"            element.clear()")
            script_lines.append(f"            element.send_keys('{text}')")
            script_lines.append(f"            time.sleep(0.5)")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'type', 'status': 'success', 'message': 'Typed text into {selector}'}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'type', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
            
        elif action == 'wait':
            seconds = step.get('value', '1')
            script_lines.append(f"        # Step {i}: Wait")
            script_lines.append(f"        time.sleep({seconds})")
            script_lines.append(f"        step_results.append({{'step': {i}, 'action': 'wait', 'status': 'success', 'message': 'Waited {seconds} seconds'}})")
            
        elif action == 'execute_js':
            js_code = step.get('value', '')
            script_lines.append(f"        # Step {i}: Execute JavaScript")
            # Escape single quotes in JS code
            js_code_escaped = js_code.replace("'", "\\'")
            script_lines.append(f"        try:")
            script_lines.append(f"            driver.execute_script('{js_code_escaped}')")
            script_lines.append(f"            time.sleep(0.5)")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'execute_js', 'status': 'success', 'message': 'Executed JavaScript'}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'execute_js', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
            
        elif action == 'screenshot':
            script_lines.append(f"        # Step {i}: Take screenshot")
            script_lines.append(f"        try:")
            script_lines.append(f"            import uuid")
            script_lines.append(f"            import os")
            script_lines.append(f"            screenshot_dir = '/app/static/screenshots'")
            script_lines.append(f"            os.makedirs(screenshot_dir, exist_ok=True)")
            script_lines.append(f"            screenshot_filename = str(uuid.uuid4()) + '.png'")
            script_lines.append(f"            screenshot_path = os.path.join(screenshot_dir, screenshot_filename)")
            script_lines.append(f"            driver.save_screenshot(screenshot_path)")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'screenshot', 'status': 'success', 'message': 'Screenshot saved', 'screenshot': screenshot_filename}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'screenshot', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
            
        elif action == 'assert_title':
            expected_title = step.get('value', '')
            script_lines.append(f"        # Step {i}: Assert page title")
            script_lines.append(f"        try:")
            script_lines.append(f"            assert '{expected_title}' in driver.title, f'Expected title to contain {expected_title}'")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'assert_title', 'status': 'success', 'message': 'Title assertion passed'}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'assert_title', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
            
        elif action == 'assert_text':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            expected_text = step.get('value', '')
            script_lines.append(f"        # Step {i}: Assert element text")
            by_type = get_by_type(selector_type)
            script_lines.append(f"        try:")
            script_lines.append(f"            element = WebDriverWait(driver, 10).until(")
            script_lines.append(f"                EC.presence_of_element_located(({by_type}, '{selector}'))")
            script_lines.append(f"            )")
            script_lines.append(f"            assert '{expected_text}' in element.text, f'Expected text to contain {expected_text}'")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'success', 'message': 'Text assertion passed'}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
            
        elif action == 'scroll_to':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            script_lines.append(f"        # Step {i}: Scroll to element")
            by_type = get_by_type(selector_type)
            script_lines.append(f"        try:")
            script_lines.append(f"            element = WebDriverWait(driver, 10).until(")
            script_lines.append(f"                EC.presence_of_element_located(({by_type}, '{selector}'))")
            script_lines.append(f"            )")
            script_lines.append(f"            driver.execute_script('arguments[0].scrollIntoView();', element)")
            script_lines.append(f"            time.sleep(0.5)")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'success', 'message': 'Scrolled to element {selector}'}})")
            script_lines.append(f"        except Exception as e:")
            script_lines.append(f"            step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'error', 'message': str(e)}})")
            script_lines.append(f"            raise")
        
        script_lines.append("")
    
    script_lines.extend([
        "        print('STEP_RESULTS:', json.dumps(step_results))",
        "        return {'status': 'success', 'message': 'Test completed successfully'}",
        "    ",
        "    except Exception as e:",
        "        print('STEP_RESULTS:', json.dumps(step_results))",
        "        return {'status': 'error', 'message': str(e)}",
        "    ",
        "    finally:",
        "        driver.quit()",
        "",
        "if __name__ == '__main__':",
        "    result = run_test()",
        "    print(result)",
    ])
    
    return '\n'.join(script_lines)


def get_by_type(selector_type):
    """
    Convert selector type to Selenium By constant
    """
    mapping = {
        'css': 'By.CSS_SELECTOR',
        'id': 'By.ID',
        'xpath': 'By.XPATH',
        'name': 'By.NAME',
        'class': 'By.CLASS_NAME',
        'tag': 'By.TAG_NAME',
        'link_text': 'By.LINK_TEXT',
        'partial_link_text': 'By.PARTIAL_LINK_TEXT',
    }
    return mapping.get(selector_type, 'By.CSS_SELECTOR')
