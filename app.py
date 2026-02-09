from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import json
import subprocess
import tempfile
import os
from database import Database
from test_generator import generate_selenium_script
from models import User

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
db = Database()

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
    executions = db.get_all_executions(team_id=team['id'])
    return render_template('view_executions.html', executions=executions, team=team)

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
    script = generate_selenium_script(steps)
    
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

@app.route('/api/tests/<int:test_id>/execute', methods=['POST'])
@login_required
def execute_test(test_id):
    """API endpoint to execute a test"""
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    
    if not test:
        return jsonify({'error': 'Test not found'}), 404
    
    print(f"\n{'='*60}")
    print(f"EXECUTING TEST: {test['name']} (ID: {test_id})")
    print(f"{'='*60}")
    
    # Create a temporary file with the script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test['script'])
        temp_script_path = f.name
    
    print(f"Temporary script path: {temp_script_path}")
    print(f"Script preview (first 500 chars):\n{test['script'][:500]}...")
    
    try:
        # Execute the script
        print(f"\nExecuting script...")
        result = subprocess.run(
            ['python', temp_script_path],
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        # Parse output
        output = result.stdout
        error = result.stderr
        
        print(f"\nReturn code: {result.returncode}")
        print(f"STDOUT length: {len(output)} characters")
        print(f"STDERR length: {len(error)} characters")
        print(f"\n--- STDOUT ---\n{output}")
        print(f"\n--- STDERR ---\n{error}")
        
        # Try to parse step results from output
        step_results = ''
        try:
            if 'STEP_RESULTS:' in output:
                # Extract the JSON part after STEP_RESULTS:
                start_idx = output.find('STEP_RESULTS:') + len('STEP_RESULTS:')
                # Find the end of the JSON array (look for the next line or end)
                rest = output[start_idx:].strip()
                # Try to find where JSON ends
                lines = rest.split('\n')
                step_results = lines[0].strip() if lines else ''
                print(f"\nExtracted step_results: {step_results}")
        except Exception as e:
            print(f"Error parsing step results: {e}")
        
        # Determine status
        if result.returncode == 0:
            status = 'success'
        else:
            status = 'error'
        
        print(f"\nStatus: {status}")
        print(f"Step results to save: {step_results}")
        
        # Log execution
        db.log_execution(test_id, status, output, error, step_results, team['id'] if team else None)
        db.update_execution_stats(test_id)
        
        print(f"{'='*60}\n")
        
        return jsonify({
            'status': status,
            'output': output,
            'error': error,
            'return_code': result.returncode
        })
    
    except subprocess.TimeoutExpired:
        db.log_execution(test_id, 'timeout', '', 'Test execution timed out after 60 seconds', '', team['id'] if team else None)
        return jsonify({
            'status': 'timeout',
            'error': 'Test execution timed out after 60 seconds'
        }), 408
    
    except Exception as e:
        db.log_execution(test_id, 'error', '', str(e), '', team['id'] if team else None)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
    
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_script_path)
        except:
            pass

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
    script = generate_selenium_script(steps)
    
    # Update in database
    db.update_test(test_id, name, description, steps, script, team['id'])
    
    return jsonify({
        'success': True,
        'test_id': test_id,
        'message': f'Test "{name}" updated successfully'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
