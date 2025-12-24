#!/usr/bin/env python3
"""
Web2Lean - Mathematical Q&A Crawler and Lean Formalization Platform

Main entry point for the application.
"""
import os
import sys
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.api import create_app


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Web2Lean Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--init-db', action='store_true', help='Initialize database and exit')
    parser.add_argument('--vllm-start', action='store_true', help='Start VLLM server for Kimina model')

    args = parser.parse_args()

    # Load settings
    settings = get_settings()

    # Override settings with CLI args
    if args.debug:
        settings.api_debug = True
    if args.port:
        settings.api_port = args.port

    # Ensure directories exist
    settings.ensure_directories()

    # Initialize database
    db = DatabaseManager(settings.db_path)
    print(f"Database initialized at: {settings.db_path}")

    if args.init_db:
        print("Database initialization complete.")
        print("\nDefault sites:")
        for site in db.get_sites():
            print(f"  - {site['site_name']}: {site['site_type']} (enabled: {site['enabled']})")
        return

    if args.vllm_start:
        print("Starting VLLM server for Kimina-Autoformalizer-7B...")
        print("Note: This requires the model to be downloaded.")
        os.system(
            f"vllm serve {settings.vllm_model_path} "
            f"--tensor-parallel-size 1 --port 8000 --host 0.0.0.0"
        )
        return

    # Create and run Flask app
    app = create_app()

    print(f"\n{'='*50}")
    print("Web2Lean Server")
    print(f"{'='*50}")
    print(f"API URL: http://{args.host}:{args.port}")
    print(f"Database: {settings.db_path}")
    print(f"Debug mode: {settings.api_debug}")
    print(f"{'='*50}\n")

    app.run(
        host=args.host,
        port=settings.api_port,
        debug=settings.api_debug
    )


if __name__ == '__main__':
    main()
