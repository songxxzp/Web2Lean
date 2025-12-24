"""
Real API test for MathSECrawler
Tests against actual StackExchange API
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.math_se_crawler import MathSECrawler
from backend.database import DatabaseManager


def test_real_api():
    """Test with real StackExchange API"""
    print("=" * 60)
    print("Testing MathSECrawler with Real API")
    print("=" * 60)

    # Use file-based database for verification
    db_path = '/tmp/test_math_se.db'
    if os.path.exists(db_path):
        os.remove(db_path)

    db = DatabaseManager(db_path)

    site_config = {
        'site_type': 'math_se',
        'base_url': 'https://math.stackexchange.com',
        'api_base': 'https://api.stackexchange.com/2.3',
        'enabled': True,
        'pages_per_run': 1,  # Only fetch 1 page for testing
        'request_delay': 0,
        'max_retries': 3,
        'timeout': 30
    }

    crawler = MathSECrawler(
        site_name='math_stackexchange',
        site_id=1,
        config=site_config,
        db_manager=db
    )

    print(f"\n✓ Crawler initialized")
    print(f"  API Base: {crawler.api_base}")
    print(f"  Pages to crawl: {crawler.pages_per_run}")

    # Test 1: Fetch questions
    print("\n" + "-" * 60)
    print("Test 1: Fetching questions from API...")
    print("-" * 60)

    try:
        questions = crawler.fetch_questions_page(1)
        print(f"✓ Successfully fetched {len(questions)} questions")

        if questions:
            q = questions[0]
            print(f"  First question ID: {q['question_id']}")
            print(f"  Title: {q['title'][:60]}...")
            answers = q.get('answers', [])
            has_answers = 'Yes' if answers else 'No'
            print(f"  Has answers: {has_answers}")
        else:
            print("  ✗ No questions returned!")
            return False

    except Exception as e:
        print(f"✗ Failed to fetch questions: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Parse question
    print("\n" + "-" * 60)
    print("Test 2: Parsing question...")
    print("-" * 60)

    try:
        parsed = crawler.parse_question(questions[0])
        print(f"✓ Successfully parsed question")
        print(f"  Title: {parsed['title'][:60]}...")
        print(f"  Score: {parsed['score']}")
        print(f"  Body (stripped): {parsed['body'][:60]}...")

    except Exception as e:
        print(f"✗ Failed to parse question: {e}")
        return False

    # Test 3: Full crawl (1 page)
    print("\n" + "-" * 60)
    print("Test 3: Running full crawl (1 page)...")
    print("-" * 60)

    try:
        run_id = crawler.start(mode='incremental')
        print(f"✓ Crawl completed")
        print(f"  Run ID: {run_id}")
        print(f"  Questions crawled: {crawler.state.questions_crawled}")
        print(f"  Answers crawled: {crawler.state.answers_crawled}")

        # Verify database
        questions_in_db = db.list_questions(limit=100)
        print(f"  Questions in database: {len(questions_in_db)}")

        if questions_in_db:
            q = questions_in_db[0]
            print(f"  First DB question: {q['title'][:60]}...")

        if crawler.state.questions_crawled > 0:
            print("\n" + "=" * 60)
            print("✓ ALL TESTS PASSED")
            print("=" * 60)
            return True
        else:
            print("\n✗ No questions were crawled!")
            return False

    except Exception as e:
        print(f"✗ Crawl failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_real_api()
    sys.exit(0 if success else 1)
