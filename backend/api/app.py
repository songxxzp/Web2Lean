"""
Flask application factory for Web2Lean API.
"""
from flask import Flask, jsonify
from flask_cors import CORS
import logging
from pathlib import Path

from ..config import get_settings
from ..database import DatabaseManager
from .routes import (
    crawlers_bp, statistics_bp, processing_bp,
    database_bp, config_bp
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

    # Register blueprints
    app.register_blueprint(crawlers_bp, url_prefix='/api/crawlers')
    app.register_blueprint(statistics_bp, url_prefix='/api/statistics')
    app.register_blueprint(processing_bp, url_prefix='/api/processing')
    app.register_blueprint(database_bp, url_prefix='/api/database')
    app.register_blueprint(config_bp, url_prefix='/api/config')

    # Root endpoint
    @app.route('/')
    def index():
        return jsonify({
            'name': 'Web2Lean API',
            'version': '1.0.0',
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
