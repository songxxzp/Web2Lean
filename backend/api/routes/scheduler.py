"""
Scheduler API endpoints for managing scheduled tasks.
"""
from flask import Blueprint, request, jsonify, current_app

scheduler_bp = Blueprint('scheduler', __name__)


@scheduler_bp.route('/tasks', methods=['GET', 'OPTIONS'])
def list_tasks():
    """Get all scheduled tasks."""
    if request.method == 'OPTIONS':
        return '', 200

    task_scheduler = current_app.config.get('task_scheduler')
    if not task_scheduler:
        return jsonify({'error': 'Scheduler not available'}), 500

    tasks = task_scheduler.get_all_tasks()
    return jsonify({'tasks': tasks})


@scheduler_bp.route('/tasks', methods=['POST', 'OPTIONS'])
def create_task():
    """Create a new scheduled task."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}

    # Validate required fields
    if 'task_name' not in data or 'task_type' not in data:
        return jsonify({'error': 'Missing required fields: task_name, task_type'}), 400

    task_scheduler = current_app.config.get('task_scheduler')
    if not task_scheduler:
        return jsonify({'error': 'Scheduler not available'}), 500

    result = task_scheduler.add_task(
        task_name=data['task_name'],
        task_type=data['task_type'],
        site_id=data.get('site_id'),
        interval_days=data.get('interval_days', 0),
        interval_hours=data.get('interval_hours', 24),
        interval_minutes=data.get('interval_minutes', 0),
        enabled=data.get('enabled', False),
        config_json=data.get('config_json')
    )

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)


@scheduler_bp.route('/tasks/<task_name>', methods=['PUT', 'OPTIONS'])
def update_task(task_name: str):
    """Update an existing scheduled task."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}

    # Remove task_name from data if present (it comes from URL)
    data.pop('task_name', None)

    task_scheduler = current_app.config.get('task_scheduler')
    if not task_scheduler:
        return jsonify({'error': 'Scheduler not available'}), 500

    result = task_scheduler.update_task(task_name, **data)

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)


@scheduler_bp.route('/tasks/<task_name>', methods=['DELETE', 'OPTIONS'])
def delete_task(task_name: str):
    """Delete a scheduled task."""
    if request.method == 'OPTIONS':
        return '', 200

    task_scheduler = current_app.config.get('task_scheduler')
    if not task_scheduler:
        return jsonify({'error': 'Scheduler not available'}), 500

    success = task_scheduler.delete_task(task_name)

    if not success:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify({'message': 'Task deleted successfully'})


@scheduler_bp.route('/status', methods=['GET', 'OPTIONS'])
def get_scheduler_status():
    """Get the status of the task scheduler."""
    if request.method == 'OPTIONS':
        return '', 200

    task_scheduler = current_app.config.get('task_scheduler')
    if not task_scheduler:
        return jsonify({'error': 'Scheduler not available'}), 500

    status = task_scheduler.get_task_status()
    return jsonify(status)
