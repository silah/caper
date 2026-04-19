from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import json
import re
import ssl
import subprocess
import tempfile
import os
import threading
import time
import urllib.request
from database import Database
from test_generator import generate_selenium_script
from models import User
import ai_client

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
db = Database()

BASE_ARTEFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'artefacts')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    user_dict = db.get_user_by_id(int(user_id))
    return User.from_dict(user_dict)

def get_current_team():
    if not current_user.is_authenticated:
        return None
    return db.get_user_team(current_user.id)

@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        user_dict = db.verify_password(username, password)
        if user_dict:
            user = User.from_dict(user_dict)
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        action = request.form.get('action')
        user_id = db.create_user(username, email, password)
        if not user_id:
            flash('Username or email already exists', 'error')
            return render_template('register.html', teams=db.get_all_teams())
        if action == 'create':
            team_name = request.form.get('team_name')
            team_id, reg_code = db.create_team(team_name, user_id)
            if team_id:
                flash(f'Team created! Registration code: {reg_code}', 'success')
            else:
                flash('Team name already exists', 'error')
                return render_template('register.html', teams=db.get_all_teams())
        elif action == 'join':
            team_id = request.form.get('team_id')
            if team_id and db.join_team_by_id(user_id, int(team_id)):
                flash('Successfully joined team!', 'success')
            else:
                flash('Could not join team', 'error')
                return render_template('register.html', teams=db.get_all_teams())
        user_dict = db.get_user_by_id(user_id)
        user = User.from_dict(user_dict)
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html', teams=db.get_all_teams())

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    team = get_current_team()
    return render_template('index.html', team=team)

@app.route('/create')
@login_required
def create():
    team = get_current_team()
    if not team:
        flash('You must be part of a team to create tests', 'error')
        return redirect(url_for('index'))
    return render_template('create_test.html', team=team)

@app.route('/tests')
@login_required
def view_tests():
    team = get_current_team()
    if not team:
        flash('You must be part of a team to view tests', 'error')
        return redirect(url_for('index'))
    tests = db.get_all_tests(team_id=team['id'])
    return render_template('view_tests.html', tests=tests, team=team)

@app.route('/executions')
@login_required
def view_executions():
    team = get_current_team()
    if not team:
        flash('You must be part of a team to view executions', 'error')
        return redirect(url_for('index'))
    tests = db.get_executions_grouped_by_test(team_id=team['id'])
    return render_template('view_executions.html', tests=tests, team=team)

@app.route('/health')
@login_required
def health_dashboard():
    team = get_current_team()
    if not team:
        flash('You must be part of a team to view the health dashboard', 'error')
        return redirect(url_for('index'))
    tests = db.get_health_dashboard(team_id=team['id'])
    stats = {
        'passing': sum(1 for t in tests if t.get('last_status') == 'success'),
        'failing': sum(1 for t in tests if t.get('last_status') in ('error', 'timeout')),
        'running': sum(1 for t in tests if t.get('last_status') == 'running'),
        'never': sum(1 for t in tests if t.get('last_status') is None),
        'total': len(tests),
    }
    return render_template('health.html', tests=tests, stats=stats, team=team)

@app.route('/compare/<int:exec_a>/<int:exec_b>')
@login_required
def compare_executions(exec_a, exec_b):
    team = get_current_team()
    a = db.get_execution(exec_a)
    b = db.get_execution(exec_b)
    if not a or not b:
        return "Execution not found", 404
    if team:
        if (a.get('team_id') and a['team_id'] != team['id']) or \
           (b.get('team_id') and b['team_id'] != team['id']):
            return "Not found", 404
    test_a = db.get_test(a['test_id'], team_id=team['id'] if team else None)
    test_b = db.get_test(b['test_id'], team_id=team['id'] if team else None)
    return render_template('compare.html', exec_a=a, exec_b=b,
                           test_a=test_a, test_b=test_b, team=team)

@app.route('/variables')
@login_required
def variables_page():
    team = get_current_team()
    if not team:
        flash('You must be part of a team to manage variables', 'error')
        return redirect(url_for('index'))
    variables = db.get_team_variables(team['id'])
    return render_template('variables.html', variables=variables, team=team)

@app.route('/api/variables', methods=['GET'])
@login_required
def api_get_variables():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    variables = db.get_team_variables(team['id'])
    # Mask secret values
    masked = []
    for v in variables:
        masked.append({
            'key': v['key'],
            'value': '••••••••' if v['is_secret'] else v['value'],
            'is_secret': v['is_secret'],
            'created_at': v['created_at'],
        })
    return jsonify(masked)

@app.route('/api/variables', methods=['POST'])
@login_required
def api_set_variable():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    data = request.json
    key = (data.get('key') or '').strip()
    value = data.get('value', '')
    is_secret = bool(data.get('is_secret', False))
    if not key or not re.match(r'^[A-Z0-9_]+$', key):
        return jsonify({'error': 'Key must be uppercase letters, digits, and underscores'}), 400
    db.set_team_variable(team['id'], key, value, is_secret)
    return jsonify({'success': True})

@app.route('/api/variables/<key>', methods=['DELETE'])
@login_required
def api_delete_variable(key):
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    db.delete_team_variable(team['id'], key)
    return jsonify({'success': True})


@app.route('/api/ai/generate-test', methods=['POST'])
@login_required
def api_ai_generate_test():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    data = request.json or {}
    prompt = (data.get('prompt') or '').strip()
    name   = (data.get('name') or 'AI Generated Test').strip()
    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400
    variables = db.get_team_variables(team['id'])
    config = ai_client.get_ai_config(variables)
    if not config.get('model'):
        return jsonify({'error': 'AI is not configured. Add CAPER_AI_PROVIDER, CAPER_AI_MODEL and CAPER_AI_API_KEY in Variables.'}), 400
    try:
        steps = ai_client.generate_test_steps(prompt, config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    try:
        script = generate_selenium_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR)
        test_id = db.create_test(
            name=name,
            description=prompt,
            steps=json.dumps(steps),
            script=script,
            team_id=team['id'],
        )
    except Exception as e:
        return jsonify({'error': f'Failed to save test: {e}'}), 500
    return jsonify({'success': True, 'test_id': test_id})


@app.route('/api/ai/describe-test', methods=['POST'])
@login_required
def api_ai_describe_test():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    data = request.json or {}
    steps = data.get('steps')
    if not steps or not isinstance(steps, list):
        return jsonify({'error': 'steps array is required'}), 400
    variables = db.get_team_variables(team['id'])
    config = ai_client.get_ai_config(variables)
    if not config.get('model'):
        return jsonify({'error': 'AI is not configured. Add CAPER_AI_PROVIDER, CAPER_AI_MODEL and CAPER_AI_API_KEY in Variables.'}), 400
    try:
        description = ai_client.describe_test(steps, config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'success': True, 'description': description})


@app.route('/tags')
@login_required
def tags_page():
    team = get_current_team()
    if not team:
        flash('You must be part of a team to manage tags', 'error')
        return redirect(url_for('index'))
    all_tags = db.get_tags(team['id'])
    categories = [
        ('status',      'Status'),
        ('environment', 'Environment'),
        ('application', 'Application'),
        ('suite',       'Test Suite'),
    ]
    grouped = {cat: [] for cat, _ in categories}
    for tag in all_tags:
        if tag['category'] in grouped:
            grouped[tag['category']].append(tag)
    return render_template('tags.html', grouped=grouped, categories=categories, team=team)


@app.route('/api/tags', methods=['GET'])
@login_required
def api_get_tags():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    return jsonify(db.get_tags(team['id']))


@app.route('/api/tags', methods=['POST'])
@login_required
def api_create_tag():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    data = request.json
    name = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    if not name or category not in ('status', 'environment', 'application', 'suite'):
        return jsonify({'error': 'Invalid name or category'}), 400
    tag_id = db.create_tag(team['id'], name, category)
    if tag_id is None:
        return jsonify({'error': 'Tag already exists in this category'}), 409
    return jsonify({'success': True, 'id': tag_id, 'name': name, 'category': category})


@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
@login_required
def api_delete_tag(tag_id):
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    db.delete_tag(tag_id, team['id'])
    return jsonify({'success': True})


@app.route('/api/tests/<int:test_id>/tags', methods=['GET'])
@login_required
def api_get_test_tags(test_id):
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    return jsonify(db.get_test_tags(test_id))


def _run_suite(suite_id, suite_execution_id, team_id):
    start_time = time.time()
    suite = db.get_suite(suite_id)
    if not suite:
        db.update_suite_execution(suite_execution_id, 'error', 0)
        return

    stop_on_failure = suite.get('stop_on_failure', 0)
    tests = suite.get('tests', [])
    all_passed = True

    for position, test in enumerate(tests):
        test_id = test['id']
        execution_id = db.create_execution(test_id, team_id)
        db.add_suite_execution_test(suite_execution_id, test_id, test['name'],
                                    execution_id, position, 'running')
        _run_test_subprocess(test_id, test['script'], execution_id, test['name'],
                             team_id, test.get('retry_count', 0), test.get('sla_seconds'))
        execution = db.get_execution(execution_id)
        status = execution['status'] if execution else 'error'
        db.update_suite_execution_test(suite_execution_id, test_id, status)
        if status != 'success':
            all_passed = False
            if stop_on_failure:
                break

    duration = time.time() - start_time
    final_status = 'success' if all_passed else 'error'
    db.update_suite_execution(suite_execution_id, final_status, duration)
    db.log_event(
        'info' if final_status == 'success' else 'error',
        f'Suite "{suite["name"]}" finished: {final_status.upper()}',
        f'suite_id={suite_id} suite_execution_id={suite_execution_id} '
        f'tests={len(tests)} duration={duration:.1f}s'
    )


@app.route('/suites')
@login_required
def suites_page():
    team = get_current_team()
    if not team:
        return redirect(url_for('index'))
    suites = db.get_suites(team['id'])
    tests = db.get_all_tests(team['id'])
    return render_template('suites.html', suites=suites, tests=tests, team=team)


@app.route('/suites/<int:suite_id>')
@login_required
def suite_detail(suite_id):
    team = get_current_team()
    suite = db.get_suite(suite_id, team_id=team['id'] if team else None)
    if not suite:
        return "Suite not found", 404
    executions = db.get_suite_executions(suite_id)
    all_tests = db.get_all_tests(team['id'] if team else None)
    return render_template('suite_detail.html', suite=suite, executions=executions,
                           all_tests=all_tests, team=team)


@app.route('/api/suites', methods=['POST'])
@login_required
def api_create_suite():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'No team'}), 403
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    suite_id = db.create_suite(team['id'], name,
                                (data.get('description') or '').strip(),
                                1 if data.get('stop_on_failure') else 0)
    if data.get('test_ids'):
        db.set_suite_tests(suite_id, data['test_ids'])
    return jsonify({'success': True, 'suite_id': suite_id})


@app.route('/api/suites/<int:suite_id>', methods=['PUT'])
@login_required
def api_update_suite(suite_id):
    team = get_current_team()
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    db.update_suite(suite_id, name, (data.get('description') or '').strip(),
                    1 if data.get('stop_on_failure') else 0,
                    team_id=team['id'] if team else None)
    if 'test_ids' in data:
        db.set_suite_tests(suite_id, data['test_ids'])
    return jsonify({'success': True})


@app.route('/api/suites/<int:suite_id>', methods=['DELETE'])
@login_required
def api_delete_suite(suite_id):
    team = get_current_team()
    db.delete_suite(suite_id, team_id=team['id'] if team else None)
    return jsonify({'success': True})


@app.route('/api/suites/<int:suite_id>/execute', methods=['POST'])
@login_required
def api_execute_suite(suite_id):
    team = get_current_team()
    suite = db.get_suite(suite_id, team_id=team['id'] if team else None)
    if not suite:
        return jsonify({'error': 'Suite not found'}), 404
    if not suite.get('tests'):
        return jsonify({'error': 'Suite has no tests'}), 400
    team_id = team['id'] if team else None
    suite_execution_id = db.create_suite_execution(suite_id, team_id)
    threading.Thread(target=_run_suite,
                     args=(suite_id, suite_execution_id, team_id),
                     daemon=True).start()
    return jsonify({'suite_execution_id': suite_execution_id, 'status': 'running'})


@app.route('/api/suite-executions/<int:suite_execution_id>/status')
@login_required
def api_suite_execution_status(suite_execution_id):
    ex = db.get_suite_execution(suite_execution_id)
    if not ex:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'status': ex['status'], 'duration_seconds': ex['duration_seconds'],
                    'tests': ex['tests']})


@app.route('/suite-executions')
@login_required
def suite_executions_page():
    team = get_current_team()
    if not team:
        return redirect(url_for('index'))
    executions = db.get_all_suite_executions(team['id'])
    return render_template('suite_executions.html', executions=executions, team=team)


@app.route('/suite-executions/<int:suite_execution_id>')
@login_required
def suite_execution_detail(suite_execution_id):
    team = get_current_team()
    ex = db.get_suite_execution(suite_execution_id)
    if not ex:
        return "Suite execution not found", 404
    for t in ex['tests']:
        if t.get('step_results'):
            try:
                t['steps_parsed'] = json.loads(t['step_results'])
            except Exception:
                t['steps_parsed'] = []
        else:
            t['steps_parsed'] = []
    return render_template('suite_execution_detail.html', ex=ex, team=team)


def _send_webhook(test_id, status):
    test = db.get_test(test_id)
    if not test or not test.get('webhook_enabled') or not test.get('webhook_url'):
        return
    url = test['webhook_url']
    method = (test.get('webhook_method') or 'POST').upper()
    payload_str = test['webhook_payload_success'] if status == 'success' else test['webhook_payload_failure']
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        if method == 'GET':
            req = urllib.request.Request(url)
        else:
            body = (payload_str or '').encode('utf-8')
            req = urllib.request.Request(url, data=body,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            db.log_event('info', f'Webhook sent ({status}): {method} {url}',
                         f'HTTP {resp.status}')
    except Exception as e:
        db.log_event('error', f'Webhook failed ({status}): {method} {url}', str(e))


def _run_test_subprocess(test_id, script, execution_id, test_name='',
                         team_id=None, retry_count=0, sla_seconds=None):
    # Substitute {{VARIABLE}} placeholders with team variables
    if team_id:
        try:
            variables = db.get_team_variables(team_id)
            for var in variables:
                script = script.replace('{{' + var['key'] + '}}', var['value'])
        except Exception:
            pass

    start_time = time.time()
    max_attempts = 1 + max(0, int(retry_count or 0))

    final_status = 'error'
    final_output = ''
    final_error = ''
    final_step_results = ''
    final_artefact_dir = ''

    for attempt in range(max_attempts):
        if attempt > 0:
            db.log_event('info',
                         f'Retrying "{test_name}" (attempt {attempt + 1}/{max_attempts})',
                         f'execution_id={execution_id}')

        temp_script_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                temp_script_path = f.name

            result = subprocess.run(
                ['python3', temp_script_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            output = result.stdout
            error = result.stderr

            step_results = ''
            if 'STEP_RESULTS:' in output:
                start_idx = output.find('STEP_RESULTS:') + len('STEP_RESULTS:')
                rest = output[start_idx:].strip()
                lines = rest.split('\n')
                step_results = lines[0].strip() if lines else ''

            artefact_dir = ''
            for line in output.splitlines():
                if line.startswith('ARTEFACT_DIR:'):
                    artefact_dir = line[len('ARTEFACT_DIR:'):].strip()
                    break

            if result.returncode != 0:
                status = 'error'
            elif step_results:
                try:
                    if any(s.get('status') == 'error' for s in json.loads(step_results)):
                        status = 'error'
                    else:
                        status = 'success'
                except Exception:
                    status = 'success'
            else:
                status = 'success'

            final_status = status
            final_output = output
            final_error = error
            final_step_results = step_results
            final_artefact_dir = artefact_dir

            if status == 'success':
                break

        except subprocess.TimeoutExpired:
            final_status = 'timeout'
            final_error = 'Test execution timed out after 60 seconds'

        except Exception as e:
            import traceback
            final_status = 'error'
            final_error = str(e)
            db.log_event('error', f'Test execution exception: {e}', traceback.format_exc())

        finally:
            if temp_script_path:
                try:
                    os.unlink(temp_script_path)
                except Exception:
                    pass

    duration_seconds = time.time() - start_time
    sla_violated = 1 if (sla_seconds and duration_seconds > float(sla_seconds)) else 0

    db.update_execution(execution_id, final_status, final_output, final_error,
                        final_step_results, final_artefact_dir, duration_seconds, sla_violated)
    db.update_execution_stats(test_id)

    label = f'"{test_name}" ' if test_name else ''
    detail = f'execution_id={execution_id} test_id={test_id} duration={duration_seconds:.1f}s'
    if sla_violated:
        detail += f' SLA_VIOLATED (limit={sla_seconds}s)'
    db.log_event(
        'info' if final_status == 'success' else 'error',
        f'Test {label}finished: {final_status.upper()}',
        detail
    )
    _send_webhook(test_id, final_status)


@app.route('/api/tests', methods=['POST'])
@login_required
def create_test():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You must be part of a team'}), 403
    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    steps = data.get('steps', [])
    if not name or not steps:
        return jsonify({'error': 'Name and steps are required'}), 400
    browser = data.get('browser', 'firefox') if data.get('browser') in ('firefox', 'chrome') else 'firefox'
    script = generate_selenium_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR,
                                      browser=browser)
    test_id = db.create_test(name, description, steps, script, team['id'], browser=browser)
    return jsonify({'success': True, 'test_id': test_id,
                    'message': f'Test "{name}" created successfully'})

@app.route('/api/tests/<int:test_id>')
@login_required
def get_test(test_id):
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    if not test:
        return jsonify({'error': 'Test not found'}), 404
    return jsonify(test)

@app.route('/api/tests/<int:test_id>/execute', methods=['POST'])
@login_required
def execute_test(test_id):
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    if not test:
        return jsonify({'error': 'Test not found'}), 404
    execution_id = db.create_execution(test_id, team['id'] if team else None)
    thread = threading.Thread(
        target=_run_test_subprocess,
        args=(test_id, test['script'], execution_id, test['name'],
              team['id'] if team else None,
              test.get('retry_count', 0),
              test.get('sla_seconds')),
        daemon=True
    )
    thread.start()
    return jsonify({'execution_id': execution_id, 'status': 'running'})


@app.route('/api/executions/<int:execution_id>/status')
@login_required
def get_execution_status(execution_id):
    execution = db.get_execution(execution_id)
    if not execution:
        return jsonify({'error': 'Execution not found'}), 404
    team = get_current_team()
    if team and execution.get('team_id') and execution['team_id'] != team['id']:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'status': execution['status'],
        'output': execution['output'],
        'error': execution['error'],
        'step_results': execution['step_results'],
        'artefact_dir': execution['artefact_dir'],
        'duration_seconds': execution['duration_seconds'],
        'sla_violated': execution['sla_violated'],
    })


@app.route('/artefacts/<path:filename>')
@login_required
def serve_artefact(filename):
    return send_from_directory(BASE_ARTEFACTS_DIR, filename)

@app.route('/api/artefacts/<path:artefact_dir>/screenshots')
@login_required
def list_screenshots(artefact_dir):
    screenshots_dir = os.path.join(BASE_ARTEFACTS_DIR, artefact_dir, 'screenshots')
    if not os.path.isdir(screenshots_dir):
        return jsonify([])
    files = sorted(f for f in os.listdir(screenshots_dir) if f.endswith('.png'))
    return jsonify([f'/artefacts/{artefact_dir}/screenshots/{f}' for f in files])


@app.route('/api/tests/<int:test_id>/executions')
@login_required
def get_test_executions(test_id):
    team = get_current_team()
    executions = db.get_test_executions(test_id, team_id=team['id'] if team else None)
    return jsonify(executions)

@app.route('/api/tests/<int:test_id>', methods=['DELETE'])
@login_required
def delete_test(test_id):
    team = get_current_team()
    db.delete_test(test_id, team_id=team['id'] if team else None)
    return jsonify({'success': True, 'message': 'Test deleted successfully'})

@app.route('/test/<int:test_id>')
@login_required
def test_detail(test_id):
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    if not test:
        return "Test not found", 404
    executions = db.get_test_executions(test_id, team_id=team['id'] if team else None)
    return render_template('test_detail.html', test=test, executions=executions, team=team)

@app.route('/edit/<int:test_id>')
@login_required
def edit_test(test_id):
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    if not test:
        return "Test not found", 404
    test_tags = db.get_test_tags(test_id)
    return render_template('edit_test.html', test=test, team=team, test_tags=test_tags)

@app.route('/api/tests/<int:test_id>', methods=['PUT'])
@login_required
def update_test(test_id):
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You must be part of a team'}), 403
    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    steps = data.get('steps', [])
    if not name or not steps:
        return jsonify({'error': 'Name and steps are required'}), 400

    browser = data.get('browser', 'firefox') if data.get('browser') in ('firefox', 'chrome') else 'firefox'
    script = generate_selenium_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR,
                                      browser=browser)

    try:
        retry_count = max(0, int(data.get('retry_count') or 0))
    except (ValueError, TypeError):
        retry_count = 0
    try:
        sla_seconds_raw = data.get('sla_seconds')
        sla_seconds = int(sla_seconds_raw) if sla_seconds_raw else None
    except (ValueError, TypeError):
        sla_seconds = None

    db.update_test(test_id, name, description, steps, script, team['id'],
                   retry_count=retry_count, sla_seconds=sla_seconds, browser=browser)

    sched = data.get('schedule', {})
    if sched:
        db.set_test_schedule(test_id, sched.get('interval'), bool(sched.get('enabled')))

    wh = data.get('webhook', {})
    if wh is not None:
        db.set_test_webhook(
            test_id,
            bool(wh.get('enabled')),
            wh.get('url', ''),
            wh.get('method', 'POST'),
            wh.get('payload_success', ''),
            wh.get('payload_failure', '')
        )

    tag_ids = data.get('tag_ids', [])
    if isinstance(tag_ids, list):
        db.set_test_tags(test_id, tag_ids)

    return jsonify({'success': True, 'test_id': test_id,
                    'message': f'Test "{name}" updated successfully'})


def _extract_querySelector_arg(jspath):
    m = re.match(r'''document\.querySelector\s*\(\s*["'](.+?)["']\s*\)''', jspath.strip())
    return m.group(1) if m else None

def _map_selector_type(st):
    return {'id': 'id', 'css': 'css', 'xpath': 'xpath', 'name': 'name',
            'class': 'class', 'tag': 'tag'}.get(st, 'css')

_NATIVE_ACTIONS = {
    'navigate', 'click', 'type', 'wait', 'execute_js', 'screenshot',
    'assert_title', 'assert_text', 'assert_visible', 'assert_hidden',
    'assert_url', 'assert_value', 'scroll_to', 'select', 'key_press',
    'hover', 'double_click', 'right_click', 'check', 'uncheck',
    'upload_file', 'wait_for_load_state', 'wait_for_element', 'clear',
    'drag_and_drop',
}


def _map_imported_step(raw):
    step_type = raw.get('type', '')
    # Native Caper format — pass through directly, renaming 'type' → 'action'
    if step_type in _NATIVE_ACTIONS:
        step = {k: v for k, v in raw.items() if k != 'type'}
        step['action'] = step_type
        return step
    name = raw.get('name', '')
    if step_type == 'go_to_url':
        url = raw.get('url') or raw.get('options', {}).get('url', '')
        return {'action': 'navigate', 'value': url}
    if step_type == 'click_element':
        st = raw.get('selectorType', 'css')
        sel = raw.get('selector', '')
        if st == 'jspath':
            css = _extract_querySelector_arg(sel)
            if css:
                return {'action': 'click', 'selectorType': 'css', 'selector': css}
            return {'action': 'execute_js', 'value': f'({sel}).click()'}
        return {'action': 'click', 'selectorType': _map_selector_type(st), 'selector': sel}
    if step_type == 'enter_value':
        st = raw.get('selectorType', 'css')
        sel = raw.get('selector', '')
        val = raw.get('value', '')
        if st == 'jspath':
            css = _extract_querySelector_arg(sel)
            if css:
                return {'action': 'type', 'selectorType': 'css', 'selector': css, 'value': val}
            return {'action': 'execute_js', 'value': f'var el=({sel}); el.value={json.dumps(val)}; el.dispatchEvent(new Event("input"));'}
        return {'action': 'type', 'selectorType': _map_selector_type(st), 'selector': sel, 'value': val}
    if step_type == 'wait':
        seconds = raw.get('duration', 1000) / 1000
        return {'action': 'wait', 'value': str(seconds)}
    if step_type == 'run_javascript':
        return {'action': 'execute_js', 'value': raw.get('value', '')}
    if step_type == 'assert_element_visible':
        st = raw.get('selectorType', 'css')
        sel = raw.get('selector', '')
        label = name or sel
        if st == 'jspath':
            return {'action': 'execute_js',
                    'value': f'if (!({sel})) throw new Error({json.dumps("Element not visible: " + label)});'}
        return {'action': 'assert_text', 'selectorType': _map_selector_type(st), 'selector': sel, 'value': ''}
    return None


@app.route('/api/tests/<int:test_id>/schedule', methods=['POST'])
@login_required
def set_schedule(test_id):
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    if not test:
        return jsonify({'error': 'Test not found'}), 404
    data = request.json
    enabled = bool(data.get('enabled', False))
    interval = data.get('interval')
    if enabled:
        try:
            interval = int(interval)
            if interval < 1:
                return jsonify({'error': 'Interval must be at least 1 minute'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid interval'}), 400
    db.set_test_schedule(test_id, interval, enabled)
    return jsonify({'success': True})


@app.route('/api/tests/import', methods=['POST'])
@login_required
def import_test():
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You must be part of a team'}), 403
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file provided'}), 400
    try:
        data = json.load(f)
    except Exception:
        return jsonify({'error': 'Invalid JSON file'}), 400
    test_data = data.get('test', data)
    name = test_data.get('name', 'Imported Test')
    steps = []
    skipped = []
    for transaction in test_data.get('transactions', []):
        for raw_step in transaction.get('steps', []):
            mapped = _map_imported_step(raw_step)
            if mapped:
                steps.append(mapped)
            else:
                skipped.append({'name': raw_step.get('name', '(unnamed)'),
                                'type': raw_step.get('type', '(unknown)')})
    if not steps:
        return jsonify({'error': 'No recognisable steps found in the file'}), 400
    script = generate_selenium_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR)
    test_id = db.create_test(name, '', steps, script, team['id'])
    return jsonify({'success': True, 'test_id': test_id,
                    'message': f'Imported "{name}" with {len(steps)} steps',
                    'skipped': skipped})


@app.route('/logs')
@login_required
def view_logs():
    per_page = 100
    page = max(1, request.args.get('page', 1, type=int))
    hours = 5
    entries = db.get_logs(hours=hours, page=page, per_page=per_page)
    total = db.get_log_count(hours=hours)
    total_pages = max(1, (total + per_page - 1) // per_page)
    team = get_current_team()
    return render_template('log.html', entries=entries, page=page,
                           total_pages=total_pages, total=total, team=team)


@app.route('/internal-testing')
@login_required
def internal_testing():
    # Pre-create the upload test file so the upload_file step works without manual setup
    try:
        with open('/tmp/caper_test_upload.txt', 'w') as _f:
            _f.write('Caper internal test upload file\n')
    except Exception:
        pass
    return render_template('internal_testing.html')


@app.route('/internal-testing/p2')
@login_required
def internal_testing_p2():
    return render_template('internal_testing_p2.html')


@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    db.log_event('error', f'{type(e).__name__}: {e}', traceback.format_exc())
    raise e


def _scheduler_loop():
    db.log_event('info', 'Scheduler started')
    tick = 0
    while True:
        time.sleep(30)
        tick += 1
        try:
            due = db.get_due_scheduled_tests()
            if due:
                for test in due:
                    db.advance_next_run(test['id'], test['schedule_interval'])
                    execution_id = db.create_execution(test['id'], test.get('team_id'))
                    db.log_event('info', f'Scheduled run started: {test["name"]}',
                                 f'test_id={test["id"]} execution_id={execution_id} '
                                 f'interval={test["schedule_interval"]}m')
                    threading.Thread(
                        target=_run_test_subprocess,
                        args=(test['id'], test['script'], execution_id, test['name'],
                              test.get('team_id'),
                              test.get('retry_count', 0),
                              test.get('sla_seconds')),
                        daemon=True
                    ).start()
            if tick % 10 == 0:
                db.log_event('info', f'Scheduler heartbeat (tick {tick})')
        except Exception as e:
            import traceback
            db.log_event('error', f'Scheduler error: {e}', traceback.format_exc())


_scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
_scheduler_thread.start()


def _migrate_selenium_scripts():
    """Regenerate any test scripts that still use the old Selenium API."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, steps, browser FROM tests')
    rows = cursor.fetchall()
    conn.close()
    migrated = 0
    for row in rows:
        test_id = row['id']
        steps_raw = row['steps']
        browser = row['browser'] or 'firefox'
        if not steps_raw:
            continue
        try:
            steps = json.loads(steps_raw if isinstance(steps_raw, str) else steps_raw.decode('utf-8'))
        except Exception:
            continue
        new_script = generate_selenium_script(steps, browser)
        conn2 = db.get_connection()
        conn2.execute('UPDATE tests SET script = ? WHERE id = ?', (new_script.encode('utf-8'), test_id))
        conn2.commit()
        conn2.close()
        migrated += 1
    if migrated:
        db.log_event('info', f'Playwright migration: regenerated scripts for {migrated} test(s)', None)


_migrate_selenium_scripts()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5098, use_reloader=False)
