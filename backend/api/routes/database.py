"""
Database viewing API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app

database_bp = Blueprint('database', __name__)


@database_bp.route('/questions', methods=['GET', 'OPTIONS'])
def list_questions():
    """List questions with optional filters."""
    if request.method == 'OPTIONS':
        return '', 200

    site_id = request.args.get('site_id', type=int)
    status = request.args.get('status')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    db = current_app.config['db']
    questions = db.list_questions(
        site_id=site_id,
        status=status,
        limit=limit,
        offset=offset
    )

    return jsonify({
        'questions': questions,
        'count': len(questions),
        'limit': limit,
        'offset': offset
    })


@database_bp.route('/questions/<int:question_id>', methods=['GET', 'OPTIONS'])
def get_question_detail(question_id: int):
    """Get detailed information about a question."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    question = db.get_question(question_id)

    if not question:
        return jsonify({'error': 'Question not found'}), 404

    return jsonify(question)


@database_bp.route('/questions/<int:question_id>/images', methods=['GET', 'OPTIONS'])
def get_question_images(question_id: int):
    """Get images for a question."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    question = db.get_question(question_id)

    if not question:
        return jsonify({'error': 'Question not found'}), 404

    return jsonify(question.get('images', []))


@database_bp.route('/statistics', methods=['GET', 'OPTIONS'])
def get_database_statistics():
    """Get database statistics."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    stats = db.get_statistics()
    return jsonify(stats)
