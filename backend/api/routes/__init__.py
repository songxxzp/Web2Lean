"""
API route blueprints.
Import and register all route modules.
"""
from flask import Blueprint

# Import blueprints from route modules
from .crawlers import crawlers_bp
from .statistics import statistics_bp
from .processing import processing_bp
from .database import database_bp
from .config import config_bp

__all__ = [
    'crawlers_bp',
    'statistics_bp',
    'processing_bp',
    'database_bp',
    'config_bp'
]
