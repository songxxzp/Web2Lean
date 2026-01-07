#!/usr/bin/env python3
"""
Test script for AMM (American Mathematical Monthly) crawler

Usage:
    python test_amm_crawler.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.database import DatabaseManager
from backend.config.settings import Settings
from backend.core.amm_crawler import AMMCrawler, AMMConfig


def main():
    print("=" * 80)
    print("Testing AMM (American Mathematical Monthly) Crawler")
    print("=" * 80)
    print()

    # Initialize database and settings
    settings = Settings()
    db = DatabaseManager(settings.db_path)

    print(f"Database: {settings.db_path}")
    print()

    # Create AMM config with test settings
    config = AMMConfig(
        enabled=True,
        max_problems=2,  # Only crawl 2 problems for testing
        request_delay=1.0,  # Shorter delay for testing
        download_images=True
    )

    print("AMM Crawler Configuration:")
    print(f"  Base URL: {config.base_url}")
    print(f"  Main Page: {config.main_page}")
    print(f"  Max problems: {config.max_problems}")
    print(f"  Request delay: {config.request_delay}s")
    print(f"  Download images: {config.download_images}")
    print(f"  Images directory: {config.images_dir}")
    print()

    print("=" * 80)
    print("Starting AMM crawler...")
    print("=" * 80)
    print()

    # Create crawler
    crawler = AMMCrawler(config=config, db_manager=db)

    try:
        # Run crawler
        stats = crawler.crawl()

        print()
        print("=" * 80)
        print("Crawl Results:")
        print("=" * 80)
        print(f"  Questions fetched: {stats['questions_fetched']}")
        print(f"  Answers fetched: {stats['answers_fetched']}")
        print(f"  Images fetched: {stats['images_fetched']}")

        if stats['errors']:
            print(f"  Errors: {len(stats['errors'])}")
            for error in stats['errors']:
                print(f"    - {error}")

        print("=" * 80)
        print()

        # Show some sample data from database
        print("Sample data from database:")
        print("-" * 80)

        from backend.database.schema import Site, Question

        session = db.get_session()
        try:
            site = session.query(Site).filter(Site.site_name == 'amm').first()
            if site:
                print(f"Site ID: {site.site_id}")
                print(f"Site Name: {site.site_name}")
                print(f"Site Type: {site.site_type}")
                print(f"Base URL: {site.base_url}")

                # Get recent questions
                questions = session.query(Question).filter(
                    Question.site_id == site.site_id
                ).order_by(Question.id.desc()).limit(2).all()

                print(f"\nRecent questions from AMM:")
                for q in questions:
                    print(f"\n  Question ID: {q.question_id}")
                    print(f"  Title: {q.title[:80]}...")
                    print(f"  Created: {q.crawled_at}")

                    # Show images
                    from backend.database.schema import Image
                    images = session.query(Image).filter(Image.question_id == q.id).all()
                    if images:
                        print(f"  Images: {len(images)}")
                        for img in images[:3]:  # Show first 3
                            print(f"    - {img.original_url}")
                            if img.local_path:
                                print(f"      Local: {img.local_path}")
                                print(f"      Size: {img.file_size} bytes")

        finally:
            session.close()

        print()
        print("✓ Test completed successfully!")

    except Exception as e:
        print()
        print("=" * 80)
        print("✗ Test failed with error:")
        print("=" * 80)
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
