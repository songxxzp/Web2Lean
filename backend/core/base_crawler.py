"""
Abstract base crawler for mathematical Q&A sites.
"""
import abc
import time
import signal
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import threading

from ..database import DatabaseManager


class CrawlerStatus(Enum):
    """Crawler status enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class CrawlerState:
    """Crawler state data."""
    status: CrawlerStatus = CrawlerStatus.IDLE
    questions_crawled: int = 0
    answers_crawled: int = 0
    images_crawled: int = 0
    current_page: int = 0
    error_message: Optional[str] = None
    start_time: Optional[str] = None
    run_id: Optional[str] = None


class BaseCrawler(abc.ABC):
    """
    Abstract base class for all crawlers.

    Subclasses must implement the abstract methods for site-specific crawling logic.
    """

    def __init__(
        self,
        site_name: str,
        site_id: int,
        config: Dict[str, Any],
        db_manager: DatabaseManager
    ):
        """
        Initialize crawler.

        Args:
            site_name: Name of the site (e.g., 'math_stackexchange')
            site_id: Database site ID
            config: Site configuration dict
            db_manager: Database manager instance
        """
        self.site_name = site_name
        self.site_id = site_id
        self.config = config
        self.db = db_manager

        # State
        self.state = CrawlerState()
        self._stop_event = threading.Event()
        self._session: Optional[requests.Session] = None

        # Config defaults
        self.base_url = config.get('base_url', '')
        self.api_base = config.get('api_base', '')
        self.request_delay = config.get('request_delay', 8.0)
        self.max_retries = config.get('max_retries', 3)
        self.timeout = config.get('timeout', 30)
        self.pages_per_run = config.get('pages_per_run', 10)
        self.enabled = config.get('enabled', True)

    @property
    def session(self) -> requests.Session:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
        return self._session

    @abc.abstractmethod
    def fetch_questions_page(self, page: int) -> List[Dict[str, Any]]:
        """
        Fetch a page of questions from the site.

        Args:
            page: Page number to fetch

        Returns:
            List of question data dicts
        """
        pass

    @abc.abstractmethod
    def parse_question(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw question data into standard format.

        Args:
            raw_data: Raw question data from API/HTML

        Returns:
            Standardized question dict with keys:
            - question_id: int
            - title: str
            - body: str (plain text)
            - body_html: str (original HTML)
            - tags: List[str]
            - score: int
            - answer_count: int
            - creation_date: str
            - link: str
            - is_answered: bool
            - accepted_answer_id: Optional[int]
        """
        pass

    @abc.abstractmethod
    def fetch_answers(self, question_id: int) -> List[Dict[str, Any]]:
        """
        Fetch answers for a question.

        Args:
            question_id: Question ID

        Returns:
            List of answer data dicts with keys:
            - answer_id: int
            - body: str
            - body_html: str
            - score: int
            - is_accepted: bool
            - creation_date: str
        """
        pass

    def start(self, mode: str = 'incremental', **kwargs) -> str:
        """
        Start the crawler.

        Args:
            mode: Crawl mode ('incremental' or 'history')
            **kwargs: Additional crawler-specific parameters

        Returns:
            Run ID
        """
        if self.state.status == CrawlerStatus.RUNNING:
            raise RuntimeError(f"Crawler for {self.site_name} is already running")

        if not self.enabled:
            raise RuntimeError(f"Crawler for {self.site_name} is disabled")

        # Reset state
        self._stop_event.clear()
        run_id = f"run_{self.site_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.state.run_id = run_id
        self.state.status = CrawlerStatus.RUNNING
        self.state.start_time = datetime.now().isoformat()
        self.state.questions_crawled = 0
        self.state.answers_crawled = 0
        self.state.images_crawled = 0
        self.state.error_message = None

        # Create run record
        self.db.create_crawler_run(self.site_id, run_id, run_mode=mode)

        try:
            # Run the crawl
            self._run_crawl(mode, **kwargs)

            # Update run record
            self.db.update_crawler_run(
                run_id,
                end_time=datetime.now().isoformat(),
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
                end_time=datetime.now().isoformat(),
                status='failed',
                error_message=str(e)
            )
            raise

        return run_id

    def stop(self):
        """Stop the crawler gracefully."""
        if self.state.status == CrawlerStatus.RUNNING:
            self._stop_event.set()
            self.state.status = CrawlerStatus.STOPPED

            if self.state.run_id:
                self.db.update_crawler_run(
                    self.state.run_id,
                    end_time=datetime.now().isoformat(),
                    status='stopped'
                )

    def _run_crawl(self, mode: str, **kwargs):
        """
        Internal method to run the crawl.

        Args:
            mode: Crawl mode
            **kwargs: Additional parameters
        """
        start_page = self._get_start_page(mode)

        for page in range(start_page, start_page + self.pages_per_run):
            if self._stop_event.is_set():
                break

            self.state.current_page = page

            # Fetch questions with retry
            questions_data = self._fetch_with_retry(
                lambda: self.fetch_questions_page(page)
            )

            if not questions_data:
                break

            # Process each question
            for raw_q in questions_data:
                if self._stop_event.is_set():
                    break

                self._process_question(raw_q)

            # Delay between pages
            if page < start_page + self.pages_per_run - 1:
                time.sleep(self.request_delay)

    def _get_start_page(self, mode: str) -> int:
        """Get starting page based on mode."""
        if mode == 'history':
            return 1
        else:
            # Get last page from state or default to 1
            return 1  # TODO: implement incremental state tracking

    def _process_question(self, raw_data: Dict[str, Any]):
        """Process a single question."""
        question = self.parse_question(raw_data)

        # Check if already exists
        existing = self.db.get_session().query(self.db.__class__).filter(
            # TODO: implement exists check
        ).first()

        # Save question
        question['site_id'] = self.site_id
        q_id = self.db.save_question(question)
        self.state.questions_crawled += 1

        # Fetch and save answers
        try:
            answers = self.fetch_answers(question['question_id'])
            for ans_data in answers:
                ans_data['question_id'] = q_id
                ans_data['site_id'] = self.site_id
                # TODO: implement save_answer
                self.state.answers_crawled += 1
        except Exception as e:
            print(f"Failed to fetch answers for question {question['question_id']}: {e}")

    def _fetch_with_retry(self, fetch_func, retries: int = None):
        """Fetch with exponential backoff retry."""
        retries = retries or self.max_retries
        last_error = None

        for attempt in range(retries):
            try:
                return fetch_func()
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    wait_time = (2 ** attempt) * 1  # Exponential backoff
                    time.sleep(wait_time)

        raise last_error

    def get_status(self) -> Dict[str, Any]:
        """Get current crawler status."""
        return {
            'site_name': self.site_name,
            'site_id': self.site_id,
            'status': self.state.status.value,
            'questions_crawled': self.state.questions_crawled,
            'answers_crawled': self.state.answers_crawled,
            'images_crawled': self.state.images_crawled,
            'current_page': self.state.current_page,
            'run_id': self.state.run_id,
            'start_time': self.state.start_time,
            'error_message': self.state.error_message,
        }

    def __del__(self):
        """Cleanup on deletion."""
        if self._session:
            self._session.close()
