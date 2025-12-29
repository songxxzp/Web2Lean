"""
Statistics API endpoints.
"""
from flask import Blueprint, jsonify, current_app, request

statistics_bp = Blueprint('statistics', __name__)


@statistics_bp.route('/overview', methods=['GET', 'OPTIONS'])
def get_overview_statistics():
    """Get overall statistics."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    stats = db.get_statistics()
    return jsonify(stats)


@statistics_bp.route('/site/<int:site_id>', methods=['GET', 'OPTIONS'])
def get_site_statistics(site_id: int):
    """Get statistics for a specific site."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    stats = db.get_site_statistics(site_id)
    if stats is None:
        return jsonify({'error': 'Site not found'}), 404
    return jsonify(stats)


@statistics_bp.route('/processing', methods=['GET', 'OPTIONS'])
def get_processing_statistics():
    """Get processing pipeline statistics."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    stats = db.get_statistics()
    return jsonify(stats.get('processing_status', {}))


@statistics_bp.route('/detailed', methods=['GET', 'OPTIONS'])
def get_detailed_statistics():
    """Get detailed statistics for dashboard."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']

    # Get all detailed stats
    site_stats = db.get_detailed_site_statistics()
    preprocessing_stats = db.get_preprocessing_statistics()
    verification_stats = db.get_verification_statistics()

    return jsonify({
        'by_site_detailed': site_stats,
        'preprocessing': preprocessing_stats,
        'verification': verification_stats,
    })
