#!/usr/bin/env python3
"""
Script to regenerate all test scripts
"""
import sqlite3
import json
import os
import sys

from test_generator import generate_playwright_script

DB_PATH = os.environ.get('DB_PATH', 'tests.db')
BASE_ARTEFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'artefacts')

def regenerate_all_scripts():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT id, name, steps FROM tests')
    tests = cursor.fetchall()

    print(f"Found {len(tests)} tests to regenerate...")

    for test in tests:
        test_id = test['id']
        name = test['name']
        steps = json.loads(test['steps'])

        print(f"  Regenerating '{name}' (ID: {test_id})...")

        new_script = generate_playwright_script(steps, test_name=name, base_artefacts_dir=BASE_ARTEFACTS_DIR)

        cursor.execute(
            'UPDATE tests SET script = ? WHERE id = ?',
            (new_script.encode('utf-8'), test_id)
        )

    conn.commit()
    conn.close()

    print(f"Done. Regenerated {len(tests)} test scripts.")

if __name__ == '__main__':
    regenerate_all_scripts()
