from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import json
import re
import subprocess
import tempfile
import os
import threading
from database import Database
from test_generator import generate_selenium_script
from models import User

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
db = Database()

BASE_ARTEFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'artefacts')

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    user_dict = db.get_user_by_id(int(user_id))
    return User.from_dict(user_dict)

# Helper function to get current user's team
def get_current_team():
    if not current_user.is_authenticated:
        return None
    return db.get_user_team(current_user.id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
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
    """Registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        action = request.form.get('action')  # 'create' or 'join'
        
        # Create user
        user_id = db.create_user(username, email, password)
        if not user_id:
            flash('Username or email already exists', 'error')
            return render_template('register.html')
        
        # Handle team creation or joining
        if action == 'create':
            team_name = request.form.get('team_name')
            team_id, reg_code = db.create_team(team_name, user_id)
            if team_id:
                flash(f'Team created! Registration code: {reg_code}', 'success')
            else:
                flash('Team name already exists', 'error')
                return render_template('register.html')
        elif action == 'join':
            reg_code = request.form.get('registration_code')
            if db.join_team(user_id, reg_code):
                flash('Successfully joined team!', 'success')
            else:
                flash('Invalid registration code', 'error')
                return render_template('register.html')
        
        # Log user in with Flask-Login
        user_dict = db.get_user_by_id(user_id)
        user = User.from_dict(user_dict)
        login_user(user)
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Home page"""
    team = get_current_team()
    return render_template('index.html', team=team)

@app.route('/create')
@login_required
def create():
    """Test creation page"""
    team = get_current_team()
    if not team:
        flash('You must be part of a team to create tests', 'error')
        return redirect(url_for('index'))
    return render_template('create_test.html', team=team)

@app.route('/tests')
@login_required
def view_tests():
    """View all tests"""
    team = get_current_team()
    if not team:
        flash('You must be part of a team to view tests', 'error')
        return redirect(url_for('index'))
    tests = db.get_all_tests(team_id=team['id'])
    return render_template('view_tests.html', tests=tests, team=team)

@app.route('/executions')
@login_required
def view_executions():
    """View all test executions"""
    team = get_current_team()
    if not team:
        flash('You must be part of a team to view executions', 'error')
        return redirect(url_for('index'))
    tests = db.get_executions_grouped_by_test(team_id=team['id'])
    return render_template('view_executions.html', tests=tests, team=team)

@app.route('/api/tests', methods=['POST'])
@login_required
def create_test():
    """API endpoint to create a new test"""
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You must be part of a team'}), 403
    
    data = request.json
    
    name = data.get('name')
    description = data.get('description', '')
    steps = data.get('steps', [])
    
    if not name or not steps:
        return jsonify({'error': 'Name and steps are required'}), 400
    
    # Generate Selenium script
    script = generate_selenium_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR)

    # Save to database
    test_id = db.create_test(name, description, steps, script, team['id'])
    
    return jsonify({
        'success': True,
        'test_id': test_id,
        'message': f'Test "{name}" created successfully'
    })

@app.route('/api/tests/<int:test_id>')
@login_required
def get_test(test_id):
    """API endpoint to get a specific test"""
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    
    if not test:
        return jsonify({'error': 'Test not found'}), 404
    
    return jsonify(test)

def _run_test_subprocess(test_id, script, execution_id):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        temp_script_path = f.name

    try:
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

        db.update_execution(execution_id, status, output, error, step_results, artefact_dir)
        db.update_execution_stats(test_id)

    except subprocess.TimeoutExpired:
        db.update_execution(execution_id, 'timeout', '', 'Test execution timed out after 60 seconds', '')

    except Exception as e:
        db.update_execution(execution_id, 'error', '', str(e), '')

    finally:
        try:
            os.unlink(temp_script_path)
        except Exception:
            pass


@app.route('/api/tests/<int:test_id>/execute', methods=['POST'])
@login_required
def execute_test(test_id):
    """API endpoint to execute a test"""
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)

    if not test:
        return jsonify({'error': 'Test not found'}), 404

    execution_id = db.create_execution(test_id, team['id'] if team else None)

    thread = threading.Thread(
        target=_run_test_subprocess,
        args=(test_id, test['script'], execution_id),
        daemon=True
    )
    thread.start()

    return jsonify({'execution_id': execution_id, 'status': 'running'})


@app.route('/api/executions/<int:execution_id>/status')
@login_required
def get_execution_status(execution_id):
    """Poll endpoint for async execution status"""
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
    """API endpoint to get execution history for a test"""
    team = get_current_team()
    executions = db.get_test_executions(test_id, team_id=team['id'] if team else None)
    return jsonify(executions)

@app.route('/api/tests/<int:test_id>', methods=['DELETE'])
@login_required
def delete_test(test_id):
    """API endpoint to delete a test"""
    team = get_current_team()
    db.delete_test(test_id, team_id=team['id'] if team else None)
    return jsonify({'success': True, 'message': 'Test deleted successfully'})

@app.route('/test/<int:test_id>')
@login_required
def test_detail(test_id):
    """Test detail and execution page"""
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    
    if not test:
        return "Test not found", 404
    
    executions = db.get_test_executions(test_id, team_id=team['id'] if team else None)
    
    return render_template('test_detail.html', test=test, executions=executions, team=team)

@app.route('/edit/<int:test_id>')
@login_required
def edit_test(test_id):
    """Edit test page"""
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    
    if not test:
        return "Test not found", 404
    
    return render_template('edit_test.html', test=test, team=team)

@app.route('/api/tests/<int:test_id>', methods=['PUT'])
@login_required
def update_test(test_id):
    """API endpoint to update an existing test"""
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You must be part of a team'}), 403
    
    data = request.json
    
    name = data.get('name')
    description = data.get('description', '')
    steps = data.get('steps', [])
    
    if not name or not steps:
        return jsonify({'error': 'Name and steps are required'}), 400
    
    # Generate Selenium script
    script = generate_selenium_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR)

    # Update in database
    db.update_test(test_id, name, description, steps, script, team['id'])
    
    return jsonify({
        'success': True,
        'test_id': test_id,
        'message': f'Test "{name}" updated successfully'
    })

def _extract_querySelector_arg(jspath):
    """Pull the CSS selector string out of document.querySelector("...") expressions."""
    m = re.match(r'''document\.querySelector\s*\(\s*["'](.+?)["']\s*\)''', jspath.strip())
    return m.group(1) if m else None


def _map_selector_type(st):
    return {'id': 'id', 'css': 'css', 'xpath': 'xpath', 'name': 'name',
            'class': 'class', 'tag': 'tag'}.get(st, 'css')


def _map_imported_step(raw):
    step_type = raw.get('type', '')
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
                skipped.append({
                    'name': raw_step.get('name', '(unnamed)'),
                    'type': raw_step.get('type', '(unknown)'),
                })

    if not steps:
        return jsonify({'error': 'No recognisable steps found in the file'}), 400

    script = generate_selenium_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR)
    test_id = db.create_test(name, '', steps, script, team['id'])

    return jsonify({'success': True, 'test_id': test_id,
                    'message': f'Imported "{name}" with {len(steps)} steps',
                    'skipped': skipped})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5098)
