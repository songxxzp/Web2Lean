#!/usr/bin/env python3
"""
Migration script to add separate verification fields for question and answer.

Adds the following columns to lean_conversion_results table:
- question_verification_status
- question_verification_messages
- question_verification_time
- answer_verification_status
- answer_verification_messages
- answer_verification_time
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database import DatabaseManager


def migrate():
    """Add separate verification fields for question and answer."""
    db = DatabaseManager()
    session = db.get_session()

    try:
        # Check if migration already ran
        from sqlalchemy import text
        result = session.execute(text("PRAGMA table_info(lean_conversion_results)"))
        columns = [row[1] for row in result.fetchall()]

        if 'question_verification_status' in columns:
            print("Migration already applied - question_verification_status column exists")
            return

        print("Adding separate verification fields...")

        # Add question verification columns
        session.execute(text("""
            ALTER TABLE lean_conversion_results
            ADD COLUMN question_verification_status TEXT
        """))

        session.execute(text("""
            ALTER TABLE lean_conversion_results
            ADD COLUMN question_verification_messages TEXT
        """))

        session.execute(text("""
            ALTER TABLE lean_conversion_results
            ADD COLUMN question_verification_time REAL
        """))

        # Add answer verification columns
        session.execute(text("""
            ALTER TABLE lean_conversion_results
            ADD COLUMN answer_verification_status TEXT
        """))

        session.execute(text("""
            ALTER TABLE lean_conversion_results
            ADD COLUMN answer_verification_messages TEXT
        """))

        session.execute(text("""
            ALTER TABLE lean_conversion_results
            ADD COLUMN answer_verification_time REAL
        """))

        session.commit()
        print("✓ Migration completed successfully")
        print("  Added 6 new columns for separate question/answer verification")

    except Exception as e:
        session.rollback()
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == '__main__':
    migrate()
