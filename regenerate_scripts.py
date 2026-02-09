#!/usr/bin/env python3
"""
Script to regenerate all test scripts with Firefox driver
"""
import sqlite3
import json
import sys
sys.path.insert(0, '/home/silas/caper')

from test_generator import generate_selenium_script

def regenerate_all_scripts():
    conn = sqlite3.connect('/home/silas/caper/tests.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, steps FROM tests')
    tests = cursor.fetchall()
    
    print(f"Found {len(tests)} tests to regenerate...")
    
    for test in tests:
        test_id = test['id']
        name = test['name']
        steps = json.loads(test['steps'])
        
        print(f"\nRegenerating test '{name}' (ID: {test_id})...")
        
        # Generate new script with Firefox
        new_script = generate_selenium_script(steps)
        
        # Update in database
        cursor.execute(
            'UPDATE tests SET script = ? WHERE id = ?',
            (new_script.encode('utf-8'), test_id)
        )
        
        print(f"  ✓ Updated script for '{name}'")
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Successfully regenerated {len(tests)} test scripts with Firefox driver")

if __name__ == '__main__':
    regenerate_all_scripts()
