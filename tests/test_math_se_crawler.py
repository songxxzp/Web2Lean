"""
Unit tests for MathSECrawler
"""
import sys
import os
import unittest
import json
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.math_se_crawler import MathSECrawler
from backend.database import DatabaseManager


class TestMathSECrawler(unittest.TestCase):
    """Test cases for MathSECrawler"""

    def setUp(self):
        """Set up test fixtures"""
        # Use in-memory database
        self.db = DatabaseManager(':memory:')

        # Sample site configuration
        self.site_config = {
            'site_type': 'math_se',
            'base_url': 'https://math.stackexchange.com',
            'api_base': 'https://api.stackexchange.com/2.3',
            'enabled': True,
            'pages_per_run': 2,
            'request_delay': 0.1,
            'max_retries': 3,
            'timeout': 30
        }

        # Create crawler instance
        self.crawler = MathSECrawler(
            site_name='math_stackexchange',
            site_id=1,
            config=self.site_config,
            db_manager=self.db
        )

    def test_crawler_initialization(self):
        """Test crawler is initialized correctly"""
        self.assertEqual(self.crawler.site_name, 'math_stackexchange')
        self.assertEqual(self.crawler.site_id, 1)
        self.assertEqual(self.crawler.api_base, 'https://api.stackexchange.com/2.3')
        self.assertEqual(self.crawler.base_url, 'https://math.stackexchange.com')
        self.assertEqual(self.crawler.pages_per_run, 2)
        self.assertEqual(self.crawler.request_delay, 0.1)
        self.assertTrue(self.crawler.enabled)

    def test_api_url_construction(self):
        """Test API URL is constructed correctly"""
        # The URL should be properly formed
        expected_url = 'https://api.stackexchange.com/2.3/questions'
        # We can't directly access the URL, but we can verify api_base is set
        self.assertEqual(self.crawler.api_base, 'https://api.stackexchange.com/2.3')

    @patch('backend.core.math_se_crawler.requests.Session.get')
    def test_fetch_questions_page(self, mock_get):
        """Test fetching questions page from API"""
        # Mock API response
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            'items': [
                {
                    'question_id': 1,
                    'title': 'Test Question',
                    'body': '<p>Test body</p>',
                    'tags': ['algebra', 'linear-algebra'],
                    'score': 5,
                    'view_count': 100,
                    'answer_count': 2,
                    'creation_date': 1234567890,
                    'last_activity_date': 1234567890,
                    'owner': {
                        'user_id': 1,
                        'display_name': 'Test User',
                        'reputation': 1000
                    },
                    'link': 'https://math.stackexchange.com/questions/1',
                    'is_answered': True,
                    'accepted_answer_id': 1,
                    'answers': [
                        {
                            'answer_id': 1,
                            'body': '<p>Test answer</p>',
                            'score': 5,
                            'creation_date': 1234567890,
                            'last_activity_date': 1234567890,
                            'owner': {
                                'user_id': 2,
                                'display_name': 'Answer User',
                                'reputation': 500
                            },
                            'is_accepted': True
                        }
                    ]
                }
            ],
            'has_more': True
        }
        mock_get.return_value = mock_response

        # Fetch page
        questions = self.crawler.fetch_questions_page(1)

        # Verify
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]['question_id'], 1)
        self.assertEqual(questions[0]['title'], 'Test Question')

        # Verify request was made with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]['params']['page'], 1)
        self.assertEqual(call_args[1]['params']['site'], 'math')

    def test_parse_question(self):
        """Test parsing raw question data"""
        raw_data = {
            'question_id': 123,
            'title': 'What is 2+2?',
            'body': '<p>I need to know what 2+2 equals.</p>',
            'tags': ['arithmetic', 'basic-math'],
            'score': 10,
            'view_count': 500,
            'answer_count': 3,
            'creation_date': 1234567890,
            'last_activity_date': 1234567890,
            'owner': {
                'user_id': 42,
                'display_name': 'MathUser',
                'reputation': 2500
            },
            'link': 'https://math.stackexchange.com/questions/123',
            'is_answered': True,
            'accepted_answer_id': 456,
            'answers': []
        }

        parsed = self.crawler.parse_question(raw_data)

        # Verify parsed data
        self.assertEqual(parsed['question_id'], 123)
        self.assertEqual(parsed['title'], 'What is 2+2?')
        self.assertIn('I need to know', parsed['body'])
        self.assertEqual(parsed['score'], 10)
        self.assertEqual(parsed['answer_count'], 3)
        self.assertTrue(parsed['is_answered'])
        self.assertEqual(parsed['accepted_answer_id'], 456)

    def test_strip_html(self):
        """Test HTML stripping"""
        html = '<p>This is <strong>bold</strong> text.</p>'
        text = self.crawler._strip_html(html)
        self.assertIn('bold', text)
        self.assertNotIn('<p>', text)
        self.assertNotIn('<strong>', text)

    @patch('backend.core.math_se_crawler.requests.Session.get')
    def test_api_error_handling(self, mock_get):
        """Test API error handling"""
        # Mock error response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("Network error")
        mock_get.return_value = mock_response

        # Should raise exception
        with self.assertRaises(Exception) as context:
            self.crawler.fetch_questions_page(1)

        # Error should be raised (exact message may vary)
        self.assertTrue(context.exception is not None)

    def test_get_status(self):
        """Test getting crawler status"""
        status = self.crawler.get_status()

        self.assertEqual(status['site_name'], 'math_stackexchange')
        self.assertEqual(status['site_id'], 1)
        self.assertEqual(status['status'], 'idle')


class TestMathSECrawlerIntegration(unittest.TestCase):
    """Integration tests for MathSECrawler with real API (limited scope)"""

    def setUp(self):
        """Set up test fixtures"""
        self.db = DatabaseManager(':memory:')

        self.site_config = {
            'site_type': 'math_se',
            'base_url': 'https://math.stackexchange.com',
            'api_base': 'https://api.stackexchange.com/2.3',
            'enabled': True,
            'pages_per_run': 1,  # Only fetch 1 page for testing
            'request_delay': 0,
            'max_retries': 2,
            'timeout': 30
        }

        self.crawler = MathSECrawler(
            site_name='math_stackexchange',
            site_id=1,
            config=self.site_config,
            db_manager=self.db
        )

    @unittest.skip("Requires network - run manually to verify API access")
    def test_real_api_fetch(self):
        """Test fetching from real StackExchange API"""
        try:
            questions = self.crawler.fetch_questions_page(1)

            # Verify we got some questions
            self.assertGreater(len(questions), 0)

            # Verify structure
            q = questions[0]
            self.assertIn('question_id', q)
            self.assertIn('title', q)
            self.assertIn('body', q)

            print(f"✓ Successfully fetched {len(questions)} questions from real API")
            print(f"  First question: {q['title'][:50]}...")

        except Exception as e:
            self.fail(f"Real API test failed: {e}")

    @unittest.skip("Requires network - run manually to verify full crawl")
    def test_real_crawl_one_page(self):
        """Test crawling one page from real API"""
        try:
            run_id = self.crawler.start(mode='incremental')

            # Check results
            self.assertGreater(self.crawler.state.questions_crawled, 0)

            # Verify data in database
            questions = self.db.list_questions(limit=10)
            self.assertGreater(len(questions), 0)

            print(f"✓ Crawled {self.crawler.state.questions_crawled} questions")
            print(f"  Run ID: {run_id}")
            print(f"  First question: {questions[0]['title'][:50]}...")

        except Exception as e:
            self.fail(f"Real crawl test failed: {e}")


def run_tests():
    """Run all tests"""
    # Run unit tests
    print("=" * 60)
    print("Running MathSECrawler Unit Tests")
    print("=" * 60)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestMathSECrawler)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"Unit Tests: {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 60)

    # Ask about integration tests
    print("\n" + "=" * 60)
    print("Integration Tests (require network access)")
    print("Run manually with: python tests/test_math_se_crawler.py --integration")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == '__main__':
    import sys

    if '--integration' in sys.argv:
        # Run integration tests
        suite = unittest.TestLoader().loadTestsFromTestCase(TestMathSECrawlerIntegration)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        # Run unit tests
        success = run_tests()
        sys.exit(0 if success else 1)
