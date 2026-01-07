"""
AMM (American Mathematical Monthly) Crawler

Crawls Problems from Roberto Tauraso's AMM collection at University of Rome Tor Vergata.
This site hosts curated AMM problems with images.

Website: https://www.mat.uniroma2.it/~tauraso/AMM/amm.html
"""
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os
import re
from urllib.parse import urljoin, urlparse
from pathlib import Path
from datetime import datetime
import threading

from ..database import DatabaseManager, Question, Answer, Image
from .base_crawler import BaseCrawler, CrawlerState, CrawlerStatus


@dataclass
class AMMConfig:
    """AMM crawler configuration."""
    base_url: str = "https://www.mat.uniroma2.it/~tauraso/AMM"
    main_page: str = "https://www.mat.uniroma2.it/~tauraso/AMM/amm.html"
    enabled: bool = False
    max_problems: int = 10  # Number of problems to crawl per run
    request_delay: float = 2.0
    max_retries: int = 3
    timeout: int = 30
    download_images: bool = True
    images_dir: str = "/datadisk/Web2Lean/data/images/amm"


class AMMCrawlerAdapter(BaseCrawler):
    """
    Adapter to make AMMCrawler compatible with BaseCrawler interface.
    This allows the AMM crawler to be used with the existing crawler API.
    """

    def __init__(
        self,
        site_name: str,
        site_id: int,
        config: Dict[str, Any],
        db_manager: DatabaseManager
    ):
        """Initialize adapter with BaseCrawler interface."""
        super().__init__(site_name, site_id, config, db_manager)

        # Create AMM config
        amm_config = AMMConfig(
            base_url=config.get('base_url', AMMConfig.base_url),
            main_page=config.get('main_page', AMMConfig.main_page),
            enabled=config.get('enabled', True),
            max_problems=config.get('max_problems', 10),
            request_delay=config.get('request_delay', 2.0),
            max_retries=config.get('max_retries', 3),
            timeout=config.get('timeout', 30),
            download_images=config.get('download_images', True),
            images_dir=config.get('images_dir', '/datadisk/Web2Lean/data/images/amm')
        )

        # Create actual AMM crawler with reference to adapter for state updates
        self.amm_crawler = _AMMCrawlerInternal(amm_config, db_manager, self)

    def fetch_questions_page(self, page: int) -> List[Dict[str, Any]]:
        """Fetch questions (not used for AMM, but required by interface)."""
        # AMM crawler doesn't use pages, but we need this for compatibility
        return []

    def parse_question(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse question (not used for AMM, but required by interface)."""
        return raw_data

    def fetch_answers(self, question_id: int) -> List[Dict[str, Any]]:
        """Fetch answers (not used for AMM, but required by interface)."""
        return []

    def start(self, mode: str = 'incremental', **kwargs) -> str:
        """
        Start the crawler using AMM's internal crawl method.

        Args:
            mode: Crawl mode (ignored for AMM)
            **kwargs: Additional parameters (ignored for AMM)

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
            # Run the AMM crawl
            stats = self.amm_crawler.crawl()

            # Update state with results
            self.state.questions_crawled = stats.get('questions_fetched', 0)
            self.state.images_crawled = stats.get('images_fetched', 0)
            self.state.status = CrawlerStatus.COMPLETED

            # Update run record
            self.db.update_crawler_run(
                run_id,
                status='completed',
                questions_count=self.state.questions_crawled,
                images_count=self.state.images_crawled
            )

        except Exception as e:
            self.state.status = CrawlerStatus.ERROR
            self.state.error_message = str(e)
            self.db.update_crawler_run(run_id, status='failed', error_message=str(e))
            raise

        return run_id

    def get_status(self) -> Dict[str, Any]:
        """Get current crawler status."""
        return {
            'site_name': self.site_name,
            'status': self.state.status.value,
            'run_id': self.state.run_id,
            'questions_crawled': self.state.questions_crawled,
            'images_crawled': self.state.images_crawled,
            'start_time': self.state.start_time,
            'error_message': self.state.error_message
        }


class _AMMCrawlerInternal:
    """Internal AMM crawler implementation."""

    def __init__(self, config: AMMConfig, db_manager: DatabaseManager, adapter=None):
        """
        Initialize AMM crawler.

        Args:
            config: AMM crawler configuration
            db_manager: Database manager instance
            adapter: Optional AMMCrawlerAdapter for real-time state updates
        """
        self.config = config
        self.db = db_manager
        self.adapter = adapter  # For real-time state updates
        self.session = requests.Session()
        # Use realistic headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })

        # Create images directory if needed
        if self.config.download_images:
            Path(self.config.images_dir).mkdir(parents=True, exist_ok=True)

    def crawl(self) -> Dict[str, Any]:
        """
        Run crawler - fetch problems from Roberto Tauraso's AMM page.

        Returns:
            Crawl statistics
        """
        stats = {
            'questions_fetched': 0,
            'questions_skipped': 0,  # Already in database
            'answers_fetched': 0,
            'images_fetched': 0,
            'images_skipped': 0,  # Already in database
            'errors': []
        }

        try:
            # Get problems from main page
            all_problems = self._get_problems_from_main_page(limit=self.config.max_problems * 2)
            print(f"Found {len(all_problems)} problems on page")

            # Filter out problems that already exist in database
            session = self.db.get_session()
            new_problems = []
            skipped_problems = 0

            try:
                from ..database.schema import Question

                for problem in all_problems:
                    external_id = f"amm.problem.{problem['number']}"
                    existing = session.query(Question).filter(
                        Question.question_id == external_id
                    ).first()

                    if existing:
                        skipped_problems += 1
                    else:
                        new_problems.append(problem)

            finally:
                session.close()

            stats['questions_skipped'] = skipped_problems

            if skipped_problems > 0:
                print(f"  Skipped {skipped_problems} already existing problems")

            if not new_problems:
                print("  No new problems to crawl")
                return stats

            print(f"  Processing {len(new_problems)} new problems")

            # Process only new problems
            for problem in new_problems[:self.config.max_problems]:
                try:
                    # Download problem image
                    if self.config.download_images:
                        image_data = self._download_problem_image(problem)
                        if not image_data:
                            # Image download failed, skip this problem
                            error_msg = f"Image download failed for problem {problem['number']}, skipping"
                            print(f"    ✗ {error_msg}")
                            stats['errors'].append(error_msg)
                            continue

                        problem['image'] = image_data
                        stats['images_fetched'] += 1

                    # Save to database
                    self._save_to_database(problem)
                    stats['questions_fetched'] += 1

                    # Update adapter state in real-time
                    if self.adapter:
                        self.adapter.state.questions_crawled = stats['questions_fetched']
                        self.adapter.state.images_crawled = stats['images_fetched']

                    print(f"    ✓ Saved: Problem {problem['number']} - {problem['proposer']}")

                    # Be respectful
                    time.sleep(self.config.request_delay)

                except Exception as e:
                    error_msg = f"Error processing problem {problem.get('number')}: {e}"
                    print(f"    ✗ {error_msg}")
                    stats['errors'].append(error_msg)

        except Exception as e:
            error_msg = f"Crawler error: {e}"
            print(f"✗ {error_msg}")
            stats['errors'].append(error_msg)

        return stats

    def _get_problems_from_main_page(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get list of problems from main AMM page."""
        response = self._make_request(self.config.main_page)
        if not response:
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        problems = []
        # Find all table rows with problems
        table = soup.find('table', border='3')
        if not table:
            print("  ✗ Could not find problems table")
            return []

        rows = table.find_all('tr')
        count = 0

        for row in rows:
            if limit and count >= limit:
                break

            # Get the cell with problem info
            cell = row.find('td')
            if not cell:
                continue

            # Extract problem number and proposer from text
            text_content = cell.get_text(strip=True)

            # Pattern: "Problem 12583 - A. Quintero (Colombia) and S. Wagon (USA)."
            match = re.search(r'Problem\s+(\d+)\s+-\s+(.+?)\.', text_content)
            if not match:
                continue

            problem_number = match.group(1)
            proposer = match.group(2).strip()

            # Find image
            img_tag = cell.find('img')
            if not img_tag:
                continue

            img_src = img_tag.get('src')
            if not img_src:
                continue

            # Construct full image URL
            if img_src.startswith('http'):
                img_url = img_src
            else:
                # Use urljoin to properly handle relative paths
                img_url = urljoin(self.config.main_page, img_src)

            problems.append({
                'number': problem_number,
                'proposer': proposer,
                'image_url': img_url,
                'url': self.config.main_page
            })

            count += 1

        return problems

    def _download_problem_image(self, problem: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Download problem image."""
        img_url = problem['image_url']
        problem_number = problem['number']

        # Determine file extension
        parsed_url = urlparse(img_url)
        ext = os.path.splitext(parsed_url.path)[1] or '.gif'

        # Create local filename
        filename = f"amm_problem_{problem_number}{ext}"
        local_path = os.path.join(self.config.images_dir, filename)

        try:
            response = self._make_request(img_url)
            if response:
                with open(local_path, 'wb') as f:
                    f.write(response.content)

                return {
                    'url': img_url,
                    'local_path': local_path,
                    'caption': f"Problem {problem_number}",
                    'size': len(response.content)
                }
        except Exception as e:
            print(f"      Failed to download image for problem {problem_number}: {e}")
            return None

    def _save_to_database(self, problem: Dict[str, Any]):
        """Save crawled problem to database."""
        session = self.db.get_session()

        try:
            # Check if site exists
            from ..database.schema import Site
            site = session.query(Site).filter(Site.site_name == 'amm').first()
            if not site:
                # Create site
                site = Site(
                    site_name='amm',
                    site_type='amm',
                    base_url=self.config.main_page,
                    enabled=True
                )
                session.add(site)
                session.commit()
                session.refresh(site)

            # Check if question already exists
            external_id = f"amm.problem.{problem['number']}"
            existing = session.query(Question).filter(
                Question.question_id == external_id
            ).first()

            # Build title and body
            title = f"AMM Problem {problem['number']}"
            body = f"Problem {problem['number']} - Proposed by {problem['proposer']}"

            # Use image URL in body if available
            if problem.get('image'):
                body += f"\n\nImage: {problem['image']['url']}"

            # Tags as JSON array
            import json
            tags_json = json.dumps(['AMM', 'Problems', 'Math'])

            if existing:
                # Update existing
                existing.title = title
                existing.body = body
                existing.site_id = site.site_id
                question = existing
                session.commit()
            else:
                # Create new question
                question = Question(
                    question_id=external_id,
                    site_id=site.site_id,
                    title=title,
                    body=body,
                    body_html=f"<p>{body}</p>",
                    tags=tags_json,
                    score=0,
                    view_count=0,
                    answer_count=0,
                    crawled_at=datetime.now().isoformat()
                )
                session.add(question)
                session.commit()
                session.refresh(question)

            # Save image if downloaded
            if problem.get('image'):
                from ..database.schema import Image
                existing_img = session.query(Image).filter(
                    Image.question_id == question.id,
                    Image.original_url == problem['image']['url']
                ).first()

                if not existing_img and problem['image']['local_path']:
                    # Get file extension for mime type
                    import mimetypes
                    ext = os.path.splitext(problem['image']['local_path'])[1]
                    mime_type = mimetypes.guess_type(problem['image']['local_path'])[0] or 'image/gif'

                    img = Image(
                        question_id=question.id,
                        site_id=site.site_id,
                        original_url=problem['image']['url'],
                        local_path=problem['image']['local_path'],
                        file_size=problem['image'].get('size'),
                        mime_type=mime_type
                    )
                    session.add(img)

            session.commit()

        finally:
            session.close()

    def _make_request(self, url: str, method: str = 'GET') -> Optional[requests.Response]:
        """Make HTTP request with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    print(f"Request failed after {self.config.max_retries} attempts: {e}")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
        return None
