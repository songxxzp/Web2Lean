"""
Generic StackExchange Crawler
Base crawler for all StackExchange-based sites (math, mathoverflow, etc.)
"""
import json
import time
import requests
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from .base_crawler import BaseCrawler, CrawlerStatus


class StackExchangeCrawler(BaseCrawler):
    """
    Generic crawler for StackExchange-based sites.

    Uses the StackExchange API v2.3 for efficient data retrieval.
    Subclasses only need to specify the site parameter.

    Site parameters:
    - math.stackexchange.com -> 'math'
    - mathoverflow.net -> 'mathoverflow'
    - stats.stackexchange.com -> 'stats'
    - etc.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = None  # Add API key if available for higher rate limits
        # Get site parameter from config (default to 'math' for backward compatibility)
        self.site_param = self.config.get('site_param', 'math')
        # Use a valid filter that includes body and answers
        # Filter: !9_bDDxJY5 includes body, answers, comments
        self.filter = '!9_bDDxJY5'

    def fetch_questions_page(self, page: int) -> List[Dict[str, Any]]:
        """
        Fetch a page of questions from StackExchange API.

        Args:
            page: Page number (1-indexed)

        Returns:
            List of raw question data from API
        """
        url = f"{self.api_base}/questions"
        params = {
            'order': 'desc',
            'sort': 'activity',
            'page': page,
            'pagesize': min(self.pages_per_run, 100),
            'filter': self.filter,
            'site': self.site_param
        }

        # Add key if available
        if self.api_key:
            params['key'] = self.api_key

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if 'error_id' in data:
                raise Exception(f"API Error: {data.get('error_message', 'Unknown error')}")

            return data.get('items', [])

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch questions page {page}: {e}")

    def parse_question(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw API question data into standard format.

        Args:
            raw_data: Raw question data from StackExchange API

        Returns:
            Standardized question dict
        """
        # Parse tags
        tags = raw_data.get('tags', [])

        # Parse owner
        owner = raw_data.get('owner', {})
        owner_data = {
            'user_id': owner.get('user_id'),
            'display_name': owner.get('display_name'),
            'reputation': owner.get('reputation')
        }

        # Get answers from API response
        answers = raw_data.get('answers', [])

        return {
            'question_id': raw_data.get('question_id'),
            'title': raw_data.get('title', ''),
            'body': self._strip_html(raw_data.get('body', '')),
            'body_html': raw_data.get('body_markdown') or raw_data.get('body', ''),
            'tags': json.dumps(tags),
            'score': raw_data.get('score', 0),
            'view_count': raw_data.get('view_count', 0),
            'answer_count': raw_data.get('answer_count', 0),
            'creation_date': raw_data.get('creation_date'),
            'last_activity_date': raw_data.get('last_activity_date'),
            'owner': json.dumps(owner_data),
            'link': raw_data.get('link', ''),
            'is_answered': raw_data.get('is_answered', False),
            'accepted_answer_id': raw_data.get('accepted_answer_id'),
            'raw_answers': answers  # Store for later processing
        }

    def fetch_answers(self, question_id: int) -> List[Dict[str, Any]]:
        """
        Fetch answers for a question.

        Note: In StackExchange crawler, answers are included in the question API response
        when using the appropriate filter. This method is kept for compatibility.

        Args:
            question_id: Question ID

        Returns:
            List of answer data dicts
        """
        # Answers are fetched along with questions in parse_question
        # This is a placeholder for potential separate answer fetching
        return []

    def _process_question(self, raw_data: Dict[str, Any]):
        """
        Process a single question and its answers.

        Args:
            raw_data: Raw question data from API
        """
        question = self.parse_question(raw_data)
        raw_answers = raw_data.get('answers', [])

        # Extract answers before saving question
        answers_data = []
        for ans in raw_answers:
            owner = ans.get('owner', {})
            answer = {
                'answer_id': ans.get('answer_id'),
                'body': self._strip_html(ans.get('body', '')),
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
            answers_data.append(answer)

        # Remove raw_answers from question dict
        question.pop('raw_answers', None)

        # Save question
        question['site_id'] = self.site_id
        q_id = self.db.save_question(question)
        self.state.questions_crawled += 1

        # Save answers
        session = self.db.get_session()
        try:
            from backend.database.schema import Answer

            for ans_data in answers_data:
                ans_data['question_id'] = q_id
                ans_data['site_id'] = self.site_id

                # Check if answer exists
                existing = session.query(Answer).filter(
                    Answer.answer_id == ans_data['answer_id'],
                    Answer.site_id == self.site_id
                ).first()

                if not existing:
                    answer = Answer(**ans_data)
                    session.add(answer)
                    self.state.answers_crawled += 1

            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error saving answers: {e}")
        finally:
            session.close()

    def _strip_html(self, html_content: str) -> str:
        """
        Strip HTML tags and decode HTML entities.

        Args:
            html_content: HTML string

        Returns:
            Plain text
        """
        if not html_content:
            return ''

        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()

        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)

        return text

    def start(self, mode: str = 'incremental', **kwargs) -> str:
        """
        Start the crawler with enhanced error handling.

        Args:
            mode: Crawl mode ('incremental' or 'history')
            **kwargs: Additional parameters

        Returns:
            Run ID
        """
        if self.state.status == CrawlerStatus.RUNNING:
            raise RuntimeError(f"Crawler for {self.site_name} is already running")

        if not self.enabled:
            raise RuntimeError(f"Crawler for {self.site_name} is disabled")

        # Reset state
        self._stop_event.clear()
        run_id = f"run_{self.site_name}_{time.strftime('%Y%m%d_%H%M%S')}"
        self.state.run_id = run_id
        self.state.status = CrawlerStatus.RUNNING
        self.state.start_time = time.strftime('%Y-%m-%d %H:%M:%S')
        self.state.questions_crawled = 0
        self.state.answers_crawled = 0
        self.state.images_crawled = 0
        self.state.error_message = None
        self.state.current_page = 0

        # Create run record
        self.db.create_crawler_run(self.site_id, run_id, run_mode=mode)

        try:
            # Run the crawl
            self._run_crawl(mode, **kwargs)

            # Update run record
            self.db.update_crawler_run(
                run_id,
                end_time=time.strftime('%Y-%m-%d %H:%M:%S'),
                status='completed',
                questions_crawled=self.state.questions_crawled,
                answers_crawled=self.state.answers_crawled
            )

            self.state.status = CrawlerStatus.COMPLETED

        except Exception as e:
            self.state.error_message = str(e)
            self.state.status = CrawlerStatus.ERROR

            self.db.update_crawler_run(
                run_id,
                end_time=time.strftime('%Y-%m-%d %H:%M:%S'),
                status='failed',
                error_message=str(e)
            )
            raise

        return run_id

    def _run_crawl(self, mode: str, **kwargs):
        """
        Internal method to run the crawl.

        Args:
            mode: Crawl mode
            **kwargs: Additional parameters
        """
        start_page = 1  # StackExchange API uses 1-indexed pages

        # Process questions
        for page in range(start_page, start_page + self.pages_per_run):
            if self._stop_event.is_set():
                break

            self.state.current_page = page

            try:
                # Fetch questions
                questions_data = self._fetch_with_retry(
                    lambda: self.fetch_questions_page(page)
                )

                if not questions_data:
                    print(f"No more questions on page {page}")
                    break

                # Process each question
                for raw_q in questions_data:
                    if self._stop_event.is_set():
                        break

                    try:
                        self._process_question(raw_q)
                    except Exception as e:
                        print(f"Error processing question: {e}")

                print(f"Page {page} completed: {len(questions_data)} questions")

                # Delay between pages
                if page < start_page + self.pages_per_run - 1:
                    time.sleep(self.request_delay)

            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                if self.max_retries <= 1:
                    break


# Convenience wrappers for specific sites
class MathSECrawler(StackExchangeCrawler):
    """Crawler for Math StackExchange (math.stackexchange.com)"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_param = 'math'


class MathOverflowCrawler(StackExchangeCrawler):
    """Crawler for MathOverflow (mathoverflow.net)"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_param = 'mathoverflow'
