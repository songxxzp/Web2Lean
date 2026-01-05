"""
Lean verification API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
import threading

verification_bp = Blueprint('verification', __name__)


@verification_bp.route('/verify/<int:question_id>', methods=['POST', 'OPTIONS'])
def verify_lean_code(question_id: int):
    """Verify Lean code for a question."""
    if request.method == 'OPTIONS':
        return '', 200

    from ...processing import LeanVerifier
    from ...database import DatabaseManager

    db = current_app.config['db']
    question = db.get_question(question_id)

    if not question:
        return jsonify({'error': 'Question not found'}), 404

    status = question.get('processing_status', {}).get('status')
    if status != 'lean_converted':
        return jsonify({'error': f'Question must be in lean_converted status (current: {status})'}), 400

    try:
        verifier = LeanVerifier(
            db_manager=db,
            kimina_url=current_app.config['settings'].kimina_url
        )

        result = verifier.verify_question(question_id)

        return jsonify(result)

    except ConnectionError as e:
        return jsonify({
            'error': 'Connection error',
            'message': str(e),
            'verification_status': 'connection_error'
        }), 503
    except Exception as e:
        return jsonify({
            'error': str(e),
            'verification_status': 'error'
        }), 500


@verification_bp.route('/verify-all', methods=['POST', 'OPTIONS'])
def verify_all_lean():
    """Verify all questions with Lean code."""
    if request.method == 'OPTIONS':
        return '', 200

    from ...processing import LeanVerifier, TaskManager

    db = current_app.config['db']
    data = request.get_json() or {}
    limit = data.get('limit', 100)
    async_mode = data.get('async', False)

    # Get all questions with lean_converted status
    questions_data = db.list_questions(
        status='lean_converted',
        limit=limit
    )
    questions = questions_data.get('questions', [])

    if not questions:
        return jsonify({'message': 'No questions ready for verification'})

    # Check if there's an active task
    task_manager = TaskManager()
    active_task = task_manager.get_active_task('verification')
    if active_task:
        return jsonify({
            'error': 'Verification already in progress',
            'task_id': active_task.task_id,
            'progress': active_task.get_progress()
        }), 400

    # Create task
    task = task_manager.create_task('verification', len(questions))

    # Import verifier
    try:
        verifier = LeanVerifier(
            db_manager=db,
            kimina_url=current_app.config['settings'].kimina_url
        )

        def process_questions():
            for q in questions:
                # Check if task is paused
                task.wait_if_paused()

                # Check if task is stopped
                if task.is_stopped():
                    break

                # Use question_id (internal_id) instead of id
                question_internal_id = q['question_id']
                task.current_question_id = question_internal_id
                try:
                    verifier.verify_question(question_internal_id)
                    task.increment_progress(success=True)
                except Exception as e:
                    print(f"Error verifying question {question_internal_id}: {e}")
                    task.increment_progress(success=False)

            # Mark task as completed
            task.status = 'completed'
            task.completed_at = task.completed_at or __import__('datetime').datetime.now()
            task.current_question_id = None

        if async_mode:
            thread = threading.Thread(target=process_questions, daemon=True)
            thread.start()

            return jsonify({
                'message': f'Verification task started for {len(questions)} questions',
                'task_id': task.task_id,
                'progress': task.get_progress()
            })
        else:
            # Synchronous verification
            process_questions()
            return jsonify({
                'message': f'Verification completed for {len(questions)} questions',
                'task_id': task.task_id,
                'progress': task.get_progress()
            })

    except Exception as e:
        task.status = 'error'
        task.error_message = str(e)
        return jsonify({'error': str(e)}), 500


@verification_bp.route('/status/<int:question_id>', methods=['GET', 'OPTIONS'])
def get_verification_status(question_id: int):
    """Get verification status for a question."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    question = db.get_question(question_id)

    if not question:
        return jsonify({'error': 'Question not found'}), 404

    ps = question.get('processing_status', {})

    return jsonify({
        'verification_status': ps.get('verification_status', 'not_verified'),
        'verification_has_errors': ps.get('verification_has_errors', False),
        'verification_has_warnings': ps.get('verification_has_warnings', False),
        'verification_messages': ps.get('verification_messages', []),
        'verification_error': ps.get('verification_error'),
        'verification_time': ps.get('verification_time'),
        'verification_completed_at': ps.get('verification_completed_at')
    })
