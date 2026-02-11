import sqlite3
import json
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Database:
    def __init__(self, db_name='tests.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Teams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                registration_code TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        
        # User-Team relationship
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_teams (
                user_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT 0,
                status TEXT DEFAULT 'approved',
                PRIMARY KEY (user_id, team_id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                steps TEXT NOT NULL,
                script BLOB NOT NULL,
                browser TEXT DEFAULT 'firefox',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_executed TIMESTAMP,
                execution_count INTEGER DEFAULT 0,
                team_id INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                output TEXT,
                error TEXT,
                step_results TEXT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                team_id INTEGER,
                FOREIGN KEY (test_id) REFERENCES tests (id)
            )
        ''')
        
        # Migrations
        try:
            cursor.execute("SELECT step_results FROM executions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE executions ADD COLUMN step_results TEXT")
        
        try:
            cursor.execute("SELECT team_id FROM tests LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE tests ADD COLUMN team_id INTEGER")
        
        try:
            cursor.execute("SELECT team_id FROM executions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE executions ADD COLUMN team_id INTEGER")
        
        try:
            cursor.execute("SELECT browser FROM tests LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE tests ADD COLUMN browser TEXT DEFAULT 'firefox'")
        
        # Add is_admin and status columns to user_teams
        try:
            cursor.execute("SELECT is_admin FROM user_teams LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE user_teams ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        
        try:
            cursor.execute("SELECT status FROM user_teams LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE user_teams ADD COLUMN status TEXT DEFAULT 'approved'")
        
        conn.commit()
        conn.close()
    
    # Authentication methods
    def create_user(self, username, email, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        password_hash = generate_password_hash(password)
        
        try:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            ''', (username, email, password_hash))
            
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    def get_user_by_username(self, username):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def verify_password(self, username, password):
        user = self.get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            return user
        return None
    
    def create_team(self, name, created_by):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Generate unique registration code
        registration_code = secrets.token_urlsafe(12)
        
        try:
            cursor.execute('''
                INSERT INTO teams (name, registration_code, created_by)
                VALUES (?, ?, ?)
            ''', (name, registration_code, created_by))
            
            team_id = cursor.lastrowid
            
            # Add creator to team as admin with approved status
            cursor.execute('''
                INSERT INTO user_teams (user_id, team_id, is_admin, status)
                VALUES (?, ?, 1, 'approved')
            ''', (created_by, team_id))
            
            conn.commit()
            conn.close()
            return team_id, registration_code
        except sqlite3.IntegrityError:
            conn.close()
            return None, None
    
    def join_team(self, user_id, registration_code):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Find team by registration code
        cursor.execute('SELECT id FROM teams WHERE registration_code = ?', (registration_code,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False
        
        team_id = row['id']
        
        try:
            # Create pending membership request
            cursor.execute('''
                INSERT INTO user_teams (user_id, team_id, is_admin, status)
                VALUES (?, ?, 0, 'pending')
            ''', (user_id, team_id))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def get_user_team(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(''', ut.is_admin, ut.status
            FROM teams t
            JOIN user_teams ut ON t.id = ut.team_id
            WHERE ut.user_id = ? AND ut.status = 'approved'N t.id = ut.team_id
            WHERE ut.user_id = ?
            LIMIT 1
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_team_members(self, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.email, ut.joined_at, ut.is_admin, ut.status
            FROM users u
            JOIN user_teams ut ON u.id = ut.user_id
            WHERE ut.team_id = ? AND ut.status = 'approved'
            ORDER BY ut.joined_at
        ''', (team_id,))
        
        members = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return members
    
    # Team management methods
    def get_pending_requests(self, team_id):
        """Get all pending membership requests for a team"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.email, ut.joined_at
            FROM users u
            JOIN user_teams ut ON u.id = ut.user_id
            WHERE ut.team_id = ? AND ut.status = 'pending'
            ORDER BY ut.joined_at DESC
        ''', (team_id,))
        
        requests = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return requests
    
    def approve_member(self, user_id, team_id):
        """Approve a pending membership request"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE user_teams
            SET status = 'approved'
            WHERE user_id = ? AND team_id = ? AND status = 'pending'
        ''', (user_id, team_id))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0
    
    def reject_member(self, user_id, team_id):
        """Reject a pending membership request"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE user_teams
            SET status = 'rejected'
            WHERE user_id = ? AND team_id = ? AND status = 'pending'
        ''', (user_id, team_id))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0
    
    def toggle_admin(self, user_id, team_id):
        """Toggle admin status for a team member"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE user_teams
            SET is_admin = NOT is_admin
            WHERE user_id = ? AND team_id = ? AND status = 'approved'
        ''', (user_id, team_id))
        
        conn.commit()
        conn.close()
        
        return cursor.rowcount > 0
    
    def update_team_name(self, team_id, new_name):
        """Update team name"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE teams
                SET name = ?
                WHERE id = ?
            ''', (new_name, team_id))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def is_team_admin(self, user_id, team_id):
        """Check if user is an admin of the team"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT is_admin
            FROM user_teams
            WHERE user_id = ? AND team_id = ? AND status = 'approved'
        ''', (user_id, team_id))
        
        row = cursor.fetchone()
        conn.close()
        
        return row and row['is_admin'] == 1
    
    # Updated test methods with team filtering
    def create_test(self, name, description, steps, script, team_id, browser='firefox'):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tests (name, description, steps, script, team_id, browser)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, json.dumps(steps), script.encode('utf-8'), team_id, browser))
        
        test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return test_id
    
    def get_all_tests(self, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if team_id:
            cursor.execute('''
                SELECT id, name, description, browser, created_at, last_executed, execution_count
                FROM tests
                WHERE team_id = ?
                ORDER BY created_at DESC
            ''', (team_id,))
        else:
            cursor.execute('''
                SELECT id, name, description, browser, created_at, last_executed, execution_count
                FROM tests
                ORDER BY created_at DESC
            ''')
        
        tests = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return tests
    
    def get_test(self, test_id, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if team_id:
            cursor.execute('''
                SELECT id, name, description, steps, script, browser, created_at, last_executed, execution_count
                FROM tests
                WHERE id = ? AND team_id = ?
            ''', (test_id, team_id))
        else:
            cursor.execute('''
                SELECT id, name, description, steps, script, browser, created_at, last_executed, execution_count
                FROM tests
                WHERE id = ?
            ''', (test_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            test = dict(row)
            test['steps'] = json.loads(test['steps'])
            test['script'] = test['script'].decode('utf-8')
            return test
        
        return None
    
    def update_execution_stats(self, test_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE tests
            SET last_executed = CURRENT_TIMESTAMP,
                execution_count = execution_count + 1
            WHERE id = ?
        ''', (test_id,))
        
        conn.commit()
        conn.close()
    
    def log_execution(self, test_id, status, output='', error='', step_results='', team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO executions (test_id, status, output, error, step_results, team_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (test_id, status, output, error, step_results, team_id))
        
        conn.commit()
        conn.close()
    
    def get_test_executions(self, test_id, limit=10, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if team_id:
            cursor.execute('''
                SELECT id, status, output, error, step_results, executed_at
                FROM executions
                WHERE test_id = ? AND team_id = ?
                ORDER BY executed_at DESC
                LIMIT ?
            ''', (test_id, team_id, limit))
        else:
            cursor.execute('''
                SELECT id, status, output, error, step_results, executed_at
                FROM executions
                WHERE test_id = ?
                ORDER BY executed_at DESC
                LIMIT ?
            ''', (test_id, limit))
        
        executions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return executions
    
    def get_all_executions(self, limit=50, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if team_id:
            cursor.execute('''
                SELECT e.id, e.test_id, e.status, e.output, e.error, e.step_results, e.executed_at,
                       t.name as test_name
                FROM executions e
                JOIN tests t ON e.test_id = t.id
                WHERE e.team_id = ?
                ORDER BY e.executed_at DESC
                LIMIT ?
            ''', (team_id, limit))
        else:
            cursor.execute('''
                SELECT e.id, e.test_id, e.status, e.output, e.error, e.step_results, e.executed_at,
                       t.name as test_name
                FROM executions e
                JOIN tests t ON e.test_id = t.id
                ORDER BY e.executed_at DESC
                LIMIT ?
            ''', (limit,))
        
        executions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return executions
    
    def update_test(self, test_id, name, description, steps, script, team_id=None, browser='firefox'):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if team_id:
            cursor.execute('''
                UPDATE tests
                SET name = ?, description = ?, steps = ?, script = ?, browser = ?
                WHERE id = ? AND team_id = ?
            ''', (name, description, json.dumps(steps), script.encode('utf-8'), browser, test_id, team_id))
        else:
            cursor.execute('''
                UPDATE tests
                SET name = ?, description = ?, steps = ?, script = ?, browser = ?
                WHERE id = ?
            ''', (name, description, json.dumps(steps), script.encode('utf-8'), browser, test_id))
        
        conn.commit()
        conn.close()
    
    def delete_test(self, test_id, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if team_id:
            cursor.execute('DELETE FROM executions WHERE test_id = ? AND team_id = ?', (test_id, team_id))
            cursor.execute('DELETE FROM tests WHERE id = ? AND team_id = ?', (test_id, team_id))
        else:
            cursor.execute('DELETE FROM executions WHERE test_id = ?', (test_id,))
            cursor.execute('DELETE FROM tests WHERE id = ?', (test_id,))
        
        conn.commit()
        conn.close()
