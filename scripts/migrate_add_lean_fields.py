#!/usr/bin/env python3
"""
Database migration script to add new fields to processing_status table.
Adds: preprocessing_error, question_lean_code, answer_lean_code
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import DatabaseManager
import sqlite3


def migrate_database(db_path: str = '/datadisk/Web2Lean/data/databases/web2lean.db'):
    """
    Add new columns to processing_status table.

    Args:
        db_path: Path to SQLite database
    """
    print(f"Migrating database: {db_path}")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(processing_status)")
        columns = [row[1] for row in cursor.fetchall()]

        columns_to_add = {
            'preprocessing_error': 'TEXT',
            'question_lean_code': 'TEXT',
            'answer_lean_code': 'TEXT'
        }

        for column, col_type in columns_to_add.items():
            if column not in columns:
                print(f"Adding column: {column}")
                cursor.execute(f"ALTER TABLE processing_status ADD COLUMN {column} {col_type}")
            else:
                print(f"Column {column} already exists, skipping")

        # Commit changes
        conn.commit()
        print("\n✓ Migration completed successfully!")

        # Verify
        cursor.execute("PRAGMA table_info(processing_status)")
        new_columns = [row[1] for row in cursor.fetchall()]
        print(f"\nCurrent columns in processing_status: {', '.join(new_columns)}")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migrate database to add new processing fields')
    parser.add_argument('--db-path', default='/datadisk/Web2Lean/data/databases/web2lean.db',
                       help='Path to database')

    args = parser.parse_args()

    migrate_database(args.db_path)
