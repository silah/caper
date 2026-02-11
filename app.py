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

# Helper function to check if user has pending membership
def check_pending_redirect():
    """Check if user has pending membership and redirect if needed"""
    if current_user.is_authenticated:
        pending_team = db.has_pending_membership(current_user.id)
        if pending_team:
            return redirect(url_for('pending_approval'))
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        # Check if user has pending membership
        pending_team = db.has_pending_membership(current_user.id)
        if pending_team:
            return redirect(url_for('pending_approval'))
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        user_dict = db.verify_password(username, password)
        if user_dict:
            user = User.from_dict(user_dict)
            login_user(user, remember=remember)
            
            # Check if user has pending membership
            pending_team = db.has_pending_membership(user.id)
            if pending_team:
                return redirect(url_for('pending_approval'))
            
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
                flash('Membership request submitted! Waiting for admin approval.', 'success')
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

@app.route('/pending')
@login_required
def pending_approval():
    """Pending approval page for users waiting for team acceptance"""
    pending_team = db.has_pending_membership(current_user.id)
    
    # If no pending membership, check for approved team
    if not pending_team:
        team = get_current_team()
        if team:
            return redirect(url_for('index'))
        # If no team at all, redirect to register to join/create a team
        flash('You are not part of any team. Please create or join a team.', 'info')
        return redirect(url_for('register'))
    
    return render_template('pending.html', team=pending_team)

@app.route('/')
@login_required
def index():
    """Home page"""
    redirect_response = check_pending_redirect()
    if redirect_response:
        return redirect_response
    
    team = get_current_team()
    return render_template('index.html', team=team)

@app.route('/create')
@login_required
def create():
    """Test creation page"""
    redirect_response = check_pending_redirect()
    if redirect_response:
        return redirect_response
    
    team = get_current_team()
    if not team:
        flash('You must be part of a team to create tests', 'error')
        return redirect(url_for('index'))
    return render_template('create_test.html', team=team)

@app.route('/tests')
@login_required
def view_tests():
    """View all tests"""
    redirect_response = check_pending_redirect()
    if redirect_response:
        return redirect_response
    
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
    redirect_response = check_pending_redirect()
    if redirect_response:
        return redirect_response
    
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
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You must be part of a team'}), 403
    
    data = request.json
    
    name = data.get('name')
    description = data.get('description', '')
    steps = data.get('steps', [])
    browser = data.get('browser', 'firefox')
    
    if not name or not steps:
        return jsonify({'error': 'Name and steps are required'}), 400
    
    # Generate Selenium script
    script = generate_selenium_script(steps, browser)
    
    # Save to database
    test_id = db.create_test(name, description, steps, script, team['id'], browser)
    
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
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
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
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
    team = get_current_team()
    db.delete_test(test_id, team_id=team['id'] if team else None)
    return jsonify({'success': True, 'message': 'Test deleted successfully'})

@app.route('/test/<int:test_id>')
@login_required
def test_detail(test_id):
    """Test detail and execution page"""
    redirect_response = check_pending_redirect()
    if redirect_response:
        return redirect_response
    
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
    redirect_response = check_pending_redirect()
    if redirect_response:
        return redirect_response
    
    team = get_current_team()
    test = db.get_test(test_id, team_id=team['id'] if team else None)
    
    if not test:
        return "Test not found", 404
    
    return render_template('edit_test.html', test=test, team=team)

@app.route('/api/tests/<int:test_id>', methods=['PUT'])
@login_required
def update_test(test_id):
    """API endpoint to update an existing test"""
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You must be part of a team'}), 403
    
    data = request.json
    
    name = data.get('name')
    description = data.get('description', '')
    steps = data.get('steps', [])
    browser = data.get('browser', 'firefox')
    
    if not name or not steps:
        return jsonify({'error': 'Name and steps are required'}), 400
    
    # Generate Selenium script
    script = generate_selenium_script(steps, browser)
    
    # Update in database
    db.update_test(test_id, name, description, steps, script, team['id'], browser)
    
    return jsonify({
        'success': True,
        'test_id': test_id,
        'message': f'Test "{name}" updated successfully'
    })

@app.route('/team')
@login_required
def team_management():
    """Team management page"""
    redirect_response = check_pending_redirect()
    if redirect_response:
        return redirect_response
    
    team = get_current_team()
    if not team:
        flash('You are not part of a team', 'error')
        return redirect(url_for('index'))
    
    # Get team members
    members = db.get_team_members(team['id'])
    
    # Check if current user is admin
    is_admin = db.is_team_admin(current_user.id, team['id'])
    
    # Get pending requests if admin
    pending_requests = []
    if is_admin:
        pending_requests = db.get_pending_requests(team['id'])
    
    return render_template('team.html', 
                         team=team, 
                         members=members,
                         pending_requests=pending_requests,
                         is_admin=is_admin)

@app.route('/api/team/approve/<int:user_id>', methods=['POST'])
@login_required
def approve_member(user_id):
    """API endpoint to approve a pending member"""
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You are not part of a team'}), 403
    
    # Check if current user is admin
    if not db.is_team_admin(current_user.id, team['id']):
        return jsonify({'error': 'Only admins can approve members'}), 403
    
    success = db.approve_member(user_id, team['id'])
    
    if success:
        return jsonify({'success': True, 'message': 'Member approved successfully'})
    else:
        return jsonify({'error': 'Failed to approve member'}), 400

@app.route('/api/team/reject/<int:user_id>', methods=['POST'])
@login_required
def reject_member(user_id):
    """API endpoint to reject a pending member"""
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You are not part of a team'}), 403
    
    # Check if current user is admin
    if not db.is_team_admin(current_user.id, team['id']):
        return jsonify({'error': 'Only admins can reject members'}), 403
    
    success = db.reject_member(user_id, team['id'])
    
    if success:
        return jsonify({'success': True, 'message': 'Member rejected successfully'})
    else:
        return jsonify({'error': 'Failed to reject member'}), 400

@app.route('/api/team/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
def toggle_admin(user_id):
    """API endpoint to toggle admin status of a team member"""
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You are not part of a team'}), 403
    
    # Check if current user is admin
    if not db.is_team_admin(current_user.id, team['id']):
        return jsonify({'error': 'Only admins can modify admin status'}), 403
    
    # Prevent user from removing their own admin status
    if user_id == current_user.id:
        return jsonify({'error': 'You cannot modify your own admin status'}), 400
    
    success = db.toggle_admin(user_id, team['id'])
    
    if success:
        return jsonify({'success': True, 'message': 'Admin status updated successfully'})
    else:
        return jsonify({'error': 'Failed to update admin status'}), 400

@app.route('/api/team/update-name', methods=['POST'])
@login_required
def update_team_name():
    """API endpoint to update team name"""
    # Check for pending membership
    if db.has_pending_membership(current_user.id):
        return jsonify({'error': 'Your team membership is pending approval'}), 403
    
    team = get_current_team()
    if not team:
        return jsonify({'error': 'You are not part of a team'}), 403
    
    # Check if current user is admin
    if not db.is_team_admin(current_user.id, team['id']):
        return jsonify({'error': 'Only admins can update team name'}), 403
    
    data = request.json
    new_name = data.get('new_name', '').strip()
    
    if not new_name:
        return jsonify({'error': 'Team name cannot be empty'}), 400
    
    success = db.update_team_name(team['id'], new_name)
    
    if success:
        return jsonify({'success': True, 'message': 'Team name updated successfully'})
    else:
        return jsonify({'error': 'Team name already exists or failed to update'}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
