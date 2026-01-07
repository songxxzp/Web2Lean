"""
AMM (American Mathematical Monthly) Crawler

Crawls Problems and Solutions sections from The American Mathematical Monthly journal.
Published by Taylor & Francis.

Target: Open access Problems and Solutions articles
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
import hashlib
from datetime import datetime

from ..database import DatabaseManager, Question, Answer, Image


@dataclass
class AMMConfig:
    """AMM crawler configuration."""
    base_url: str = "https://www.tandfonline.com"
    journal_code: str = "uamm20"
    enabled: bool = False
    pages_per_run: int = 1  # Number of issues to crawl per run
    request_delay: float = 5.0
    max_retries: int = 3
    timeout: int = 30
    download_images: bool = True
    images_dir: str = "/datadisk/Web2Lean/data/images/amm"


class AMMCrawler:
    """Crawler for American Mathematical Monthly Problems and Solutions."""

    def __init__(self, config: AMMConfig, db_manager: DatabaseManager):
        """
        Initialize AMM crawler.

        Args:
            config: AMM crawler configuration
            db_manager: Database manager instance
        """
        self.config = config
        self.db = db_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        # Create images directory if needed
        if self.config.download_images:
            Path(self.config.images_dir).mkdir(parents=True, exist_ok=True)

    def crawl(self) -> Dict[str, Any]:
        """
        Run crawler - fetch recent issues and save to database.

        Returns:
            Crawl statistics
        """
        stats = {
            'questions_fetched': 0,
            'answers_fetched': 0,
            'images_fetched': 0,
            'errors': []
        }

        try:
            # Get recent issues
            issues = self._get_issues_list(limit=self.config.pages_per_run)
            print(f"Found {len(issues)} issues to crawl")

            for issue in issues:
                try:
                    # Get articles from this issue
                    articles = self._get_problems_articles(issue)
                    print(f"  Found {len(articles)} Problems and Solutions articles")

                    for article in articles:
                        try:
                            # Get full content
                            content = self._get_article_content(article)
                            if content:
                                # Save to database
                                self._save_to_database(content)
                                stats['questions_fetched'] += 1
                                stats['images_fetched'] += len(content.get('images', []))

                                print(f"    ✓ Saved: {content['title']}")
                                print(f"      {len(content.get('problems', []))} problems, {len(content.get('images', []))} images")

                            # Be respectful
                            time.sleep(self.config.request_delay)

                        except Exception as e:
                            error_msg = f"Error processing article {article.get('url')}: {e}"
                            print(f"    ✗ {error_msg}")
                            stats['errors'].append(error_msg)

                except Exception as e:
                    error_msg = f"Error processing issue {issue['volume']}.{issue['issue']}: {e}"
                    print(f"  ✗ {error_msg}")
                    stats['errors'].append(error_msg)

        except Exception as e:
            error_msg = f"Crawler error: {e}"
            print(f"✗ {error_msg}")
            stats['errors'].append(error_msg)

        return stats

    def _get_issues_list(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get list of available issues."""
        url = f"{self.config.base_url}/toc/{self.config.journal_code}/current"
        response = self._make_request(url)
        if not response:
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        issues = []
        # Parse issue list from dropdown
        issue_links = soup.select('a[href*="/toc/uamm20/"]')

        seen = set()
        for link in issue_links[:limit] if limit else issue_links:
            href = link.get('href', '')
            if '/toc/uamm20/' in href:
                match = re.search(r'/toc/uamm20/(\d+)/(\d+)', href)
                if match:
                    volume, issue = match.groups()
                    issue_id = f"{volume}.{issue}"

                    if issue_id not in seen:
                        seen.add(issue_id)
                        issues.append({
                            'volume': int(volume),
                            'issue': int(issue),
                            'url': urljoin(self.config.base_url, href),
                            'journal_code': self.config.journal_code
                        })

        return issues

    def _get_problems_articles(self, issue: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get Problems and Solutions articles from an issue."""
        response = self._make_request(issue['url'])
        if not response:
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        articles = []

        # Find all articles in "Problems and Solutions" section
        for section in soup.find_all('div', class_='section'):
            section_title = section.find('h2')
            if section_title and 'Problems and Solutions' in section_title.get_text():
                for article_div in section.find_all('div', class_='item'):
                    # Skip if not open access
                    access_icon = article_div.find('span', class_='accessIcon')
                    if access_icon and 'padlock' in access_icon.get('class', []):
                        continue

                    title_link = article_div.find('a', href=re.compile(r'/doi/'))
                    if not title_link:
                        continue

                    article_url = urljoin(self.config.base_url, title_link['href'])
                    title = title_link.get_text(strip=True)

                    pages_span = article_div.find('span', string=re.compile(r'Pages?:'))
                    pages = pages_span.get_text(strip=True).replace('Pages:', '').strip() if pages_span else None

                    doi_match = re.search(r'/doi/(10\.1080/[^\s]+)', article_url)
                    doi = doi_match.group(1) if doi_match else None

                    articles.append({
                        'title': title,
                        'url': article_url,
                        'pages': pages,
                        'doi': doi,
                        'volume': issue['volume'],
                        'issue': issue['issue'],
                        'journal_code': self.config.journal_code,
                        'section': 'Problems and Solutions'
                    })

        return articles

    def _get_article_content(self, article: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get full content of an article."""
        response = self._make_request(article['url'])
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        full_text_div = soup.find('div', class_='fullText')
        if not full_text_div:
            return None

        body_html = str(full_text_div)

        # Extract authors
        authors = []
        author_divs = soup.find_all('div', class_='authors')
        if author_divs:
            for author_div in author_divs:
                author_links = author_div.find_all('a', class_='email')
                authors.extend([a.get_text(strip=True) for a in author_links])

        # Extract PDF URL
        pdf_url = None
        pdf_link = soup.find('a', string=re.compile(r'PDF'))
        if pdf_link:
            pdf_url = urljoin(self.config.base_url, pdf_link.get('href', ''))

        # Extract and download images
        images = self._extract_images(full_text_div, article)

        # Parse individual problems
        problems = self._parse_problems(full_text_div)

        # Generate external ID
        external_id = self._generate_external_id(article)

        return {
            'external_id': external_id,
            'volume': article['volume'],
            'issue': article['issue'],
            'pages': article['pages'],
            'section': article['section'],
            'title': article['title'],
            'authors': authors,
            'body': full_text_div.get_text(strip=True, separator=' '),
            'body_html': body_html,
            'problems': problems,
            'images': images,
            'doi': article['doi'],
            'pdf_url': pdf_url,
            'full_text_url': article['url'],
            'crawled_at': datetime.now().isoformat()
        }

    def _extract_images(self, content_div, article: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract and optionally download images."""
        images = []
        img_tags = content_div.find_all('img')

        for idx, img in enumerate(img_tags):
            src = img.get('src') or img.get('data-src')
            if not src or not src.startswith('http'):
                continue

            img_url = urljoin(self.config.base_url, src)

            external_id = self._generate_external_id(article)
            ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
            filename = f"{external_id}.img{idx}{ext}"
            local_path = os.path.join(self.config.images_dir, filename)

            image_data = {
                'url': img_url,
                'local_path': local_path if self.config.download_images else None,
                'caption': img.get('alt') or img.get('title', '')
            }

            if self.config.download_images:
                try:
                    img_response = self._make_request(img_url)
                    if img_response:
                        with open(local_path, 'wb') as f:
                            f.write(img_response.content)
                        image_data['size'] = len(img_response.content)
                except Exception as e:
                    print(f"      Failed to download image: {e}")
                    image_data['local_path'] = None

            images.append(image_data)

        return images

    def _parse_problems(self, content_div) -> List[Dict[str, str]]:
        """Parse individual problems from article content."""
        problems = []
        content_html = str(content_div)

        # Find problem numbers (4 or 5 digit numbers)
        problem_pattern = r'(\b\d{4,5}\b)[.:\s]+'
        parts = re.split(problem_pattern, content_html)

        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    number = parts[i]
                    content = parts[i + 1]

                    solution_match = re.split(r'Solution:?\s*', content, maxsplit=1, flags=re.IGNORECASE)

                    problems.append({
                        'number': number,
                        'statement': solution_match[0] if solution_match else content,
                        'solution': solution_match[1] if len(solution_match) > 1 else None
                    })

        return problems

    def _generate_external_id(self, article: Dict[str, Any]) -> str:
        """Generate unique external ID for an article."""
        first_page = article.get('pages', '').split('-')[0] if article.get('pages') else 'unknown'
        return f"{article['journal_code']}.v{article['volume']}.i{article['issue']}.p{first_page}"

    def _save_to_database(self, content: Dict[str, Any]):
        """Save crawled content to database."""
        session = self.db.get_session()

        try:
            # Check if already exists
            from ..database.schema import Site
            site = session.query(Site).filter(Site.name == 'amm').first()
            if not site:
                # Create site
                site = Site(
                    name='amm',
                    display_name='American Mathematical Monthly',
                    site_type='amm',
                    base_url=self.config.base_url
                )
                session.add(site)
                session.commit()
                session.refresh(site)

            # Check if question already exists
            existing = session.query(Question).filter(
                Question.question_id == content['external_id']
            ).first()

            if existing:
                # Update existing
                existing.title = content['title']
                existing.body = content['body']
                existing.body_html = content['body_html']
                existing.site_id = site.id
                session.commit()
            else:
                # Create new question
                question = Question(
                    question_id=content['external_id'],
                    site_id=site.id,
                    title=content['title'],
                    body=content['body'],
                    body_html=content['body_html'],
                    tags='Problems,Solutions,Math',
                    score=0,
                    view_count=0,
                    answer_count=len(content.get('problems', [])),
                    crawled_at=datetime.now().isoformat()
                )
                session.add(question)
                session.commit()
                session.refresh(question)

            # Save images
            for img_data in content.get('images', []):
                existing_img = session.query(Image).filter(
                    Image.question_id == question.id,
                    Image.url == img_data['url']
                ).first()

                if not existing_img and img_data['local_path']:
                    img = Image(
                        question_id=question.id,
                        url=img_data['url'],
                        local_path=img_data['local_path'],
                        caption=img_data['caption']
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

