"""
Database viewing API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app

database_bp = Blueprint('database', __name__)


@database_bp.route('/clear', methods=['POST', 'OPTIONS'])
def clear_data():
    """Clear data by stage or completely."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    stage = data.get('stage')  # 'lean', 'verification', 'preprocess', 'failed', 'raw', or 'all'

    db = current_app.config['db']
    session = db.get_session()

    try:
        from backend.database.schema import ProcessingStatus, Question, Answer, Image

        if stage == 'lean':
            # Clear all lean_code and verification status
            count = session.query(ProcessingStatus).filter(
                ProcessingStatus.lean_code.isnot(None)
            ).update({
                ProcessingStatus.lean_code: None,
                ProcessingStatus.status: 'preprocessed',
                ProcessingStatus.verification_status: None,
                ProcessingStatus.verification_has_errors: None,
                ProcessingStatus.verification_has_warnings: None,
                ProcessingStatus.verification_messages: None,
                ProcessingStatus.verification_error: None,
                ProcessingStatus.verification_time: None,
                ProcessingStatus.verification_completed_at: None
            }, synchronize_session=False)
            session.commit()
            return jsonify({'message': f'Cleared lean code from {count} questions'})

        elif stage == 'verification':
            # Clear all verification status but keep lean code
            count = session.query(ProcessingStatus).filter(
                ProcessingStatus.verification_status.isnot(None)
            ).update({
                ProcessingStatus.verification_status: None,
                ProcessingStatus.verification_has_errors: None,
                ProcessingStatus.verification_has_warnings: None,
                ProcessingStatus.verification_messages: None,
                ProcessingStatus.verification_error: None,
                ProcessingStatus.verification_time: None,
                ProcessingStatus.verification_completed_at: None
            }, synchronize_session=False)
            session.commit()
            return jsonify({'message': f'Cleared verification status from {count} questions'})

        elif stage == 'preprocess':
            # Clear preprocessed data, lean code, verification status, and failed/cant_convert status
            ps_query = session.query(ProcessingStatus).filter(
                ProcessingStatus.status.in_(['preprocessed', 'lean_converted', 'failed', 'cant_convert'])
            )
            count = ps_query.count()
            ps_query.update({
                ProcessingStatus.status: 'raw',
                ProcessingStatus.preprocessed_body: None,
                ProcessingStatus.preprocessed_answer: None,
                ProcessingStatus.correction_notes: None,
                ProcessingStatus.lean_code: None,
                ProcessingStatus.lean_error: None,
                ProcessingStatus.current_stage: None,
                ProcessingStatus.verification_status: None,
                ProcessingStatus.verification_has_errors: None,
                ProcessingStatus.verification_has_warnings: None,
                ProcessingStatus.verification_messages: None,
                ProcessingStatus.verification_error: None,
                ProcessingStatus.verification_time: None,
                ProcessingStatus.verification_completed_at: None
            }, synchronize_session=False)
            session.commit()
            return jsonify({'message': f'Cleared preprocessed data from {count} questions'})

        elif stage == 'failed':
            # Reset all failed questions to raw status
            ps_query = session.query(ProcessingStatus).filter(
                ProcessingStatus.status == 'failed'
            )
            count = ps_query.count()
            ps_query.update({
                ProcessingStatus.status: 'raw',
                ProcessingStatus.preprocessed_body: None,
                ProcessingStatus.preprocessed_answer: None,
                ProcessingStatus.correction_notes: None,
                ProcessingStatus.lean_code: None,
                ProcessingStatus.lean_error: None,
                ProcessingStatus.current_stage: None
            }, synchronize_session=False)
            session.commit()
            return jsonify({'message': f'Reset {count} failed questions to raw status'})

        elif stage == 'raw':
            # Delete all raw questions and related data
            # First get count
            count = session.query(Question).count()

            # Delete all processing status
            session.query(ProcessingStatus).delete()

            # Delete all images
            session.query(Image).delete()

            # Delete all answers
            session.query(Answer).delete()

            # Delete all questions
            session.query(Question).delete()

            session.commit()
            return jsonify({'message': f'Deleted all {count} questions'})

        else:
            return jsonify({'error': 'Invalid stage'}), 400

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@database_bp.route('/questions/<int:question_id>/clear', methods=['POST', 'OPTIONS'])
def clear_question_stage(question_id: int):
    """Clear data from a specific stage for a question."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    stage = data.get('stage')  # 'lean', 'preprocess', 'raw'

    db = current_app.config['db']
    session = db.get_session()

    try:
        from backend.database.schema import ProcessingStatus, Question, Answer, Image

        # Get question
        question = session.query(Question).filter(Question.id == question_id).first()
        if not question:
            return jsonify({'error': 'Question not found'}), 404

        if stage == 'lean':
            # Clear lean code and verification status
            ps = session.query(ProcessingStatus).filter(
                ProcessingStatus.question_id == question_id
            ).first()
            if ps:
                ps.lean_code = None
                ps.verification_status = None
                ps.verification_has_errors = None
                ps.verification_has_warnings = None
                ps.verification_messages = None
                ps.verification_error = None
                ps.verification_time = None
                ps.verification_completed_at = None
                if ps.status == 'lean_converted':
                    ps.status = 'preprocessed'
            session.commit()
            return jsonify({'message': 'Cleared lean code'})

        elif stage == 'preprocess':
            # Clear preprocessed data, lean code, verification status, and failed/cant_convert status
            ps = session.query(ProcessingStatus).filter(
                ProcessingStatus.question_id == question_id
            ).first()
            if ps:
                ps.preprocessed_body = None
                ps.preprocessed_answer = None
                ps.correction_notes = None
                ps.lean_code = None
                ps.lean_error = None
                ps.verification_status = None
                ps.verification_has_errors = None
                ps.verification_has_warnings = None
                ps.verification_messages = None
                ps.verification_error = None
                ps.verification_time = None
                ps.verification_completed_at = None
                # Reset to raw for preprocessed, lean_converted, failed, cant_convert
                if ps.status in ['preprocessed', 'lean_converted', 'failed', 'cant_convert']:
                    ps.status = 'raw'
                ps.current_stage = None
            session.commit()
            return jsonify({'message': 'Cleared preprocessed data'})

        elif stage == 'raw':
            # Delete entire question and related data
            # Delete images
            session.query(Image).filter(Image.question_id == question_id).delete()
            # Delete answers
            session.query(Answer).filter(Answer.question_id == question_id).delete()
            # Delete processing status
            session.query(ProcessingStatus).filter(
                ProcessingStatus.question_id == question_id
            ).delete()
            # Delete question
            session.query(Question).filter(Question.id == question_id).delete()
            session.commit()
            return jsonify({'message': 'Deleted question'})

        else:
            return jsonify({'error': 'Invalid stage'}), 400

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


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
    result = db.list_questions(
        site_id=site_id,
        status=status,
        limit=limit,
        offset=offset
    )

    return jsonify({
        'questions': result['questions'],
        'count': result['total'],
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
