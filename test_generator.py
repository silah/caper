"""
Generate Playwright scripts from test steps
"""
import re
import os


def _sanitize_name(name):
    return re.sub(r'[^\w\-]', '_', name)


def _pw_selector(selector_type, selector):
    """Convert a selector type + value to a Playwright-compatible selector string."""
    if selector_type == 'id':
        return f'[id="{selector}"]'
    elif selector_type == 'name':
        return f'[name="{selector}"]'
    elif selector_type == 'class':
        return f'.{selector}'
    elif selector_type == 'xpath':
        return f'xpath={selector}'
    elif selector_type == 'link_text':
        return f'a:text-is("{selector}")'
    elif selector_type == 'partial_link_text':
        return f'a:has-text("{selector}")'
    elif selector_type == 'aria':
        return f'[aria-label="{selector}"]'
    else:  # css, tag, or unknown
        return selector


def _pw_locator_lines(selector_type, selector, var_name='element'):
    """
    Return lines at 16-space indent that resolve a locator into var_name.
    (Per-step code lives at 12 spaces; inner code at 16.)
    """
    if selector_type == 'jspath':
        expr_r = repr(selector)
        return [
            f"                _{var_name}_h = page.evaluate_handle('() => (' + {expr_r} + ')')",
            f"                {var_name} = _{var_name}_h.as_element()",
            f"                assert {var_name} is not None, 'JSPath returned no element: ' + {expr_r}",
        ]
    sel_r = repr(_pw_selector(selector_type, selector))
    return [f"                {var_name} = page.locator({sel_r}).first"]


def generate_selenium_script(steps, test_name='test', base_artefacts_dir=None, browser='firefox'):
    """Generate a Playwright test script from step definitions."""
    if base_artefacts_dir is None:
        base_artefacts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'artefacts')

    test_name_safe = _sanitize_name(test_name)
    # Map legacy 'chrome' to Playwright's 'chromium'
    browser_type = 'chromium' if browser == 'chrome' else (browser or 'firefox')
    browser_r = repr(browser_type)

    script_lines = [
        "from playwright.sync_api import sync_playwright",
        "import time",
        "import json",
        "import os",
        "import datetime",
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
        f"    with sync_playwright() as _pw:",
        f"        _browser = getattr(_pw, {browser_r}).launch(headless=True)",
        "        _context = _browser.new_context(record_video_dir=video_dir)",
        "        page = _context.new_page()",
        "        step_results = []",
        "",
        "        def _save_har(step_num):",
        "            try:",
        "                raw = page.evaluate('JSON.stringify(window.performance.getEntriesByType(\"resource\"))')",
        "                resources = json.loads(raw) if raw else []",
        "                har_data = _performance_to_har(resources)",
        "                with open(os.path.join(hars_dir, f'step_{step_num:03d}.har'), 'w') as _f:",
        "                    json.dump(har_data, _f, indent=2)",
        "            except Exception:",
        "                pass",
        "            try:",
        "                page.evaluate('window.performance.clearResourceTimings()')",
        "            except Exception:",
        "                pass",
        "",
        "        def _screenshot(step_num):",
        "            try:",
        "                page.screenshot(path=os.path.join(screenshots_dir, f'{step_num:04d}.png'))",
        "            except Exception:",
        "                pass",
        "",
        "        try:",
    ]

    for i, step in enumerate(steps, 1):
        action = step.get('action')

        # Clear perf timings before each step
        script_lines.extend([
            "            try:",
            "                page.evaluate('window.performance.clearResourceTimings()')",
            "            except Exception:",
            "                pass",
        ])

        if action == 'navigate':
            url_r = repr(step.get('value', ''))
            msg_r = repr(f'Navigated to {step.get("value", "")}')
            script_lines.extend([
                f"            # Step {i}: Navigate",
                f"            try:",
                f"                page.goto({url_r})",
                f"                step_results.append({{'step': {i}, 'action': 'navigate', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'navigate', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'click':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Clicked {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Click",
                f"            try:",
            ] + locator_lines + [
                f"                element.click()",
                f"                step_results.append({{'step': {i}, 'action': 'click', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'click', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'type':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            text_r = repr(step.get('value', ''))
            msg_r = repr(f'Typed into {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Type",
                f"            try:",
            ] + locator_lines + [
                f"                element.fill({text_r})",
                f"                step_results.append({{'step': {i}, 'action': 'type', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'type', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'wait':
            try:
                seconds_val = float(step.get('value', '1'))
            except (ValueError, TypeError):
                seconds_val = 1.0
            msg_r = repr(f'Waited {seconds_val}s')
            script_lines.extend([
                f"            # Step {i}: Wait",
                f"            try:",
                f"                page.wait_for_timeout({int(seconds_val * 1000)})",
                f"                step_results.append({{'step': {i}, 'action': 'wait', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'wait', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'execute_js':
            js_r = repr(step.get('value', ''))
            script_lines.extend([
                f"            # Step {i}: Execute JS",
                f"            try:",
                f"                page.evaluate({js_r})",
                f"                step_results.append({{'step': {i}, 'action': 'execute_js', 'status': 'success', 'message': 'Executed JavaScript'}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'execute_js', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'screenshot':
            script_lines.extend([
                f"            # Step {i}: Screenshot",
                f"            try:",
                f"                _screenshot({i})",
                f"                step_results.append({{'step': {i}, 'action': 'screenshot', 'status': 'success', 'message': 'Screenshot taken'}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'screenshot', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _save_har({i})",
            ])

        elif action == 'assert_title':
            title_r = repr(step.get('value', ''))
            script_lines.extend([
                f"            # Step {i}: Assert title",
                f"            try:",
                f"                _title = page.title()",
                f"                assert {title_r} in _title, 'Expected title to contain ' + {title_r} + ', got: ' + _title",
                f"                step_results.append({{'step': {i}, 'action': 'assert_title', 'status': 'success', 'message': 'Title assertion passed'}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'assert_title', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'assert_text':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            text_r = repr(step.get('value', ''))
            msg_r = repr(f'Text assertion passed on {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Assert text",
                f"            try:",
            ] + locator_lines + [
                f"                _actual = element.text_content() or ''",
                f"                assert {text_r} in _actual, 'Expected text to contain ' + {text_r} + ', got: ' + _actual",
                f"                step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'assert_text', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'scroll_to':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Scrolled to {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Scroll to element",
                f"            try:",
            ] + locator_lines + [
                f"                element.scroll_into_view_if_needed()",
                f"                step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'scroll_to', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'select':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            option_r = repr(step.get('value', ''))
            select_by = step.get('selectBy', 'text')
            msg_r = repr(f'Selected in {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            if select_by == 'value':
                select_call = f"element.select_option(value={option_r})"
            elif select_by == 'index':
                select_call = f"element.select_option(index=int({option_r}))"
            else:
                select_call = f"element.select_option(label={option_r})"
            script_lines.extend([
                f"            # Step {i}: Select dropdown",
                f"            try:",
            ] + locator_lines + [
                f"                {select_call}",
                f"                step_results.append({{'step': {i}, 'action': 'select', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'select', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'assert_visible':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Element {selector} is visible')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Assert visible",
                f"            try:",
            ] + locator_lines + [
                f"                element.wait_for(state='visible', timeout=10000)",
                f"                step_results.append({{'step': {i}, 'action': 'assert_visible', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'assert_visible', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'assert_url':
            expected_r = repr(step.get('value', ''))
            msg_r = repr(f'URL contains "{step.get("value", "")}"')
            script_lines.extend([
                f"            # Step {i}: Assert URL",
                f"            try:",
                f"                _url = page.url",
                f"                assert {expected_r} in _url, 'Expected URL to contain ' + {expected_r} + ', got: ' + _url",
                f"                step_results.append({{'step': {i}, 'action': 'assert_url', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'assert_url', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'key_press':
            key_name = step.get('key', 'Enter')
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            key_r = repr(key_name)
            msg_r = repr(f'Pressed {key_name}')
            if selector:
                locator_lines = _pw_locator_lines(selector_type, selector)
                press_lines = locator_lines + [f"                element.press({key_r})"]
            else:
                press_lines = [f"                page.keyboard.press({key_r})"]
            script_lines.extend([
                f"            # Step {i}: Key press",
                f"            try:",
            ] + press_lines + [
                f"                step_results.append({{'step': {i}, 'action': 'key_press', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'key_press', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'hover':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Hovered over {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Hover",
                f"            try:",
            ] + locator_lines + [
                f"                element.hover()",
                f"                step_results.append({{'step': {i}, 'action': 'hover', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'hover', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'double_click':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Double-clicked {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Double-click",
                f"            try:",
            ] + locator_lines + [
                f"                element.dblclick()",
                f"                step_results.append({{'step': {i}, 'action': 'double_click', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'double_click', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'wait_for_element':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            try:
                timeout_ms = int(float(step.get('value', '10')) * 1000)
            except (ValueError, TypeError):
                timeout_ms = 10000
            msg_r = repr(f'Element {selector} appeared')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Wait for element",
                f"            try:",
            ] + locator_lines + [
                f"                element.wait_for(state='visible', timeout={timeout_ms})",
                f"                step_results.append({{'step': {i}, 'action': 'wait_for_element', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'wait_for_element', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        elif action == 'clear':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Cleared {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Clear input",
                f"            try:",
            ] + locator_lines + [
                f"                element.clear()",
                f"                step_results.append({{'step': {i}, 'action': 'clear', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'clear', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
                f"                _save_har({i})",
            ])

        script_lines.append("")

    script_lines.extend([
        "            print('STEP_RESULTS:', json.dumps(step_results))",
        "            return {'status': 'success', 'message': 'Test completed successfully'}",
        "",
        "        except Exception as e:",
        "            print('STEP_RESULTS:', json.dumps(step_results))",
        "            return {'status': 'error', 'message': str(e)}",
        "",
        "        finally:",
        "            _video_path = None",
        "            try:",
        "                if page.video:",
        "                    _video_path = page.video.path()",
        "            except Exception:",
        "                pass",
        "            _context.close()",
        "            _browser.close()",
        "            if _video_path and os.path.exists(_video_path):",
        "                _sp.run([",
        "                    'ffmpeg', '-y', '-i', _video_path,",
        "                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p',",
        "                    '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',",
        "                    os.path.join(video_dir, 'recording.mp4'),",
        "                ], capture_output=True)",
        "",
        "if __name__ == '__main__':",
        "    result = run_test()",
        "    print(result)",
    ])

    return '\n'.join(script_lines)
