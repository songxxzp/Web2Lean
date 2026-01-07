#!/usr/bin/env python3
"""
Interactive CLI Crawler for Web2Lean
Debugging tool for testing crawlers with detailed logging

Usage:
    # Interactive mode
    python test_crawler.py

    # Non-interactive mode
    python test_crawler.py --site math --pages 2 --no-save
    python test_crawler.py --site mathoverflow --verbose --show-data --delay 10
    python test_crawler.py --site physics --pages 5 --mode history
"""
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.database import DatabaseManager
from backend.config.settings import Settings
from backend.core.stackexchange_crawler import StackExchangeCrawler, MathSECrawler, MathOverflowCrawler


class DebugCrawler(StackExchangeCrawler):
    """Extended crawler with debug output for CLI"""

    def __init__(self, *args, verbose=True, show_data=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = verbose
        self.show_data = show_data
        self._last_url = None
        self._last_response = None

    def _log_request(self, url: str, params: Dict = None, response: Any = None):
        """Log HTTP request details"""
        print(f"\n{'='*80}")
        print(f"[REQUEST] {datetime.now().strftime('%H:%M:%S')}")
        print(f"URL: {url}")
        if params:
            print(f"Params: {json.dumps(params, indent=2)}")
        if response:
            print(f"Status: {response.status_code}")
            if hasattr(response, 'headers'):
                content_type = response.headers.get('content-type', 'N/A')
                print(f"Content-Type: {content_type}")
        print(f"{'='*80}\n")

    def _log_data(self, data: Any, label: str = "DATA"):
        """Log data preview"""
        if not self.show_data:
            return

        print(f"\n[{label}]")
        if isinstance(data, list):
            print(f"Count: {len(data)} items")
            if data:
                print(f"First item preview:")
                print(json.dumps(data[0], indent=2, ensure_ascii=False)[:500])
                if len(json.dumps(data[0], ensure_ascii=False)) > 500:
                    print("... (truncated)")
        elif isinstance(data, dict):
            print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
            if len(json.dumps(data, ensure_ascii=False)) > 500:
                print("... (truncated)")
        print()

    def fetch_questions_page(self, page: int, since: int = None) -> List[Dict[str, Any]]:
        """Fetch with debug logging"""
        url = f"{self.api_base}/questions"
        params = {
            'order': 'desc',
            'sort': 'activity',
            'page': page,
            'pagesize': min(self.pages_per_run, 100),
            'filter': self.filter,
            'site': self.site_param
        }

        if since:
            params['since'] = since
        if self.api_key:
            params['key'] = self.api_key

        self._last_url = url
        if self.verbose:
            self._log_request(url, params, None)

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            if self.verbose:
                self._log_request(url, params, response)

            data = response.json()
            self._last_response = data

            if 'error_id' in data:
                raise Exception(f"API Error: {data.get('error_message', 'Unknown error')}")

            items = data.get('items', [])
            if self.verbose:
                print(f"✓ Retrieved {len(items)} questions from page {page}")
                if items:
                    print(f"  First question ID: {items[0].get('question_id')}")
                    print(f"  First question title: {items[0].get('title', 'N/A')[:60]}...")

            self._log_data(items, "QUESTIONS_DATA")

            return items

        except Exception as e:
            print(f"✗ Error fetching page {page}: {e}")
            raise

    def fetch_answers(self, question_id: int) -> List[Dict[str, Any]]:
        """Fetch answers with debug logging"""
        url = f"{self.api_base}/questions/{question_id}/answers"
        params = {
            'order': 'desc',
            'sort': 'votes',
            'site': self.site_param,
            'filter': self.answer_filter,
            'key': self.api_key
        }
        params = {k: v for k, v in params.items() if v is not None}

        if self.verbose:
            self._log_request(url, params, None)
            print(f"Fetching answers for question {question_id}...")

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()

            if self.verbose:
                self._log_request(url, params, response)

            data = response.json()
            items = data.get('items', [])

            if self.verbose:
                print(f"✓ Retrieved {len(items)} answers")

            self._log_data(items, f"ANSWERS_DATA (Q:{question_id})")

            return items

        except Exception as e:
            print(f"✗ Error fetching answers for {question_id}: {e}")
            return []

    def _process_question(self, raw_data: Dict[str, Any]):
        """Process with logging"""
        question = self.parse_question(raw_data)
        qid = question.get('question_id')

        if self.verbose:
            print(f"\n[PROCESSING] Question {qid}")
            print(f"  Title: {question.get('title', 'N/A')[:80]}")
            print(f"  Score: {question.get('score', 0)} | Answers: {question.get('answer_count', 0)}")
            print(f"  Tags: {question.get('tags', 'N/A')}")

        # Check if exists
        if self.db.question_exists(qid, self.site_id):
            if self.verbose:
                print(f"  ⊘ Question already exists, skipping")
            return

        # Fetch answers
        raw_answers = self.fetch_answers(qid)

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

        # Save question
        question['site_id'] = self.site_id
        q_id, is_new = self.db.save_question(question)

        if is_new:
            self.state.questions_crawled += 1
            if self.verbose:
                print(f"  ✓ Saved new question (DB ID: {q_id})")
        else:
            if self.verbose:
                print(f"  ⊘ Question exists in DB (ID: {q_id})")

        # Save answers
        session = self.db.get_session()
        try:
            from backend.database.schema import Answer

            for ans_data in answers_data:
                ans_data['question_id'] = q_id
                ans_data['site_id'] = self.site_id

                existing = session.query(Answer).filter(
                    Answer.answer_id == ans_data['answer_id'],
                    Answer.site_id == self.site_id
                ).first()

                if not existing:
                    answer = Answer(**ans_data)
                    session.add(answer)
                    if is_new:
                        self.state.answers_crawled += 1

            session.commit()
            if self.verbose and answers_data:
                print(f"  ✓ Saved {len(answers_data)} answers")

        except Exception as e:
            session.rollback()
            print(f"  ✗ Error saving answers: {e}")
        finally:
            session.close()


def print_banner():
    """Print CLI banner"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║              Web2Lean Interactive Crawler CLI                     ║
║                                                                    ║
║              Debugging Tool for StackExchange Crawlers            ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)


def print_menu():
    """Print main menu"""
    print("""
Main Menu:
─────────────────────────────────────────────────────────────────────
  1. Math StackExchange (math.stackexchange.com)
  2. MathOverflow (mathoverflow.net)
  3. Custom StackExchange site
  4. Exit
─────────────────────────────────────────────────────────────────────
    """)


def get_site_config() -> tuple:
    """Get site selection from user"""
    while True:
        print_menu()
        choice = input("Select crawler (1-4): ").strip()

        if choice == '1':
            return 'math_stackexchange', 'math', 'Math StackExchange'
        elif choice == '2':
            return 'mathoverflow', 'mathoverflow', 'MathOverflow'
        elif choice == '3':
            site_param = input("Enter site parameter (e.g. 'stats', 'physics'): ").strip()
            site_name = input("Enter site name: ").strip()
            return f"custom_{site_param}", site_param, site_name
        elif choice == '4':
            print("Goodbye!")
            sys.exit(0)
        else:
            print("Invalid choice, please try again.\n")


def get_crawl_options() -> Dict[str, Any]:
    """Get crawl options from user"""
    print("\nCrawl Options:")
    print("─────────────────────────────────────────────────────────────────────")

    options = {}

    # Mode
    mode_choice = input("Crawl mode (1=incremental, 2=history) [default: 1]: ").strip()
    options['mode'] = 'history' if mode_choice == '2' else 'incremental'

    # Pages
    pages = input(f"Number of pages to crawl [default: 1]: ").strip()
    options['pages'] = int(pages) if pages.isdigit() else 1

    # Verbose
    verbose = input("Verbose output (y/n) [default: y]: ").strip().lower()
    options['verbose'] = verbose != 'n'

    # Show data
    show_data = input("Show raw data (y/n) [default: n]: ").strip().lower()
    options['show_data'] = show_data == 'y'

    # Save to DB
    save_db = input("Save to database (y/n) [default: y]: ").strip().lower()
    options['save_db'] = save_db != 'n'

    # Delay
    delay = input("Request delay in seconds [default: 8]: ").strip()
    options['delay'] = float(delay) if delay else 8.0

    print("\nConfiguration:")
    print(f"  Mode: {options['mode']}")
    print(f"  Pages: {options['pages']}")
    print(f"  Verbose: {options['verbose']}")
    print(f"  Show data: {options['show_data']}")
    print(f"  Save to DB: {options['save_db']}")
    print(f"  Request delay: {options['delay']}s")
    print()

    return options


def confirm_start() -> bool:
    """Confirm start crawl"""
    confirm = input("Start crawling? (y/n): ").strip().lower()
    return confirm == 'y'


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Web2Lean Interactive Crawler CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (default)
  python test_crawler.py

  # Non-interactive mode
  python test_crawler.py --site math --pages 2
  python test_crawler.py --site mathoverflow --verbose --show-data --no-save
  python test_crawler.py --site physics --pages 5 --mode history --delay 10

  # Available sites: math, mathoverflow, stats, physics, cs, etc.
        """
    )

    parser.add_argument(
        '--site', '-s',
        type=str,
        help='Site parameter (e.g., math, mathoverflow, stats, physics)'
    )

    parser.add_argument(
        '--pages', '-p',
        type=int,
        default=1,
        help='Number of pages to crawl (default: 1)'
    )

    parser.add_argument(
        '--mode', '-m',
        type=str,
        choices=['incremental', 'history'],
        default='incremental',
        help='Crawl mode (default: incremental)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        default=True,
        help='Verbose output (default: True)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet mode (no verbose output)'
    )

    parser.add_argument(
        '--show-data',
        action='store_true',
        help='Show raw JSON data'
    )

    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Dry run mode (do not save to database)'
    )

    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=8.0,
        help='Request delay in seconds (default: 8.0)'
    )

    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Skip confirmation prompt'
    )

    return parser.parse_args()


def main():
    """Main CLI entry point"""
    # Parse command line arguments
    args = parse_args()

    # Check if running in non-interactive mode
    non_interactive = args.site is not None

    if non_interactive:
        # Non-interactive mode
        site_param = args.site
        site_name = f"custom_{site_param}" if site_param not in ['math', 'mathoverflow'] else f"{site_param}_stackexchange" if site_param == 'math' else 'mathoverflow'
        display_name = f"{site_param.title()} StackExchange" if site_param != 'mathoverflow' else 'MathOverflow'

        # Build options dict from args
        options = {
            'mode': args.mode,
            'pages': args.pages,
            'verbose': not args.quiet,
            'show_data': args.show_data,
            'save_db': not args.no_save,
            'delay': args.delay
        }

        # Skip banner for non-interactive mode
        if not args.quiet:
            print_banner()
            print(f"Running in non-interactive mode")
            print(f"Site: {display_name} ({site_param})")
            print(f"Pages: {options['pages']}")
            print(f"Mode: {options['mode']}")
            print(f"Save to DB: {options['save_db']}")
            print()
    else:
        # Interactive mode
        print_banner()

    # Initialize database and settings
    settings = Settings()
    db = DatabaseManager(settings.db_path)

    if not args.quiet:
        print(f"Database: {settings.db_path}")
        print(f"Available sites: {list(settings.site_configs.keys())}\n")

    # Get site selection (interactive mode only)
    if not non_interactive:
        site_name, site_param, display_name = get_site_config()

    # Load or create site config
    if site_name in settings.site_configs:
        config = settings.site_configs[site_name]
        site_id = list(settings.site_configs.keys()).index(site_name) + 1
        if not args.quiet:
            print(f"Loaded config for {display_name}")
    else:
        # Create default config for custom site
        config = {
            'base_url': f'https://{site_param}.stackexchange.com' if site_param != 'mathoverflow' else 'https://mathoverflow.net',
            'api_base': 'https://api.stackexchange.com/2.3',
            'enabled': True,
            'pages_per_run': 10,
            'request_delay': 8.0,
            'max_retries': 3,
            'timeout': 30,
            'site_param': site_param
        }
        site_id = len(settings.site_configs) + 1
        if not args.quiet:
            print(f"Created default config for {display_name}")

    # Get crawl options (interactive mode only)
    if not non_interactive:
        options = get_crawl_options()

        if not confirm_start():
            print("Cancelled.")
            return

    # Check confirmation in non-interactive mode
    if non_interactive and not args.no_confirm and not args.quiet:
        print("\nReady to start crawling. Press Enter to continue or Ctrl+C to cancel...")
        input()

    # Create crawler
    if not args.quiet:
        print(f"\nInitializing crawler for {display_name}...")

    crawler = DebugCrawler(
        site_name=site_name,
        site_id=site_id,
        config=config,
        db_manager=db,
        verbose=options['verbose'],
        show_data=options['show_data']
    )

    # Override config with user options
    crawler.pages_per_run = options['pages']
    crawler.request_delay = options['delay']

    if not options['save_db']:
        print("⚠ Database saving disabled - dry run mode")

    if not args.quiet:
        print(f"\n{'='*80}")
        print(f"Starting crawl at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Site: {display_name} ({site_param})")
        print(f"Mode: {options['mode']}")
        print(f"Pages: {options['pages']}")
        print(f"{'='*80}\n")

    try:
        # Override _process_question to skip DB saving if in dry run mode
        if not options['save_db']:
            original_process = crawler._process_question

            def dry_run_process(raw_data):
                question = crawler.parse_question(raw_data)
                qid = question.get('question_id')
                crawler.state.questions_crawled += 1
                print(f"[DRY RUN] Would save question {qid}: {question.get('title', 'N/A')[:60]}")

            crawler._process_question = dry_run_process

        run_id = crawler.start(mode=options['mode'])

        print(f"\n{'='*80}")
        print(f"Crawl completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Run ID: {run_id}")
        print(f"Questions crawled: {crawler.state.questions_crawled}")
        print(f"Answers crawled: {crawler.state.answers_crawled}")
        print(f"Status: {crawler.state.status.value}")
        print(f"{'='*80}\n")

    except KeyboardInterrupt:
        print("\n\nCrawl interrupted by user")
        crawler.stop()
    except Exception as e:
        print(f"\n\n✗ Crawl failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
