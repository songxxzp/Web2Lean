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
    """Verify all Lean conversion results that haven't been verified yet."""
    if request.method == 'OPTIONS':
        return '', 200

    from ...processing import TaskManager
    from ...database import DatabaseManager, LeanConversionResult

    db = current_app.config['db']
    data = request.get_json() or {}
    limit = data.get('limit', 100)
    async_mode = data.get('async', False)

    # Get all unverified lean conversion results
    session = db.get_session()
    try:
        query = session.query(LeanConversionResult).filter(
            LeanConversionResult.verification_status == None
        ).order_by(LeanConversionResult.id)

        if limit > 0:
            query = query.limit(limit)

        results = query.all()
        conversion_results = [{'id': r.id, 'question_id': r.question_id, 'converter_name': r.converter_name} for r in results]
    finally:
        session.close()

    if not conversion_results:
        return jsonify({'message': 'No Lean conversion results ready for verification'})

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
    task = task_manager.create_task('verification', len(conversion_results))

    # Import verifier
    try:
        from ...processing.lean_verifier import LeanVerifier

        verifier = LeanVerifier(
            db_manager=db,
            kimina_url=current_app.config['settings'].kimina_url
        )

        def process_results():
            for result_info in conversion_results:
                # Check if task is paused
                task.wait_if_paused()

                # Check if task is stopped
                if task.is_stopped():
                    break

                result_id = result_info['id']
                task.current_question_id = result_info['question_id']
                try:
                    verifier.verify_conversion_result(result_id)
                    task.increment_progress(success=True)
                except Exception as e:
                    print(f"Error verifying conversion result {result_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    task.increment_progress(success=False)

            # Mark task as completed
            task.status = 'completed'
            task.completed_at = task.completed_at or __import__('datetime').datetime.now()
            task.current_question_id = None

        if async_mode:
            thread = threading.Thread(target=process_results, daemon=True)
            thread.start()

            return jsonify({
                'message': f'Verification task started for {len(conversion_results)} conversion results',
                'task_id': task.task_id,
                'progress': task.get_progress()
            })
        else:
            # Synchronous verification
            process_results()
            return jsonify({
                'message': f'Verification completed for {len(conversion_results)} conversion results',
                'task_id': task.task_id,
                'progress': task.get_progress()
            })

    except Exception as e:
        task.status = 'error'
        task.error_message = str(e)
        import traceback
        traceback.print_exc()
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
