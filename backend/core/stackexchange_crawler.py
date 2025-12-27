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

    def __init__(self, *args, api_base: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        # API base URL (either passed as arg or from config)
        self.api_base = api_base or self.config.get('api_base', 'https://api.stackexchange.com/2.3')
        self.api_key = None  # Add API key if available for higher rate limits
        # Get site parameter from config (default to 'math' for backward compatibility)
        self.site_param = self.config.get('site_param', 'math')
        # Use a valid filter that includes body and answers
        # Filter: !9_bDDxJY5 includes body, answers, comments
        self.filter = '!9_bDDxJY5'
        # Starting page for crawling (default: 1)
        self.start_page = self.config.get('start_page', 1)
        # Stop strategy: 'pages' (limit by pages_per_run) or 'questions' (limit by new_questions_count)
        self.stop_strategy = self.config.get('stop_strategy', 'pages')
        # New questions limit (0 = unlimited, only used when stop_strategy='questions')
        self.new_questions_limit = self.config.get('new_questions_limit', 0)

    def fetch_questions_page(self, page: int, since: int = None) -> List[Dict[str, Any]]:
        """
        Fetch a page of questions from StackExchange API.

        Args:
            page: Page number (1-indexed)
            since: Optional Unix timestamp to fetch only questions newer than this

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

        # Add since parameter for incremental crawling
        if since:
            params['since'] = since

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
        Fetch answers for a question from StackExchange API.

        Args:
            question_id: Question ID (external ID from StackExchange)

        Returns:
            List of answer data dicts
        """
        url = f"{self.api_base}/questions/{question_id}/answers"
        params = {
            'order': 'desc',
            'sort': 'votes',
            'site': self.site_param,
            'filter': '!9_bDDxJY5',  # Include body
            'key': self.api_key
        }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if 'error_id' in data:
                print(f"API Error fetching answers for question {question_id}: {data.get('error_message')}")
                return []

            return data.get('items', [])

        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch answers for question {question_id}: {e}")
            return []

    def _process_question(self, raw_data: Dict[str, Any]):
        """
        Process a single question and its answers.

        Args:
            raw_data: Raw question data from API
        """
        question = self.parse_question(raw_data)
        question_id = question.get('question_id')

        # Fetch answers from API (since /questions endpoint doesn't include them)
        raw_answers = self.fetch_answers(question_id)

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

        # Save question (now returns tuple of id, is_new)
        question['site_id'] = self.site_id
        q_id, is_new = self.db.save_question(question)

        # Only count if it's a new question
        if is_new:
            self.state.questions_crawled += 1

        # Save answers (both new and existing questions to ensure answers are populated)
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
                    # Create new answer
                    answer = Answer(**ans_data)
                    session.add(answer)
                    if is_new:
                        self.state.answers_crawled += 1
                # If answer exists, we could update it here if needed
                # For now, we keep existing answers as-is

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
            mode: Crawl mode ('incremental' or 'history')
            **kwargs: Additional parameters
        """
        new_questions_count = 0
        skipped_count = 0

        # Determine stop conditions based on strategy
        if self.stop_strategy == 'questions':
            # Stop when we reach new_questions_limit (or 0 = unlimited)
            if self.new_questions_limit == 0:
                print(f"Stop strategy: Crawl until no more new questions (unlimited)")
                max_pages = 100000  # Effectively unlimited
            else:
                print(f"Stop strategy: Crawl until {self.new_questions_limit} new questions found")
                max_pages = 100000  # Effectively unlimited
        else:
            # Default: stop after pages_per_run pages
            print(f"Stop strategy: Crawl {self.pages_per_run} pages")
            max_pages = self.pages_per_run

        page = self.start_page

        # Process questions
        while page < self.start_page + max_pages:
            if self._stop_event.is_set():
                break

            # Check if we reached the new questions limit
            if self.stop_strategy == 'questions' and self.new_questions_limit > 0:
                if self.state.questions_crawled >= self.new_questions_limit:
                    print(f"Reached new questions limit: {self.new_questions_limit}")
                    break

            self.state.current_page = page
            questions_before = self.state.questions_crawled

            try:
                # Fetch questions
                questions_data = self._fetch_with_retry(
                    lambda: self.fetch_questions_page(page, since=None)
                )

                if not questions_data:
                    print(f"No more questions on page {page}")
                    break

                # Process each question
                page_new_count = 0
                for raw_q in questions_data:
                    if self._stop_event.is_set():
                        break

                    try:
                        qid = raw_q.get('question_id')

                        # Check if question exists (for all modes to avoid duplicates)
                        if self.db.question_exists(qid, self.site_id):
                            skipped_count += 1
                            continue

                        self._process_question(raw_q)
                        page_new_count += 1

                        # Check if we reached the limit mid-page
                        if self.stop_strategy == 'questions' and self.new_questions_limit > 0:
                            if self.state.questions_crawled >= self.new_questions_limit:
                                print(f"Reached new questions limit: {self.new_questions_limit}")
                                break
                    except Exception as e:
                        print(f"Error processing question: {e}")

                page_new_questions = self.state.questions_crawled - questions_before
                progress_info = f"Page {page} completed: {len(questions_data)} fetched, {page_new_questions} new, {len(questions_data) - page_new_questions} skipped"

                if self.stop_strategy == 'questions' and self.new_questions_limit > 0:
                    progress_info += f" (Total new: {self.state.questions_crawled}/{self.new_questions_limit})"

                print(progress_info)

                page += 1

                # Delay between pages
                if page < self.start_page + max_pages:
                    time.sleep(self.request_delay)

            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                if self.max_retries <= 1:
                    break

        print(f"Crawl completed: {self.state.questions_crawled} new questions, {skipped_count} existing questions skipped")


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
