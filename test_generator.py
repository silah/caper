"""
Generate Playwright scripts from test steps
"""
import re
import os


def _sanitize_name(name):
    return re.sub(r'[^\w\-]', '_', name)


def _pw_selector(selector_type, selector):
    """Convert a selector type + value to a Playwright CSS/pseudo selector string."""
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
    Return lines at 16-space indent that resolve a Playwright locator into var_name.
    Per-step code lives at 12 spaces; inner code at 16.
    get_by_* methods are strict (fail loudly on ambiguity); page.locator() is used for
    CSS/xpath/etc. without .first so ambiguity also fails loudly.
    """
    ind = '                '  # 16 spaces
    if selector_type == 'jspath':
        expr_r = repr(selector)
        return [
            f"{ind}_{var_name}_h = page.evaluate_handle('() => (' + {expr_r} + ')')",
            f"{ind}{var_name} = _{var_name}_h.as_element()",
            f"{ind}assert {var_name} is not None, 'JSPath returned no element: ' + {expr_r}",
        ]
    elif selector_type == 'text':
        return [f"{ind}{var_name} = page.get_by_text({repr(selector)})"]
    elif selector_type == 'label':
        return [f"{ind}{var_name} = page.get_by_label({repr(selector)})"]
    elif selector_type == 'placeholder':
        return [f"{ind}{var_name} = page.get_by_placeholder({repr(selector)})"]
    elif selector_type == 'role':
        # selector format: "role" or "role:accessible name"
        if ':' in selector:
            role_part, name_part = selector.split(':', 1)
            return [f"{ind}{var_name} = page.get_by_role({repr(role_part.strip())}, name={repr(name_part.strip())})"]
        else:
            return [f"{ind}{var_name} = page.get_by_role({repr(selector.strip())})"]
    else:
        sel_r = repr(_pw_selector(selector_type, selector))
        return [f"{ind}{var_name} = page.locator({sel_r})"]


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
        "import json",
        "import os",
        "import datetime",
        "import subprocess as _sp",
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
        "        _context = _browser.new_context(",
        "            record_video_dir=video_dir,",
        "            record_har_path=os.path.join(hars_dir, 'trace.har'),",
        "        )",
        "        page = _context.new_page()",
        "        step_results = []",
        "        _console_errors = []",
        "        page.on('console', lambda msg: _console_errors.append({'type': msg.type, 'text': msg.text}) if msg.type in ('error', 'warning') else None)",
        "        page.on('pageerror', lambda err: _console_errors.append({'type': 'pageerror', 'text': str(err)}))",
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
        if not isinstance(step, dict):
            continue
        action = step.get('action')

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
            ])

        elif action == 'assert_hidden':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Element {selector} is hidden')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Assert hidden",
                f"            try:",
            ] + locator_lines + [
                f"                element.wait_for(state='hidden', timeout=10000)",
                f"                step_results.append({{'step': {i}, 'action': 'assert_hidden', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'assert_hidden', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
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
            ])

        elif action == 'assert_value':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            expected_r = repr(step.get('value', ''))
            msg_r = repr(f'Value assertion passed on {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Assert input value",
                f"            try:",
            ] + locator_lines + [
                f"                _actual = element.input_value()",
                f"                assert {expected_r} in _actual, 'Expected value to contain ' + {expected_r} + ', got: ' + _actual",
                f"                step_results.append({{'step': {i}, 'action': 'assert_value', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'assert_value', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
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
            ])

        elif action == 'right_click':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Right-clicked {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Right-click",
                f"            try:",
            ] + locator_lines + [
                f"                element.click(button='right')",
                f"                step_results.append({{'step': {i}, 'action': 'right_click', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'right_click', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
            ])

        elif action == 'check':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Checked {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Check",
                f"            try:",
            ] + locator_lines + [
                f"                element.check()",
                f"                step_results.append({{'step': {i}, 'action': 'check', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'check', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
            ])

        elif action == 'uncheck':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            msg_r = repr(f'Unchecked {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Uncheck",
                f"            try:",
            ] + locator_lines + [
                f"                element.uncheck()",
                f"                step_results.append({{'step': {i}, 'action': 'uncheck', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'uncheck', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
            ])

        elif action == 'upload_file':
            selector_type = step.get('selectorType', 'css')
            selector = step.get('selector', '')
            file_path_r = repr(step.get('value', ''))
            msg_r = repr(f'Uploaded file to {selector}')
            locator_lines = _pw_locator_lines(selector_type, selector)
            script_lines.extend([
                f"            # Step {i}: Upload file",
                f"            try:",
            ] + locator_lines + [
                f"                element.set_input_files({file_path_r})",
                f"                step_results.append({{'step': {i}, 'action': 'upload_file', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'upload_file', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
            ])

        elif action == 'wait_for_load_state':
            state_r = repr(step.get('value', 'networkidle'))
            msg_r = repr(f'Waited for load state: {step.get("value", "networkidle")}')
            script_lines.extend([
                f"            # Step {i}: Wait for load state",
                f"            try:",
                f"                page.wait_for_load_state({state_r})",
                f"                step_results.append({{'step': {i}, 'action': 'wait_for_load_state', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'wait_for_load_state', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
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
            ])

        elif action == 'drag_and_drop':
            src_type = step.get('selectorType', 'css')
            src_sel = step.get('selector', '')
            tgt_type = step.get('targetSelectorType', 'css')
            tgt_sel = step.get('targetSelector', '')
            msg_r = repr(f'Dragged {src_sel} to {tgt_sel}')
            src_lines = _pw_locator_lines(src_type, src_sel, var_name='_src')
            tgt_lines = _pw_locator_lines(tgt_type, tgt_sel, var_name='_tgt')
            script_lines.extend([
                f"            # Step {i}: Drag and drop",
                f"            try:",
            ] + src_lines + tgt_lines + [
                f"                _src.drag_to(_tgt)",
                f"                step_results.append({{'step': {i}, 'action': 'drag_and_drop', 'status': 'success', 'message': {msg_r}}})",
                f"            except Exception as e:",
                f"                step_results.append({{'step': {i}, 'action': 'drag_and_drop', 'status': 'error', 'message': str(e)}})",
                f"                raise",
                f"            finally:",
                f"                _screenshot({i})",
            ])

        script_lines.append("")

    script_lines.extend([
        "            print('STEP_RESULTS:', json.dumps(step_results))",
        "            print('CONSOLE_ERRORS:', json.dumps(_console_errors))",
        "            return {'status': 'success', 'message': 'Test completed successfully'}",
        "",
        "        except Exception as e:",
        "            print('STEP_RESULTS:', json.dumps(step_results))",
        "            print('CONSOLE_ERRORS:', json.dumps(_console_errors))",
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
