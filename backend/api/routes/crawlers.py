"""
Crawler control API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
import threading

crawlers_bp = Blueprint('crawlers', __name__)

# Active crawler instances per site
_active_crawlers = {}


@crawlers_bp.route('/start', methods=['POST', 'OPTIONS'])
def start_crawler():
    """Start a crawler for a specific site."""
    # Handle OPTIONS preflight
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json()
    site_name = data.get('site_name')
    mode = data.get('mode', 'incremental')

    if not site_name:
        return jsonify({'error': 'site_name is required'}), 400

    db = current_app.config['db']

    # Get site info
    site = db.get_site_by_name(site_name)
    if not site:
        return jsonify({'error': f'Site {site_name} not found'}), 404

    if not site['enabled']:
        return jsonify({'error': f'Site {site_name} is disabled'}), 400

    # Check if already running
    if site_name in _active_crawlers:
        crawler = _active_crawlers[site_name]
        if crawler.get('status') == 'running':
            return jsonify({'error': f'Crawler for {site_name} is already running'}), 400

    # Create and start crawler
    try:
        from ...core.math_se_crawler import MathSECrawler

        # Get config from config_json
        import json
        if isinstance(site.get('config_json'), str):
            config = json.loads(site['config_json'])
        else:
            config = {}

        # Add API base and other site-level fields to config
        config['api_base'] = site.get('api_base') or config.get('api_base')
        config['base_url'] = site.get('base_url') or config.get('base_url')
        config['site_type'] = site.get('site_type')

        crawler = MathSECrawler(
            site_name=site_name,
            site_id=site['site_id'],
            config=config,
            db_manager=db
        )

        # Run in background thread
        def run_crawler():
            try:
                crawler.start(mode=mode)
            except Exception as e:
                print(f"Crawler error: {e}")
                import traceback
                traceback.print_exc()

        thread = threading.Thread(target=run_crawler, daemon=True)
        thread.start()

        _active_crawlers[site_name] = {
            'crawler': crawler,
            'thread': thread,
            'status': 'running'
        }

        return jsonify({
            'message': f'Crawler for {site_name} started',
            'run_id': crawler.state.run_id,
            'mode': mode
        })

    except ImportError as e:
        return jsonify({'error': f'Crawler not implemented: {e}'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@crawlers_bp.route('/stop/<site_name>', methods=['POST', 'OPTIONS'])
def stop_crawler(site_name):
    """Stop a crawler for a specific site."""
    if request.method == 'OPTIONS':
        return '', 200

    if site_name not in _active_crawlers:
        return jsonify({'error': f'No active crawler for {site_name}'}), 404

    crawler_info = _active_crawlers[site_name]
    crawler_info['crawler'].stop()
    crawler_info['status'] = 'stopped'

    return jsonify({'message': f'Crawler for {site_name} stopped'})


@crawlers_bp.route('/status', methods=['GET', 'OPTIONS'])
def get_all_crawler_status():
    """Get status of all crawlers."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']

    # Get active crawler statuses
    active_statuses = {}
    for site_name, info in _active_crawlers.items():
        try:
            status = info['crawler'].get_status()
            active_statuses[site_name] = status
            # Update stored status
            info['status'] = status.get('status', 'unknown')
        except Exception as e:
            active_statuses[site_name] = {'error': str(e)}

    # Get all sites
    sites = db.get_sites()

    return jsonify({
        'active_crawlers': active_statuses,
        'all_sites': sites
    })


@crawlers_bp.route('/status/<site_name>', methods=['GET', 'OPTIONS'])
def get_crawler_status(site_name):
    """Get status of a specific crawler."""
    if request.method == 'OPTIONS':
        return '', 200

    if site_name in _active_crawlers:
        return jsonify(_active_crawlers[site_name]['crawler'].get_status())

    # Return idle status if not active
    db = current_app.config['db']
    site = db.get_site_by_name(site_name)

    if not site:
        return jsonify({'error': f'Site {site_name} not found'}), 404

    return jsonify({
        'site_name': site_name,
        'status': 'idle'
    })
