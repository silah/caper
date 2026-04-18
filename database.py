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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS team_variables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                is_secret INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, key),
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, category, name),
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_tags (
                test_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (test_id, tag_id),
                FOREIGN KEY (test_id) REFERENCES tests (id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                stop_on_failure INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suite_tests (
                suite_id INTEGER NOT NULL,
                test_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (suite_id, test_id),
                FOREIGN KEY (suite_id) REFERENCES suites (id) ON DELETE CASCADE,
                FOREIGN KEY (test_id) REFERENCES tests (id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suite_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suite_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                duration_seconds REAL,
                FOREIGN KEY (suite_id) REFERENCES suites (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suite_execution_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suite_execution_id INTEGER NOT NULL,
                test_id INTEGER,
                test_name TEXT,
                execution_id INTEGER,
                position INTEGER NOT NULL DEFAULT 0,
                status TEXT,
                FOREIGN KEY (suite_execution_id) REFERENCES suite_executions (id) ON DELETE CASCADE,
                FOREIGN KEY (execution_id) REFERENCES executions (id)
            )
        ''')

        # Migrations
        migrations = [
            ("SELECT step_results FROM executions LIMIT 1",
             "ALTER TABLE executions ADD COLUMN step_results TEXT"),
            ("SELECT team_id FROM tests LIMIT 1",
             "ALTER TABLE tests ADD COLUMN team_id INTEGER"),
            ("SELECT team_id FROM executions LIMIT 1",
             "ALTER TABLE executions ADD COLUMN team_id INTEGER"),
            ("SELECT artefact_dir FROM executions LIMIT 1",
             "ALTER TABLE executions ADD COLUMN artefact_dir TEXT"),
            ("SELECT schedule_interval FROM tests LIMIT 1",
             None),  # multi-column, handled below
            ("SELECT webhook_url FROM tests LIMIT 1",
             None),  # multi-column, handled below
            ("SELECT retry_count FROM tests LIMIT 1",
             "ALTER TABLE tests ADD COLUMN retry_count INTEGER DEFAULT 0"),
            ("SELECT sla_seconds FROM tests LIMIT 1",
             "ALTER TABLE tests ADD COLUMN sla_seconds INTEGER DEFAULT NULL"),
            ("SELECT duration_seconds FROM executions LIMIT 1",
             None),  # multi-column, handled below
        ]

        for check_sql, alter_sql in migrations:
            try:
                cursor.execute(check_sql)
            except sqlite3.OperationalError:
                if alter_sql:
                    cursor.execute(alter_sql)
                elif 'schedule_interval' in check_sql:
                    for col_sql in [
                        "ALTER TABLE tests ADD COLUMN schedule_interval INTEGER DEFAULT NULL",
                        "ALTER TABLE tests ADD COLUMN schedule_enabled INTEGER DEFAULT 0",
                        "ALTER TABLE tests ADD COLUMN schedule_next_run TIMESTAMP DEFAULT NULL",
                    ]:
                        try:
                            cursor.execute(col_sql)
                        except sqlite3.OperationalError:
                            pass
                elif 'webhook_url' in check_sql:
                    for col_sql in [
                        "ALTER TABLE tests ADD COLUMN webhook_enabled INTEGER DEFAULT 0",
                        "ALTER TABLE tests ADD COLUMN webhook_url TEXT DEFAULT NULL",
                        "ALTER TABLE tests ADD COLUMN webhook_method TEXT DEFAULT 'POST'",
                        "ALTER TABLE tests ADD COLUMN webhook_payload_success TEXT DEFAULT NULL",
                        "ALTER TABLE tests ADD COLUMN webhook_payload_failure TEXT DEFAULT NULL",
                    ]:
                        try:
                            cursor.execute(col_sql)
                        except sqlite3.OperationalError:
                            pass
                elif 'duration_seconds' in check_sql:
                    try:
                        cursor.execute("ALTER TABLE executions ADD COLUMN duration_seconds REAL DEFAULT NULL")
                    except sqlite3.OperationalError:
                        pass
                    try:
                        cursor.execute("ALTER TABLE executions ADD COLUMN sla_violated INTEGER DEFAULT 0")
                    except sqlite3.OperationalError:
                        pass

        conn.commit()
        conn.close()

    def create_user(self, username, email, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        try:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)
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
        registration_code = secrets.token_urlsafe(12)
        try:
            cursor.execute('''
                INSERT INTO teams (name, registration_code, created_by) VALUES (?, ?, ?)
            ''', (name, registration_code, created_by))
            team_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO user_teams (user_id, team_id) VALUES (?, ?)
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
        cursor.execute('SELECT id FROM teams WHERE registration_code = ?', (registration_code,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        team_id = row['id']
        try:
            cursor.execute('INSERT INTO user_teams (user_id, team_id) VALUES (?, ?)', (user_id, team_id))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_all_teams(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM teams ORDER BY name')
        teams = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return teams

    def join_team_by_id(self, user_id, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO user_teams (user_id, team_id) VALUES (?, ?)', (user_id, team_id))
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

    # Team variables
    def get_team_variables(self, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, key, value, is_secret, created_at
            FROM team_variables WHERE team_id = ? ORDER BY key
        ''', (team_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def set_team_variable(self, team_id, key, value, is_secret=False):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO team_variables (team_id, key, value, is_secret)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(team_id, key) DO UPDATE SET value=excluded.value, is_secret=excluded.is_secret
        ''', (team_id, key, value, 1 if is_secret else 0))
        conn.commit()
        conn.close()

    def delete_team_variable(self, team_id, key):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM team_variables WHERE team_id = ? AND key = ?', (team_id, key))
        conn.commit()
        conn.close()

    def create_test(self, name, description, steps, script, team_id, retry_count=0, sla_seconds=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tests (name, description, steps, script, team_id, retry_count, sla_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, json.dumps(steps), script.encode('utf-8'), team_id,
              retry_count or 0, sla_seconds))
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
                       schedule_interval, schedule_enabled, schedule_next_run,
                       retry_count, sla_seconds
                FROM tests WHERE team_id = ? ORDER BY created_at DESC
            ''', (team_id,))
        else:
            cursor.execute('''
                SELECT id, name, description, created_at, last_executed, execution_count,
                       schedule_interval, schedule_enabled, schedule_next_run,
                       retry_count, sla_seconds
                FROM tests ORDER BY created_at DESC
            ''')
        tests = [dict(row) for row in cursor.fetchall()]

        for test in tests:
            cursor.execute('''
                SELECT status FROM executions
                WHERE test_id = ? AND status != 'running'
                ORDER BY executed_at DESC LIMIT 10
            ''', (test['id'],))
            statuses = [r[0] for r in cursor.fetchall()]
            terminal = [s for s in statuses if s in ('success', 'error', 'timeout')]
            test['flaky'] = (
                len(terminal) >= 3 and
                any(s == 'success' for s in terminal) and
                any(s in ('error', 'timeout') for s in terminal)
            )
            cursor.execute('''
                SELECT t.id, t.name, t.category FROM tags t
                JOIN test_tags tt ON tt.tag_id = t.id
                WHERE tt.test_id = ? ORDER BY t.category, t.name
            ''', (test['id'],))
            test['tags'] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return tests

    def get_test(self, test_id, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if team_id:
            cursor.execute('''
                SELECT id, name, description, steps, script, created_at, last_executed, execution_count,
                       schedule_interval, schedule_enabled, schedule_next_run,
                       webhook_enabled, webhook_url, webhook_method,
                       webhook_payload_success, webhook_payload_failure,
                       retry_count, sla_seconds
                FROM tests WHERE id = ? AND team_id = ?
            ''', (test_id, team_id))
        else:
            cursor.execute('''
                SELECT id, name, description, steps, script, created_at, last_executed, execution_count,
                       schedule_interval, schedule_enabled, schedule_next_run,
                       webhook_enabled, webhook_url, webhook_method,
                       webhook_payload_success, webhook_payload_failure,
                       retry_count, sla_seconds
                FROM tests WHERE id = ?
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
            UPDATE tests SET last_executed = CURRENT_TIMESTAMP,
                execution_count = execution_count + 1
            WHERE id = ?
        ''', (test_id,))
        conn.commit()
        conn.close()

    def create_execution(self, test_id, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO executions (test_id, status, team_id) VALUES (?, 'running', ?)
        ''', (test_id, team_id))
        execution_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return execution_id

    def update_execution(self, execution_id, status, output='', error='', step_results='',
                         artefact_dir='', duration_seconds=None, sla_violated=0):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE executions
            SET status = ?, output = ?, error = ?, step_results = ?, artefact_dir = ?,
                duration_seconds = ?, sla_violated = ?
            WHERE id = ?
        ''', (status, output, error, step_results, artefact_dir,
              duration_seconds, sla_violated, execution_id))
        conn.commit()
        conn.close()

    def get_execution(self, execution_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, test_id, status, output, error, step_results, executed_at,
                   team_id, artefact_dir, duration_seconds, sla_violated
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
                SELECT id, status, output, error, step_results, executed_at, artefact_dir,
                       duration_seconds, sla_violated
                FROM executions WHERE test_id = ? AND team_id = ?
                ORDER BY executed_at DESC LIMIT ?
            ''', (test_id, team_id, limit))
        else:
            cursor.execute('''
                SELECT id, status, output, error, step_results, executed_at, artefact_dir,
                       duration_seconds, sla_violated
                FROM executions WHERE test_id = ?
                ORDER BY executed_at DESC LIMIT ?
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
                       e.artefact_dir, e.duration_seconds, e.sla_violated, t.name as test_name
                FROM executions e JOIN tests t ON e.test_id = t.id
                WHERE e.team_id = ? ORDER BY e.executed_at DESC LIMIT ?
            ''', (team_id, limit))
        else:
            cursor.execute('''
                SELECT e.id, e.test_id, e.status, e.output, e.error, e.step_results, e.executed_at,
                       e.artefact_dir, e.duration_seconds, e.sla_violated, t.name as test_name
                FROM executions e JOIN tests t ON e.test_id = t.id
                ORDER BY e.executed_at DESC LIMIT ?
            ''', (limit,))
        executions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return executions

    def log_event(self, level, message, details=None):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO logs (level, message, details) VALUES (?, ?, ?)',
                (level, message, details)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_logs(self, hours=5, page=1, per_page=100):
        conn = self.get_connection()
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        cursor.execute('''
            SELECT id, level, message, details, created_at FROM logs
            WHERE created_at >= datetime('now', ? || ' hours')
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        ''', (str(-hours), per_page, offset))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def get_log_count(self, hours=5):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM logs WHERE created_at >= datetime('now', ? || ' hours')
        ''', (str(-hours),))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def set_test_schedule(self, test_id, interval_minutes, enabled):
        conn = self.get_connection()
        cursor = conn.cursor()
        if enabled and interval_minutes:
            cursor.execute('''
                UPDATE tests SET schedule_interval = ?, schedule_enabled = 1,
                    schedule_next_run = datetime('now')
                WHERE id = ?
            ''', (interval_minutes, test_id))
        else:
            cursor.execute('''
                UPDATE tests SET schedule_interval = ?, schedule_enabled = 0,
                    schedule_next_run = NULL WHERE id = ?
            ''', (interval_minutes, test_id))
        conn.commit()
        conn.close()

    def set_test_webhook(self, test_id, enabled, url, method, payload_success, payload_failure):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tests SET webhook_enabled = ?, webhook_url = ?, webhook_method = ?,
                webhook_payload_success = ?, webhook_payload_failure = ?
            WHERE id = ?
        ''', (1 if enabled else 0, url, method, payload_success, payload_failure, test_id))
        conn.commit()
        conn.close()

    def advance_next_run(self, test_id, interval_minutes):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tests SET schedule_next_run = datetime('now', ? || ' minutes') WHERE id = ?
        ''', (str(interval_minutes), test_id))
        conn.commit()
        conn.close()

    def get_due_scheduled_tests(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, script, team_id, schedule_interval, retry_count, sla_seconds
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
                    SELECT id, status, executed_at, artefact_dir, step_results, error, output,
                           duration_seconds, sla_violated
                    FROM executions WHERE test_id = ? AND team_id = ?
                    ORDER BY executed_at DESC LIMIT ?
                ''', (test['id'], team_id, limit_per_test))
            else:
                cursor.execute('''
                    SELECT id, status, executed_at, artefact_dir, step_results, error, output,
                           duration_seconds, sla_violated
                    FROM executions WHERE test_id = ?
                    ORDER BY executed_at DESC LIMIT ?
                ''', (test['id'], limit_per_test))
            test['executions'] = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return tests

    def update_test(self, test_id, name, description, steps, script, team_id=None,
                    retry_count=0, sla_seconds=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if team_id:
            cursor.execute('''
                UPDATE tests SET name = ?, description = ?, steps = ?, script = ?,
                    retry_count = ?, sla_seconds = ?
                WHERE id = ? AND team_id = ?
            ''', (name, description, json.dumps(steps), script.encode('utf-8'),
                  retry_count or 0, sla_seconds, test_id, team_id))
        else:
            cursor.execute('''
                UPDATE tests SET name = ?, description = ?, steps = ?, script = ?,
                    retry_count = ?, sla_seconds = ?
                WHERE id = ?
            ''', (name, description, json.dumps(steps), script.encode('utf-8'),
                  retry_count or 0, sla_seconds, test_id))
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

    def get_health_dashboard(self, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if team_id:
            cursor.execute('''
                SELECT t.id, t.name, t.schedule_enabled, t.schedule_interval,
                       t.schedule_next_run, t.sla_seconds, t.execution_count,
                       e.status as last_status, e.executed_at as last_run,
                       e.duration_seconds, e.sla_violated
                FROM tests t
                LEFT JOIN executions e ON e.id = (
                    SELECT id FROM executions
                    WHERE test_id = t.id ORDER BY executed_at DESC LIMIT 1
                )
                WHERE t.team_id = ?
                ORDER BY t.name
            ''', (team_id,))
        else:
            cursor.execute('''
                SELECT t.id, t.name, t.schedule_enabled, t.schedule_interval,
                       t.schedule_next_run, t.sla_seconds, t.execution_count,
                       e.status as last_status, e.executed_at as last_run,
                       e.duration_seconds, e.sla_violated
                FROM tests t
                LEFT JOIN executions e ON e.id = (
                    SELECT id FROM executions
                    WHERE test_id = t.id ORDER BY executed_at DESC LIMIT 1
                )
                ORDER BY t.name
            ''')
        tests = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tests

    def get_tags(self, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM tags WHERE team_id = ? ORDER BY category, name',
            (team_id,)
        )
        tags = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tags

    def create_tag(self, team_id, name, category):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO tags (team_id, name, category) VALUES (?, ?, ?)',
                (team_id, name, category)
            )
            tag_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return tag_id
        except sqlite3.IntegrityError:
            conn.close()
            return None

    def delete_tag(self, tag_id, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM test_tags WHERE tag_id = ?', (tag_id,))
        cursor.execute('DELETE FROM tags WHERE id = ? AND team_id = ?', (tag_id, team_id))
        conn.commit()
        conn.close()

    def get_test_tags(self, test_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.id, t.name, t.category FROM tags t
            JOIN test_tags tt ON tt.tag_id = t.id
            WHERE tt.test_id = ? ORDER BY t.category, t.name
        ''', (test_id,))
        tags = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tags

    def set_test_tags(self, test_id, tag_ids):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM test_tags WHERE test_id = ?', (test_id,))
        for tag_id in tag_ids:
            try:
                cursor.execute(
                    'INSERT INTO test_tags (test_id, tag_id) VALUES (?, ?)',
                    (test_id, int(tag_id))
                )
            except (sqlite3.IntegrityError, ValueError):
                pass
        conn.commit()
        conn.close()

    # ── Suites ────────────────────────────────────────────────────────────────

    def create_suite(self, team_id, name, description='', stop_on_failure=0):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO suites (team_id, name, description, stop_on_failure) VALUES (?, ?, ?, ?)',
            (team_id, name, description or '', int(stop_on_failure))
        )
        suite_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return suite_id

    def get_suites(self, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.*,
                COUNT(DISTINCT st.test_id) as test_count,
                (SELECT status FROM suite_executions WHERE suite_id = s.id
                 ORDER BY started_at DESC LIMIT 1) as last_status,
                (SELECT started_at FROM suite_executions WHERE suite_id = s.id
                 ORDER BY started_at DESC LIMIT 1) as last_run
            FROM suites s
            LEFT JOIN suite_tests st ON st.suite_id = s.id
            WHERE s.team_id = ?
            GROUP BY s.id
            ORDER BY s.name
        ''', (team_id,))
        suites = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return suites

    def get_suite(self, suite_id, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if team_id:
            cursor.execute('SELECT * FROM suites WHERE id = ? AND team_id = ?', (suite_id, team_id))
        else:
            cursor.execute('SELECT * FROM suites WHERE id = ?', (suite_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        suite = dict(row)
        cursor.execute('''
            SELECT t.id, t.name, t.description, t.script, t.retry_count, t.sla_seconds,
                   st.position
            FROM suite_tests st
            JOIN tests t ON t.id = st.test_id
            WHERE st.suite_id = ?
            ORDER BY st.position
        ''', (suite_id,))
        suite['tests'] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return suite

    def update_suite(self, suite_id, name, description, stop_on_failure, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if team_id:
            cursor.execute(
                'UPDATE suites SET name=?, description=?, stop_on_failure=? WHERE id=? AND team_id=?',
                (name, description or '', int(stop_on_failure), suite_id, team_id)
            )
        else:
            cursor.execute(
                'UPDATE suites SET name=?, description=?, stop_on_failure=? WHERE id=?',
                (name, description or '', int(stop_on_failure), suite_id)
            )
        conn.commit()
        conn.close()

    def set_suite_tests(self, suite_id, test_ids):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM suite_tests WHERE suite_id = ?', (suite_id,))
        for position, test_id in enumerate(test_ids):
            try:
                cursor.execute(
                    'INSERT INTO suite_tests (suite_id, test_id, position) VALUES (?, ?, ?)',
                    (suite_id, int(test_id), position)
                )
            except (sqlite3.IntegrityError, ValueError):
                pass
        conn.commit()
        conn.close()

    def delete_suite(self, suite_id, team_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if team_id:
            cursor.execute('DELETE FROM suites WHERE id = ? AND team_id = ?', (suite_id, team_id))
        else:
            cursor.execute('DELETE FROM suites WHERE id = ?', (suite_id,))
        conn.commit()
        conn.close()

    def create_suite_execution(self, suite_id, team_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO suite_executions (suite_id, team_id, status) VALUES (?, ?, ?)',
            (suite_id, team_id, 'running')
        )
        suite_execution_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return suite_execution_id

    def update_suite_execution(self, suite_execution_id, status, duration_seconds):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE suite_executions
               SET status=?, finished_at=CURRENT_TIMESTAMP, duration_seconds=?
               WHERE id=?''',
            (status, duration_seconds, suite_execution_id)
        )
        conn.commit()
        conn.close()

    def add_suite_execution_test(self, suite_execution_id, test_id, test_name,
                                  execution_id, position, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO suite_execution_tests
               (suite_execution_id, test_id, test_name, execution_id, position, status)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (suite_execution_id, test_id, test_name, execution_id, position, status)
        )
        conn.commit()
        conn.close()

    def update_suite_execution_test(self, suite_execution_id, test_id, status):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''UPDATE suite_execution_tests SET status=?
               WHERE suite_execution_id=? AND test_id=?''',
            (status, suite_execution_id, test_id)
        )
        conn.commit()
        conn.close()

    def get_suite_executions(self, suite_id, limit=15):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM suite_executions WHERE suite_id = ? ORDER BY started_at DESC LIMIT ?',
            (suite_id, limit)
        )
        executions = [dict(row) for row in cursor.fetchall()]
        for ex in executions:
            cursor.execute(
                'SELECT * FROM suite_execution_tests WHERE suite_execution_id = ? ORDER BY position',
                (ex['id'],)
            )
            ex['tests'] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return executions

    def get_suite_execution(self, suite_execution_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT se.*, s.name as suite_name, s.id as suite_id_ref
            FROM suite_executions se
            LEFT JOIN suites s ON s.id = se.suite_id
            WHERE se.id = ?
        ''', (suite_execution_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        ex = dict(row)
        cursor.execute('''
            SELECT set.*, e.error, e.step_results, e.output,
                   e.duration_seconds as exec_duration, e.artefact_dir, e.sla_violated
            FROM suite_execution_tests set
            LEFT JOIN executions e ON e.id = set.execution_id
            WHERE set.suite_execution_id = ?
            ORDER BY set.position
        ''', (suite_execution_id,))
        ex['tests'] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return ex

    def get_all_suite_executions(self, team_id, limit=50):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT se.*, s.name as suite_name,
                COUNT(set.id) as test_count,
                SUM(CASE WHEN set.status = 'success' THEN 1 ELSE 0 END) as pass_count
            FROM suite_executions se
            JOIN suites s ON s.id = se.suite_id
            LEFT JOIN suite_execution_tests set ON set.suite_execution_id = se.id
            WHERE se.team_id = ?
            GROUP BY se.id
            ORDER BY se.started_at DESC
            LIMIT ?
        ''', (team_id, limit))
        executions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return executions
