import sqlite3
import json
import os
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Database:
    def __init__(self, db_name=None):
        if db_name is None:
            db_name = os.environ.get('DB_PATH', 'tests.db')
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
            cursor.execute("SELECT artefact_dir FROM executions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE executions ADD COLUMN artefact_dir TEXT")

        try:
            cursor.execute("SELECT schedule_interval FROM tests LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE tests ADD COLUMN schedule_interval INTEGER DEFAULT NULL")
            cursor.execute("ALTER TABLE tests ADD COLUMN schedule_enabled INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE tests ADD COLUMN schedule_next_run TIMESTAMP DEFAULT NULL")

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
            
            # Add creator to team
            cursor.execute('''
                INSERT INTO user_teams (user_id, team_id)
                VALUES (?, ?)
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
            cursor.execute('''
                INSERT INTO user_teams (user_id, team_id)
                VALUES (?, ?)
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
        
        cursor.execute('''
            SELECT t.id, t.name, t.registration_code, t.created_at
            FROM teams t
            JOIN user_teams ut ON t.id = ut.team_id
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
            SELECT u.id, u.username, u.email, ut.joined_at
            FROM users u
            JOIN user_teams ut ON u.id = ut.user_id
            WHERE ut.team_id = ?
            ORDER BY ut.joined_at
        ''', (team_id,))
        
        members = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return members
    
    # Updated test methods with team filtering
    def create_test(self, name, description, steps, script, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tests (name, description, steps, script, team_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, json.dumps(steps), script.encode('utf-8'), team_id))
        
        test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return test_id
    
    def get_all_tests(self, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()

        if team_id:
            cursor.execute('''
                SELECT id, name, description, created_at, last_executed, execution_count,
                       schedule_interval, schedule_enabled, schedule_next_run
                FROM tests
                WHERE team_id = ?
                ORDER BY created_at DESC
            ''', (team_id,))
        else:
            cursor.execute('''
                SELECT id, name, description, created_at, last_executed, execution_count,
                       schedule_interval, schedule_enabled, schedule_next_run
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
                SELECT id, name, description, steps, script, created_at, last_executed, execution_count,
                       schedule_interval, schedule_enabled, schedule_next_run
                FROM tests
                WHERE id = ? AND team_id = ?
            ''', (test_id, team_id))
        else:
            cursor.execute('''
                SELECT id, name, description, steps, script, created_at, last_executed, execution_count,
                       schedule_interval, schedule_enabled, schedule_next_run
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
    
    def create_execution(self, test_id, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO executions (test_id, status, team_id)
            VALUES (?, 'running', ?)
        ''', (test_id, team_id))
        execution_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return execution_id

    def update_execution(self, execution_id, status, output='', error='', step_results='', artefact_dir=''):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE executions
            SET status = ?, output = ?, error = ?, step_results = ?, artefact_dir = ?
            WHERE id = ?
        ''', (status, output, error, step_results, artefact_dir, execution_id))
        conn.commit()
        conn.close()

    def get_execution(self, execution_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, test_id, status, output, error, step_results, executed_at, team_id, artefact_dir
            FROM executions WHERE id = ?
        ''', (execution_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

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
                SELECT id, status, output, error, step_results, executed_at, artefact_dir
                FROM executions
                WHERE test_id = ? AND team_id = ?
                ORDER BY executed_at DESC
                LIMIT ?
            ''', (test_id, team_id, limit))
        else:
            cursor.execute('''
                SELECT id, status, output, error, step_results, executed_at, artefact_dir
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
                       e.artefact_dir, t.name as test_name
                FROM executions e
                JOIN tests t ON e.test_id = t.id
                WHERE e.team_id = ?
                ORDER BY e.executed_at DESC
                LIMIT ?
            ''', (team_id, limit))
        else:
            cursor.execute('''
                SELECT e.id, e.test_id, e.status, e.output, e.error, e.step_results, e.executed_at,
                       e.artefact_dir, t.name as test_name
                FROM executions e
                JOIN tests t ON e.test_id = t.id
                ORDER BY e.executed_at DESC
                LIMIT ?
            ''', (limit,))
        
        executions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return executions
    
    def set_test_schedule(self, test_id, interval_minutes, enabled):
        conn = self.get_connection()
        cursor = conn.cursor()
        if enabled and interval_minutes:
            cursor.execute('''
                UPDATE tests
                SET schedule_interval = ?, schedule_enabled = 1,
                    schedule_next_run = datetime('now', ? || ' minutes')
                WHERE id = ?
            ''', (interval_minutes, str(interval_minutes), test_id))
        else:
            cursor.execute('''
                UPDATE tests
                SET schedule_interval = ?, schedule_enabled = 0, schedule_next_run = NULL
                WHERE id = ?
            ''', (interval_minutes, test_id))
        conn.commit()
        conn.close()

    def advance_next_run(self, test_id, interval_minutes):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tests
            SET schedule_next_run = datetime('now', ? || ' minutes')
            WHERE id = ?
        ''', (str(interval_minutes), test_id))
        conn.commit()
        conn.close()

    def get_due_scheduled_tests(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, script, team_id, schedule_interval
            FROM tests
            WHERE schedule_enabled = 1
              AND schedule_interval IS NOT NULL
              AND (schedule_next_run IS NULL OR schedule_next_run <= datetime('now'))
        ''')
        tests = [dict(row) for row in cursor.fetchall()]
        conn.close()
        for t in tests:
            if isinstance(t.get('script'), bytes):
                t['script'] = t['script'].decode('utf-8')
        return tests

    def get_executions_grouped_by_test(self, team_id=None, limit_per_test=100):
        conn = self.get_connection()
        cursor = conn.cursor()

        if team_id:
            cursor.execute('SELECT id, name FROM tests WHERE team_id = ? ORDER BY name', (team_id,))
        else:
            cursor.execute('SELECT id, name FROM tests ORDER BY name')
        tests = [dict(row) for row in cursor.fetchall()]

        for test in tests:
            if team_id:
                cursor.execute('''
                    SELECT id, status, executed_at, artefact_dir, step_results, error, output
                    FROM executions
                    WHERE test_id = ? AND team_id = ?
                    ORDER BY executed_at DESC
                    LIMIT ?
                ''', (test['id'], team_id, limit_per_test))
            else:
                cursor.execute('''
                    SELECT id, status, executed_at, artefact_dir, step_results, error, output
                    FROM executions
                    WHERE test_id = ?
                    ORDER BY executed_at DESC
                    LIMIT ?
                ''', (test['id'], limit_per_test))
            test['executions'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return tests

    def update_test(self, test_id, name, description, steps, script, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if team_id:
            cursor.execute('''
                UPDATE tests
                SET name = ?, description = ?, steps = ?, script = ?
                WHERE id = ? AND team_id = ?
            ''', (name, description, json.dumps(steps), script.encode('utf-8'), test_id, team_id))
        else:
            cursor.execute('''
                UPDATE tests
                SET name = ?, description = ?, steps = ?, script = ?
                WHERE id = ?
            ''', (name, description, json.dumps(steps), script.encode('utf-8'), test_id))
        
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
