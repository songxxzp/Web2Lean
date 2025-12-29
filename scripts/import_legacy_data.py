#!/usr/bin/env python3
"""
Import legacy database data to new Web2Lean database.
Imports questions and answers from legacy math_se_questions.db
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import DatabaseManager
from backend.database.schema import Question, Answer, ProcessingStatus, Site
import sqlite3
from datetime import datetime


def import_legacy_data(
    legacy_db_path: str = '/datadisk/Web2Lean/legacy/math_server_data/math_se_questions.db',
    site_name: str = 'math_stackexchange',
    batch_size: int = 100
):
    """
    Import questions and answers from legacy database.

    Args:
        legacy_db_path: Path to legacy SQLite database
        site_name: Site name in new database
        batch_size: Number of questions to process per transaction
    """
    # Connect to new database
    new_db = DatabaseManager()
    site = new_db.get_site_by_name(site_name)

    if not site:
        print(f"Error: Site {site_name} not found in new database!")
        return

    site_id = site['site_id']
    print(f"Target site: {site['site_name']} (ID: {site_id})")

    # Connect to legacy database
    if not os.path.exists(legacy_db_path):
        print(f"Error: Legacy database not found at {legacy_db_path}")
        return

    legacy_conn = sqlite3.connect(legacy_db_path)
    legacy_conn.row_factory = sqlite3.Row
    legacy_cursor = legacy_conn.cursor()

    # Get counts
    legacy_cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = legacy_cursor.fetchone()[0]

    legacy_cursor.execute("SELECT COUNT(*) FROM answers")
    total_answers = legacy_cursor.fetchone()[0]

    print(f"\nLegacy database:")
    print(f"  Questions: {total_questions}")
    print(f"  Answers: {total_answers}")
    print(f"\nStarting import...\n")

    # Check existing data
    session = new_db.get_session()
    try:
        existing_count = session.query(Question).filter(
            Question.site_id == site_id
        ).count()
        print(f"Existing questions in new database: {existing_count}")

        if existing_count > 0:
            response = input(f"\nNew database already has {existing_count} questions. Continue import? (y/n): ")
            if response.lower() != 'y':
                print("Import cancelled.")
                return

        # Import questions and answers
        imported_questions = 0
        imported_answers = 0
        skipped_questions = 0

        # Fetch all questions from legacy
        legacy_cursor.execute("""
            SELECT
                question_id, title, body, tags, score, view_count, answer_count,
                creation_date, last_activity_date, owner, link, is_answered,
                accepted_answer_id, crawled_at
            FROM questions
            ORDER BY question_id
        """)

        legacy_questions = legacy_cursor.fetchall()

        # Map legacy question_id to new internal id
        question_id_map = {}

        for legacy_q in legacy_questions:
            # Check if already exists
            existing = session.query(Question).filter(
                Question.question_id == legacy_q['question_id'],
                Question.site_id == site_id
            ).first()

            if existing:
                print(f"[{imported_questions+skipped_questions+1}/{total_questions}] Skipping question {legacy_q['question_id']} (already exists)")
                question_id_map[legacy_q['question_id']] = existing.id
                skipped_questions += 1
                continue

            # Create new question
            question = Question(
                question_id=legacy_q['question_id'],
                site_id=site_id,
                title=legacy_q['title'],
                body=legacy_q['body'],
                body_html=None,  # Legacy doesn't have this
                tags=legacy_q['tags'],
                score=legacy_q['score'] or 0,
                view_count=legacy_q['view_count'] or 0,
                answer_count=legacy_q['answer_count'] or 0,
                creation_date=legacy_q['creation_date'],
                last_activity_date=legacy_q['last_activity_date'],
                owner=legacy_q['owner'],
                link=legacy_q['link'],
                is_answered=legacy_q['is_answered'] or False,
                accepted_answer_id=legacy_q['accepted_answer_id'],
                crawled_at=legacy_q['crawled_at'] or datetime.now().isoformat()
            )

            session.add(question)
            session.flush()  # Get the new ID
            question_id_map[legacy_q['question_id']] = question.id

            # Create processing status
            processing_status = ProcessingStatus(
                question_id=question.id,
                site_id=site_id,
                status='raw'
            )
            session.add(processing_status)

            imported_questions += 1

            # Commit in batches
            if imported_questions % batch_size == 0:
                session.commit()
                print(f"[{imported_questions+skipped_questions}/{total_questions}] Imported {imported_questions} questions, committed batch")

            # Progress every 10 questions
            elif imported_questions % 10 == 0:
                print(f"[{imported_questions+skipped_questions}/{total_questions}] Importing...")

        # Final commit for questions
        session.commit()
        print(f"\n✓ Imported {imported_questions} questions (skipped {skipped_questions})")

        # Import answers
        print(f"\nImporting answers...")

        legacy_cursor.execute("""
            SELECT
                answer_id, question_id, body, score, creation_date,
                last_activity_date, owner, is_accepted, crawled_at
            FROM answers
            ORDER BY answer_id
        """)

        legacy_answers = legacy_cursor.fetchall()

        for legacy_a in legacy_answers:
            # Get new question internal ID
            new_question_id = question_id_map.get(legacy_a['question_id'])

            if not new_question_id:
                # Answer's question wasn't imported (maybe it was skipped)
                print(f"Warning: Answer {legacy_a['answer_id']} references question {legacy_a['question_id']} which wasn't imported")
                continue

            # Check if answer already exists
            existing = session.query(Answer).filter(
                Answer.answer_id == legacy_a['answer_id'],
                Answer.site_id == site_id
            ).first()

            if existing:
                continue

            # Create new answer
            answer = Answer(
                answer_id=legacy_a['answer_id'],
                question_id=new_question_id,
                site_id=site_id,
                body=legacy_a['body'],
                body_html=None,  # Legacy doesn't have this
                score=legacy_a['score'] or 0,
                creation_date=legacy_a['creation_date'],
                last_activity_date=legacy_a['last_activity_date'],
                owner=legacy_a['owner'],
                is_accepted=legacy_a['is_accepted'] or False,
                crawled_at=legacy_a['crawled_at'] or datetime.now().isoformat()
            )

            session.add(answer)
            imported_answers += 1

            # Commit in batches
            if imported_answers % batch_size == 0:
                session.commit()
                print(f"[{imported_answers}/{total_answers}] Imported {imported_answers} answers, committed batch")

        # Final commit
        session.commit()
        print(f"\n✓ Imported {imported_answers} answers")

        print(f"\n{'='*60}")
        print(f"Import complete!")
        print(f"  Questions imported: {imported_questions}")
        print(f"  Questions skipped:  {skipped_questions}")
        print(f"  Answers imported:   {imported_answers}")
        print(f"{'='*60}")

    except Exception as e:
        session.rollback()
        print(f"\nError during import: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()
        legacy_conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Import legacy database to new Web2Lean database')
    parser.add_argument('--legacy-db', default='/datadisk/Web2Lean/legacy/math_server_data/math_se_questions.db',
                       help='Path to legacy database')
    parser.add_argument('--site', default='math_stackexchange', help='Site name in new database')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for commits')

    args = parser.parse_args()

    import_legacy_data(
        legacy_db_path=args.legacy_db,
        site_name=args.site,
        batch_size=args.batch_size
    )
