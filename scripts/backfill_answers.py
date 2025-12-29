#!/usr/bin/env python3
"""
Backfill answers for existing questions that don't have answers in the database.
This script fetches answers from StackExchange API for questions that have answer_count > 0
but no actual Answer records.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from backend.database import DatabaseManager
from backend.core.stackexchange_crawler import StackExchangeCrawler


def backfill_answers(site_name='math_stackexchange', batch_size=10, delay=1.0):
    """
    Backfill answers for existing questions.

    Args:
        site_name: Site configuration name
        batch_size: Number of questions to process before delay
        delay: Delay between batches (seconds)
    """
    db = DatabaseManager()
    site = db.get_site_by_name(site_name)

    if not site:
        print(f"Site {site_name} not found!")
        return

    print(f"Site: {site['site_name']} (ID: {site['site_id']})")
    print(f"API Base: {site['api_base']}")

    # Create crawler instance to use fetch_answers method
    import json
    config = json.loads(site['config_json']) if site.get('config_json') else {}
    config['api_base'] = site['api_base']  # Add api_base to config

    crawler = StackExchangeCrawler(
        site_id=site['site_id'],
        site_name=site['site_name'],
        api_base=site['api_base'],
        config=config,
        db_manager=db
    )

    # Override answer filter to ensure body is included
    crawler.answer_filter = '!*S4CeCUIRL)Y'  # Filter that includes answer body

    # Get all internal question IDs
    session = db.get_session()
    try:
        from backend.database.schema import Question, Answer

        # Find questions with answer_count > 0 but no answers in database
        query = session.query(Question).filter(
            Question.site_id == site['site_id'],
            Question.answer_count > 0
        )

        total_questions = query.count()
        print(f"\nFound {total_questions} questions with answer_count > 0")

        processed = 0
        backfilled = 0
        errors = 0

        for question in query.all():
            # Check if answers already exist
            existing_count = session.query(Answer).filter(
                Answer.question_id == question.id
            ).count()

            if existing_count > 0:
                # Answers already exist, skip
                continue

            # Fetch answers from API
            print(f"\n[{processed+1}/{total_questions}] Fetching answers for question {question.question_id}...")
            try:
                raw_answers = crawler.fetch_answers(question.question_id)

                if not raw_answers:
                    print(f"  No answers returned from API (count: {question.answer_count})")
                    processed += 1
                    continue

                # Save answers
                for ans in raw_answers:
                    from backend.database.schema import Answer as AnswerModel
                    from sqlalchemy import inspect

                    owner = ans.get('owner', {})
                    answer_data = {
                        'answer_id': ans.get('answer_id'),
                        'question_id': question.id,  # Internal ID
                        'site_id': site['site_id'],
                        'body': crawler._strip_html(ans.get('body', '')),
                        'body_html': ans.get('body_markdown') or ans.get('body', ''),
                        'score': ans.get('score', 0),
                        'creation_date': ans.get('creation_date'),
                        'last_activity_date': ans.get('last_activity_date'),
                        'owner': json.dumps({
                            'user_id': owner.get('user_id'),
                            'display_name': owner.get('display_name'),
                            'reputation': owner.get('reputation')
                        }),
                        'is_accepted': ans.get('is_accepted', False)
                    }

                    # Check for duplicates
                    existing = session.query(AnswerModel).filter(
                        AnswerModel.answer_id == answer_data['answer_id'],
                        AnswerModel.site_id == site['site_id']
                    ).first()

                    if not existing:
                        answer = AnswerModel(**answer_data)
                        session.add(answer)
                        backfilled += 1

                session.commit()
                print(f"  ✓ Saved {len(raw_answers)} answers")

                # Delay to avoid rate limiting
                if (processed + 1) % batch_size == 0:
                    print(f"\n  Batch complete, sleeping {delay}s...")
                    time.sleep(delay)

            except Exception as e:
                session.rollback()
                print(f"  ✗ Error: {e}")
                errors += 1

            processed += 1

        print(f"\n{'='*60}")
        print(f"Backfill complete!")
        print(f"  Processed: {processed}")
        print(f"  Backfilled: {backfilled} answers")
        print(f"  Errors: {errors}")

    finally:
        session.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Backfill answers for existing questions')
    parser.add_argument('--site', default='math_stackexchange', help='Site name')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between batches (seconds)')

    args = parser.parse_args()

    backfill_answers(
        site_name=args.site,
        batch_size=args.batch_size,
        delay=args.delay
    )
