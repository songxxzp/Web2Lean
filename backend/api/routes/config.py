"""
Configuration API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app

config_bp = Blueprint('config', __name__)


@config_bp.route('/sites', methods=['GET', 'OPTIONS'])
def get_sites():
    """Get all site configurations."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    sites = db.get_sites()
    return jsonify(sites)


@config_bp.route('/prompts', methods=['GET', 'OPTIONS'])
def get_prompts():
    """Get LLM prompts."""
    if request.method == 'OPTIONS':
        return '', 200

    settings = current_app.config['settings']
    return jsonify(settings.prompts)


@config_bp.route('/schedules', methods=['GET', 'OPTIONS'])
def get_schedules():
    """Get scheduled tasks."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    session = db.get_session()

    try:
        from backend.database.schema import ScheduledTask
        tasks = session.query(ScheduledTask).all()

        return jsonify([
            {
                'id': t.id,
                'task_name': t.task_name,
                'task_type': t.task_type,
                'site_id': t.site_id,
                'interval_hours': t.interval_hours,
                'interval_minutes': t.interval_minutes,
                'last_run': t.last_run,
                'next_run': t.next_run,
                'enabled': t.enabled,
            }
            for t in tasks
        ])
    finally:
        session.close()
