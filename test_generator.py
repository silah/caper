"""
Generate Selenium scripts from test steps
"""
import re
import os


def _sanitize_name(name):
    return re.sub(r'[^\w\-]', '_', name)


def generate_selenium_script(steps, test_name='test', base_artefacts_dir=None):
    if base_artefacts_dir is None:
        base_artefacts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'artefacts')

    test_name_safe = _sanitize_name(test_name)

    script_lines = [
        "from seleniumwire import webdriver",
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.common.keys import Keys",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
        "from selenium.webdriver.firefox.options import Options",
        "from selenium.webdriver.firefox.service import Service",
        "import shutil",
        "import time",
        "import json",
        "import os",
        "import datetime",
        "import threading",
        "import subprocess as _sp",
        "import base64",
        "",
        "",
        "def _requests_to_har(requests):",
        "    entries = []",
        "    for req in requests:",
        "        try:",
        "            req_headers = [{'name': k, 'value': v} for k, v in req.headers.items()]",
        "            entry = {",
        "                'startedDateTime': req.date.isoformat() + 'Z' if req.date else '',",
        "                'time': -1,",
        "                'request': {",
        "                    'method': req.method,",
        "                    'url': req.url,",
        "                    'httpVersion': 'HTTP/1.1',",
        "                    'headers': req_headers,",
        "                    'queryString': [],",
        "                    'cookies': [],",
        "                    'headersSize': -1,",
        "                    'bodySize': len(req.body) if req.body else 0,",
        "                },",
        "                'response': {",
        "                    'status': 0, 'statusText': '', 'httpVersion': 'HTTP/1.1',",
        "                    'headers': [], 'cookies': [],",
        "                    'content': {'size': 0, 'mimeType': ''},",
        "                    'redirectURL': '', 'headersSize': -1, 'bodySize': -1,",
        "                },",
        "                'cache': {},",
        "                'timings': {'send': 0, 'wait': 0, 'receive': 0},",
        "            }",
        "            if req.response:",
        "                resp = req.response",
        "                mime = resp.headers.get('Content-Type', 'application/octet-stream').split(';')[0]",
        "                body = resp.body or b''",
        "                try:",
        "                    content = {'size': len(body), 'mimeType': mime, 'text': body.decode('utf-8')}",
        "                except Exception:",
        "                    content = {",
        "                        'size': len(body), 'mimeType': mime,",
        "                        'text': base64.b64encode(body).decode('ascii'), 'encoding': 'base64',",
        "                    }",
        "                resp_headers = [{'name': k, 'value': v} for k, v in resp.headers.items()]",
        "                entry['response'] = {",
        "                    'status': resp.status_code, 'statusText': '',",
        "                    'httpVersion': 'HTTP/1.1', 'headers': resp_headers,",
        "                    'cookies': [], 'content': content,",
        "                    'redirectURL': '', 'headersSize': -1, 'bodySize': len(body),",
        "                }",
        "                if req.date and resp.date:",
        "                    entry['time'] = (resp.date - req.date).total_seconds() * 1000",
        "            entries.append(entry)",
        "        except Exception:",
        "            continue",
        "    return {",
        "        'log': {",
        "            'version': '1.2',",
        "            'creator': {'name': 'caper', 'version': '1.0'},",
        "            'pages': [],",
        "            'entries': entries,",
        "        }",
        "    }",
        "",
        "",
        "def run_test():",
        f"    _base = {repr(base_artefacts_dir)}",
        f"    _name = {repr(test_name_safe)}",
        "    _ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')",
        "    working_dir = os.path.join(_base, _name, _ts)",
        "    screenshots_dir = os.path.join(working_dir, 'screenshots')",
        "    hars_dir = os.path.join(working_dir, 'hars')",
        "    video_dir = os.path.join(working_dir, 'video')",
        "    os.makedirs(screenshots_dir, exist_ok=True)",
        "    os.makedirs(hars_dir, exist_ok=True)",
        "    os.makedirs(video_dir, exist_ok=True)",
        "",
        "    firefox_options = Options()",
        "    firefox_options.add_argument('--headless')",
        "    _gecko = shutil.which('geckodriver')",
        "    if _gecko:",
        "        service = Service(_gecko)",
        "    else:",
        "        from webdriver_manager.firefox import GeckoDriverManager",
        "        service = Service(GeckoDriverManager().install())",
        "    driver = webdriver.Firefox(service=service, options=firefox_options)",
        "    step_results = []",
        "",
        "    _ss_counter = [0]",
        "    _ss_running = [True]",
        "",
        "    def _screenshot_worker():",
        "        while _ss_running[0]:",
        "            _ss_counter[0] += 1",
        "            path = os.path.join(screenshots_dir, f'{_ss_counter[0]:04d}.png')",
        "            try:",
        "                driver.save_screenshot(path)",
        "            except Exception:",
        "                pass",
        "            time.sleep(1)",
        "",
        "    _ss_thread = threading.Thread(target=_screenshot_worker, daemon=True)",
        "    _ss_thread.start()",
        "",
        "    def _save_har(step_num):",
        "        try:",
        "            har_data = _requests_to_har(driver.requests)",
        "            har_path = os.path.join(hars_dir, f'step_{step_num:03d}.har')",
        "            with open(har_path, 'w') as _f:",
        "                json.dump(har_data, _f, indent=2)",
        "            del driver.requests",
        "        except Exception:",
        "            pass",
        "",
        "    try:",
    ]

    for i, step in enumerate(steps, 1):
        action = step.get('action')

        # Clear captured requests before each step so the HAR only contains
        # traffic triggered by that step.
        script_lines.append(f"        del driver.requests")

        if action == 'navigate':
            url = step.get('value', '')
            url_r = repr(url)
            msg_r = repr(f'Navigated to {url}')
            script_lines.extend([
                f"        # Step {i}: Navigate to URL",
                f"        try:",
                f"            driver.get({url_r})",
                f"            time.sleep(1)",
                f"            step_results.append({{'step': {i}, 'action': 'navigate', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'navigate', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'click':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            selector_r = repr(selector)
            msg_r = repr(f'Clicked element {selector}')
            by_type = get_by_type(selector_type)
            script_lines.extend([
                f"        # Step {i}: Click element",
                f"        try:",
                f"            element = WebDriverWait(driver, 10).until(",
                f"                EC.element_to_be_clickable(({by_type}, {selector_r}))",
                f"            )",
                f"            element.click()",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'click', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'click', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'type':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            text = step.get('value', '')
            selector_r = repr(selector)
            text_r = repr(text)
            msg_r = repr(f'Typed text into {selector}')
            by_type = get_by_type(selector_type)
            script_lines.extend([
                f"        # Step {i}: Type text into element",
                f"        try:",
                f"            element = WebDriverWait(driver, 10).until(",
                f"                EC.presence_of_element_located(({by_type}, {selector_r}))",
                f"            )",
                f"            element.clear()",
                f"            element.send_keys({text_r})",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'type', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'type', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'wait':
            try:
                seconds_val = float(step.get('value', '1'))
            except (ValueError, TypeError):
                seconds_val = 1.0
            msg_r = repr(f'Waited {seconds_val} seconds')
            script_lines.extend([
                f"        # Step {i}: Wait",
                f"        try:",
                f"            time.sleep({seconds_val})",
                f"            step_results.append({{'step': {i}, 'action': 'wait', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'wait', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'execute_js':
            js_code = step.get('value', '')
            js_r = repr(js_code)
            script_lines.extend([
                f"        # Step {i}: Execute JavaScript",
                f"        try:",
                f"            driver.execute_script({js_r})",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'execute_js', 'status': 'success', 'message': 'Executed JavaScript'}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'execute_js', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'screenshot':
            # Continuous screenshots are handled by the background thread;
            # this step just records the fact in step_results and saves HAR.
            script_lines.extend([
                f"        # Step {i}: Screenshot (continuous screenshots running in background)",
                f"        try:",
                f"            step_results.append({{'step': {i}, 'action': 'screenshot', 'status': 'success', 'message': 'Continuous screenshots active'}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'screenshot', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'assert_title':
            expected_title = step.get('value', '')
            title_r = repr(expected_title)
            script_lines.extend([
                f"        # Step {i}: Assert page title",
                f"        try:",
                f"            assert {title_r} in driver.title, 'Expected title to contain ' + {title_r}",
                f"            step_results.append({{'step': {i}, 'action': 'assert_title', 'status': 'success', 'message': 'Title assertion passed'}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'assert_title', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'assert_text':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            expected_text = step.get('value', '')
            selector_r = repr(selector)
            text_r = repr(expected_text)
            by_type = get_by_type(selector_type)
            script_lines.extend([
                f"        # Step {i}: Assert element text",
                f"        try:",
                f"            element = WebDriverWait(driver, 10).until(",
                f"                EC.presence_of_element_located(({by_type}, {selector_r}))",
                f"            )",
                f"            assert {text_r} in element.text, 'Expected text to contain ' + {text_r}",
                f"            step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'success', 'message': 'Text assertion passed'}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'scroll_to':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            selector_r = repr(selector)
            msg_r = repr(f'Scrolled to element {selector}')
            by_type = get_by_type(selector_type)
            script_lines.extend([
                f"        # Step {i}: Scroll to element",
                f"        try:",
                f"            element = WebDriverWait(driver, 10).until(",
                f"                EC.presence_of_element_located(({by_type}, {selector_r}))",
                f"            )",
                f"            driver.execute_script('arguments[0].scrollIntoView();', element)",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

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
        "        _ss_running[0] = False",
        "        _ss_thread.join(timeout=2)",
        "        driver.quit()",
        "        if os.path.exists(os.path.join(screenshots_dir, '0001.png')):",
        "            _sp.run([",
        "                'ffmpeg', '-y', '-framerate', '1', '-start_number', '1',",
        "                '-i', os.path.join(screenshots_dir, '%04d.png'),",
        "                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',",
        "                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',",
        "                os.path.join(video_dir, 'recording.mp4'),",
        "            ], capture_output=True)",
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
