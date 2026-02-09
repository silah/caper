#!/usr/bin/env python3
"""
Migration script to assign existing tests and executions to a team.
Run this after creating your first team to assign all orphaned data.
"""

from database import Database
import sys

def migrate_orphaned_data():
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Check for orphaned tests
    cursor.execute('SELECT COUNT(*) as count FROM tests WHERE team_id IS NULL')
    orphaned_tests = cursor.fetchone()['count']
    
    # Check for orphaned executions
    cursor.execute('SELECT COUNT(*) as count FROM executions WHERE team_id IS NULL')
    orphaned_executions = cursor.fetchone()['count']
    
    if orphaned_tests == 0 and orphaned_executions == 0:
        print("✓ No orphaned data found. All tests and executions are assigned to teams.")
        conn.close()
        return
    
    print(f"Found {orphaned_tests} tests and {orphaned_executions} executions without a team.")
    
    # Get the first team (or let user choose)
    cursor.execute('SELECT id, name FROM teams ORDER BY created_at ASC')
    teams = cursor.fetchall()
    
    if not teams:
        print("\n⚠ No teams exist yet!")
        print("Please register a user and create a team first, then run this migration again.")
        conn.close()
        return
    
    print("\nAvailable teams:")
    for i, team in enumerate(teams, 1):
        print(f"{i}. {team['name']} (ID: {team['id']})")
    
    if len(teams) == 1:
        print(f"\nAutomatically selecting the only team: {teams[0]['name']}")
        selected_team_id = teams[0]['id']
    else:
        try:
            choice = input(f"\nSelect team number (1-{len(teams)}) or press Enter for team 1: ").strip()
            if not choice:
                choice = 1
            else:
                choice = int(choice)
            
            if choice < 1 or choice > len(teams):
                print("Invalid selection. Exiting.")
                conn.close()
                return
            
            selected_team_id = teams[choice - 1]['id']
        except (ValueError, KeyboardInterrupt):
            print("\nMigration cancelled.")
            conn.close()
            return
    
    # Perform migration
    print(f"\nMigrating data to team ID {selected_team_id}...")
    
    cursor.execute('UPDATE tests SET team_id = ? WHERE team_id IS NULL', (selected_team_id,))
    updated_tests = cursor.rowcount
    
    cursor.execute('UPDATE executions SET team_id = ? WHERE team_id IS NULL', (selected_team_id,))
    updated_executions = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✓ Migration complete!")
    print(f"  - Updated {updated_tests} tests")
    print(f"  - Updated {updated_executions} executions")

if __name__ == '__main__':
    print("=" * 60)
    print("Data Migration Script")
    print("=" * 60)
    migrate_orphaned_data()
