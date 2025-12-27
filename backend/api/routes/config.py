"""
Configuration API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
import json

config_bp = Blueprint('config', __name__)


@config_bp.route('/sites', methods=['GET', 'OPTIONS'])
def get_sites():
    """Get all site configurations."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    sites = db.get_sites()
    return jsonify(sites)


@config_bp.route('/sites/<int:site_id>', methods=['PUT', 'OPTIONS'])
def update_site(site_id):
    """Update a site configuration."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json()
    db = current_app.config['db']

    session = db.get_session()
    try:
        from backend.database.schema import Site

        site = session.query(Site).filter(Site.site_id == site_id).first()
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        # Update allowed fields
        if 'enabled' in data:
            site.enabled = data['enabled']
        if 'config' in data:
            # Merge config with existing config
            existing_config = {}
            if site.config_json:
                try:
                    existing_config = json.loads(site.config_json)
                except:
                    pass
            existing_config.update(data['config'])
            site.config_json = json.dumps(existing_config)

        session.commit()
        return jsonify({'message': 'Site updated successfully'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


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


@config_bp.route('/models', methods=['GET', 'OPTIONS'])
def get_models():
    """Get LLM model configuration."""
    if request.method == 'OPTIONS':
        return '', 200

    settings = current_app.config['settings']
    # Convert empty string to 'local' for frontend
    lean_model = settings.glm_lean_model if settings.glm_lean_model else 'local'
    return jsonify({
        'glm_text_model': settings.glm_text_model,
        'glm_vision_model': settings.glm_vision_model,
        'glm_lean_model': lean_model,
        'vllm_base_url': settings.vllm_base_url,
        'vllm_model_path': settings.vllm_model_path,
    })


@config_bp.route('/models', methods=['PUT', 'OPTIONS'])
def update_models():
    """Update LLM model configuration."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json()
    settings = current_app.config['settings']

    # Update model settings
    if 'glm_text_model' in data:
        settings.glm_text_model = data['glm_text_model']
    if 'glm_vision_model' in data:
        settings.glm_vision_model = data['glm_vision_model']
    if 'glm_lean_model' in data:
        # Convert 'local' back to empty string for internal use
        lean_model = data['glm_lean_model']
        settings.glm_lean_model = '' if lean_model == 'local' else lean_model

    # Save to environment file (optional)
    try:
        env_file = settings.base_dir / '.env'
        env_vars = {}
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value

        # Update model vars
        env_vars['GLM_TEXT_MODEL'] = settings.glm_text_model
        env_vars['GLM_VISION_MODEL'] = settings.glm_vision_model
        env_vars['GLM_LEAN_MODEL'] = settings.glm_lean_model

        with open(env_file, 'w') as f:
            for key, value in env_vars.items():
                f.write(f'{key}={value}\n')
    except Exception as e:
        # Non-fatal if we can't save .env
        pass

    # Convert back to 'local' for response
    lean_model_response = settings.glm_lean_model if settings.glm_lean_model else 'local'
    return jsonify({
        'message': 'Models updated successfully',
        'models': {
            'glm_text_model': settings.glm_text_model,
            'glm_vision_model': settings.glm_vision_model,
            'glm_lean_model': lean_model_response,
        }
    })
