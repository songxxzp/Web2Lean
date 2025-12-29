"""
Flask application factory for Web2Lean API.
"""
from flask import Flask, jsonify
from flask_cors import CORS
import logging
from pathlib import Path

from ..config import get_settings
from ..database import DatabaseManager
from ..version import BACKEND_VERSION
from .routes import (
    crawlers_bp, statistics_bp, processing_bp,
    database_bp, config_bp, verification_bp
)


def create_app(config_path: str = None) -> Flask:
    """
    Create Flask application.

    Args:
        config_path: Optional path to config file

    Returns:
        Flask application
    """
    app = Flask(__name__)

    # Load settings
    settings = get_settings()
    app.config['settings'] = settings
    app.config['db'] = DatabaseManager(settings.db_path)

    # Enable CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Setup logging
    setup_logging(app)

    # Clean up any stuck preprocessing status from previous runs
    cleanup_stuck_preprocessing(app)

    # Register blueprints
    app.register_blueprint(crawlers_bp, url_prefix='/api/crawlers')
    app.register_blueprint(statistics_bp, url_prefix='/api/statistics')
    app.register_blueprint(processing_bp, url_prefix='/api/processing')
    app.register_blueprint(database_bp, url_prefix='/api/database')
    app.register_blueprint(config_bp, url_prefix='/api/config')
    app.register_blueprint(verification_bp, url_prefix='/api/verification')

    # Root endpoint
    @app.route('/')
    def index():
        return jsonify({
            'name': 'Web2Lean API',
            'version': BACKEND_VERSION,
            'status': 'running'
        })

    # Health check
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy'})

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return app


def setup_logging(app: Flask):
    """Setup application logging."""
    settings = app.config['settings']
    log_dir = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'api.log'),
            logging.StreamHandler()
        ]
    )


def cleanup_stuck_preprocessing(app: Flask):
    """
    Clean up questions stuck in 'preprocessing' status on backend startup.

    This handles cases where the backend was shut down while preprocessing was in progress.
    """
    try:
        db = app.config['db']
        count = db.cleanup_stuck_preprocessing()
        if count > 0:
            logging.info(f'Cleaned up {count} questions stuck in preprocessing status on startup')
    except Exception as e:
        logging.error(f'Error cleaning up stuck preprocessing on startup: {e}')
