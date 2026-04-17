"""
Generate Selenium scripts from test steps
"""
import re
import os


def _sanitize_name(name):
    return re.sub(r'[^\w\-]', '_', name)


def get_by_type(selector_type):
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


def _element_find_code(selector_type, selector, ec_type='presence', timeout=10, var_name='element'):
    """Return indented lines (8 spaces) that locate an element into var_name.

    ec_type: 'presence' | 'clickable' | 'visible'
    Handles jspath (JS expression polling) and aria ([aria-label=...] CSS).
    """
    if selector_type == 'jspath':
        expr_r = repr(selector)
        return [f"            {var_name} = _jspath_wait({expr_r}, timeout={timeout})"]

    if selector_type == 'aria':
        resolved = f'[aria-label="{selector}"]'
        by_type = 'By.CSS_SELECTOR'
    else:
        resolved = selector
        by_type = get_by_type(selector_type)

    sel_r = repr(resolved)

    ec_map = {
        'clickable': f'EC.element_to_be_clickable(({by_type}, {sel_r}))',
        'presence':  f'EC.presence_of_element_located(({by_type}, {sel_r}))',
        'visible':   f'EC.visibility_of_element_located(({by_type}, {sel_r}))',
    }
    ec_call = ec_map.get(ec_type, ec_map['presence'])

    return [
        f"            {var_name} = WebDriverWait(driver, {timeout}).until(",
        f"                {ec_call}",
        f"            )",
    ]


# Lines added to every generated script's run_test() body, before `try:`
_JSPATH_HELPER = [
    "    def _jspath_wait(expr, timeout=10):",
    "        _deadline = time.time() + timeout",
    "        while time.time() < _deadline:",
    "            _el = driver.execute_script('return (' + expr + ')')",
    "            if _el is not None:",
    "                return _el",
    "            time.sleep(0.3)",
    "        raise Exception('JSPath timed out: ' + repr(expr))",
    "",
]


def generate_selenium_script(steps, test_name='test', base_artefacts_dir=None):
    if base_artefacts_dir is None:
        base_artefacts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'artefacts')

    test_name_safe = _sanitize_name(test_name)

    script_lines = [
        "from selenium import webdriver",
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.common.keys import Keys",
        "from selenium.webdriver.support.ui import WebDriverWait, Select",
        "from selenium.webdriver.support import expected_conditions as EC",
        "from selenium.webdriver.common.action_chains import ActionChains",
        "from selenium.webdriver.firefox.options import Options",
        "from selenium.webdriver.firefox.service import Service",
        "import shutil",
        "import time",
        "import json",
        "import os",
        "import datetime",
        "import threading",
        "import subprocess as _sp",
        "",
        "",
        "def _performance_to_har(resources):",
        "    entries = []",
        "    now = datetime.datetime.utcnow().isoformat() + 'Z'",
        "    for r in resources:",
        "        entries.append({",
        "            'startedDateTime': now,",
        "            'time': r.get('duration', 0),",
        "            'request': {",
        "                'method': 'GET',",
        "                'url': r.get('name', ''),",
        "                'httpVersion': 'HTTP/1.1',",
        "                'headers': [], 'queryString': [], 'cookies': [],",
        "                'headersSize': -1,",
        "                'bodySize': r.get('transferSize', -1),",
        "            },",
        "            'response': {",
        "                'status': 0, 'statusText': '', 'httpVersion': 'HTTP/1.1',",
        "                'headers': [], 'cookies': [],",
        "                'content': {'size': r.get('decodedBodySize', -1), 'mimeType': ''},",
        "                'redirectURL': '', 'headersSize': -1,",
        "                'bodySize': r.get('encodedBodySize', -1),",
        "            },",
        "            'cache': {},",
        "            'timings': {",
        "                'dns': max(0, r.get('domainLookupEnd', 0) - r.get('domainLookupStart', 0)),",
        "                'connect': max(0, r.get('connectEnd', 0) - r.get('connectStart', 0)),",
        "                'send': 0,",
        "                'wait': max(0, r.get('responseStart', 0) - r.get('requestStart', 0)),",
        "                'receive': max(0, r.get('responseEnd', 0) - r.get('responseStart', 0)),",
        "            },",
        "        })",
        "    return {",
        "        'log': {",
        "            'version': '1.2',",
        "            'creator': {'name': 'caper', 'version': '1.0'},",
        "            'pages': [], 'entries': entries,",
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
        "    print('ARTEFACT_DIR:', os.path.join(_name, _ts))",
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
        "            time.sleep(0.25)",
        "",
        "    _ss_thread = threading.Thread(target=_screenshot_worker, daemon=True)",
        "    _ss_thread.start()",
        "",
        "    def _save_har(step_num):",
        "        try:",
        "            raw = driver.execute_script(",
        "                'return JSON.stringify(window.performance.getEntriesByType(\"resource\"))'",
        "            )",
        "            resources = json.loads(raw) if raw else []",
        "            har_data = _performance_to_har(resources)",
        "            har_path = os.path.join(hars_dir, f'step_{step_num:03d}.har')",
        "            with open(har_path, 'w') as _f:",
        "                json.dump(har_data, _f, indent=2)",
        "        except Exception:",
        "            pass",
        "        try:",
        "            driver.execute_script('window.performance.clearResourceTimings()')",
        "        except Exception:",
        "            pass",
        "",
    ] + _JSPATH_HELPER + [
        "    try:",
    ]

    for i, step in enumerate(steps, 1):
        action = step.get('action')

        script_lines.extend([
            "        try:",
            "            driver.execute_script('window.performance.clearResourceTimings()')",
            "        except Exception:",
            "            pass",
        ])

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
            msg_r = repr(f'Clicked element {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='clickable')
            script_lines.extend([
                f"        # Step {i}: Click element",
                f"        try:",
            ] + find_lines + [
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
            text_r = repr(text)
            msg_r = repr(f'Typed text into {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='presence')
            script_lines.extend([
                f"        # Step {i}: Type text into element",
                f"        try:",
            ] + find_lines + [
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
            text_r = repr(expected_text)
            msg_r = repr(f'Text assertion passed on {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='presence')
            script_lines.extend([
                f"        # Step {i}: Assert element text",
                f"        try:",
            ] + find_lines + [
                f"            assert {text_r} in element.text, 'Expected text to contain ' + {text_r}",
                f"            step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'scroll_to':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Scrolled to element {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='presence')
            script_lines.extend([
                f"        # Step {i}: Scroll to element",
                f"        try:",
            ] + find_lines + [
                f"            driver.execute_script('arguments[0].scrollIntoView();', element)",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'select':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            option = step.get('value', '')
            select_by = step.get('selectBy', 'text')
            option_r = repr(option)
            msg_r = repr(f'Selected "{option}" in {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='presence')
            if select_by == 'value':
                select_call = f"Select(element).select_by_value({option_r})"
            elif select_by == 'index':
                select_call = f"Select(element).select_by_index(int({option_r}))"
            else:
                select_call = f"Select(element).select_by_visible_text({option_r})"
            script_lines.extend([
                f"        # Step {i}: Select dropdown option",
                f"        try:",
            ] + find_lines + [
                f"            {select_call}",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'select', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'select', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'assert_visible':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Element {selector} is visible')
            find_lines = _element_find_code(selector_type, selector, ec_type='visible')
            script_lines.extend([
                f"        # Step {i}: Assert element visible",
                f"        try:",
            ] + find_lines + [
                f"            step_results.append({{'step': {i}, 'action': 'assert_visible', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'assert_visible', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'assert_url':
            expected = step.get('value', '')
            expected_r = repr(expected)
            msg_r = repr(f'URL contains "{expected}"')
            script_lines.extend([
                f"        # Step {i}: Assert URL",
                f"        try:",
                f"            _current_url = driver.current_url",
                f"            assert {expected_r} in _current_url, 'Expected URL to contain ' + {expected_r} + ', got: ' + _current_url",
                f"            step_results.append({{'step': {i}, 'action': 'assert_url', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'assert_url', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'key_press':
            key_name = step.get('key', 'Enter')
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            key_map = {
                'Enter': 'Keys.ENTER', 'Tab': 'Keys.TAB', 'Escape': 'Keys.ESCAPE',
                'Space': 'Keys.SPACE', 'Backspace': 'Keys.BACK_SPACE', 'Delete': 'Keys.DELETE',
                'ArrowUp': 'Keys.ARROW_UP', 'ArrowDown': 'Keys.ARROW_DOWN',
                'ArrowLeft': 'Keys.ARROW_LEFT', 'ArrowRight': 'Keys.ARROW_RIGHT',
            }
            keys_const = key_map.get(key_name, 'Keys.ENTER')
            msg_r = repr(f'Pressed {key_name}')
            if selector:
                find_lines = _element_find_code(selector_type, selector, ec_type='presence')
                send_lines = find_lines + [f"            element.send_keys({keys_const})"]
            else:
                send_lines = [f"            ActionChains(driver).send_keys({keys_const}).perform()"]
            script_lines.extend([
                f"        # Step {i}: Key press",
                f"        try:",
            ] + send_lines + [
                f"            time.sleep(0.3)",
                f"            step_results.append({{'step': {i}, 'action': 'key_press', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'key_press', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'hover':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Hovered over {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='presence')
            script_lines.extend([
                f"        # Step {i}: Hover over element",
                f"        try:",
            ] + find_lines + [
                f"            ActionChains(driver).move_to_element(element).perform()",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'hover', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'hover', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'double_click':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Double-clicked {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='clickable')
            script_lines.extend([
                f"        # Step {i}: Double-click element",
                f"        try:",
            ] + find_lines + [
                f"            ActionChains(driver).double_click(element).perform()",
                f"            time.sleep(0.5)",
                f"            step_results.append({{'step': {i}, 'action': 'double_click', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'double_click', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'wait_for_element':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            timeout = step.get('value', '10')
            try:
                timeout_val = float(timeout)
            except (ValueError, TypeError):
                timeout_val = 10.0
            msg_r = repr(f'Element {selector} appeared')
            find_lines = _element_find_code(selector_type, selector, ec_type='visible', timeout=int(timeout_val))
            script_lines.extend([
                f"        # Step {i}: Wait for element",
                f"        try:",
            ] + find_lines + [
                f"            step_results.append({{'step': {i}, 'action': 'wait_for_element', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'wait_for_element', 'status': 'error', 'message': str(e)}})",
                f"            raise",
                f"        finally:",
                f"            _save_har({i})",
            ])

        elif action == 'clear':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Cleared {selector}')
            find_lines = _element_find_code(selector_type, selector, ec_type='presence')
            script_lines.extend([
                f"        # Step {i}: Clear input",
                f"        try:",
            ] + find_lines + [
                f"            element.clear()",
                f"            time.sleep(0.3)",
                f"            step_results.append({{'step': {i}, 'action': 'clear', 'status': 'success', 'message': {msg_r}}})",
                f"        except Exception as e:",
                f"            step_results.append({{'step': {i}, 'action': 'clear', 'status': 'error', 'message': str(e)}})",
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
        "                'ffmpeg', '-y', '-framerate', '4', '-start_number', '1',",
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
