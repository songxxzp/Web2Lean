"""
Processing API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
import threading
import time

processing_bp = Blueprint('processing', __name__)


@processing_bp.route('/start-lean', methods=['POST', 'OPTIONS'])
def start_lean_conversion():
    """Start Lean conversion for pending questions."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    limit = data.get('limit', 10)
    site_id = data.get('site_id')
    converter_type = data.get('converter', 'kimina')  # 'kimina' or 'llm'

    db = current_app.config['db']

    # Check if there's an active task for this specific converter type
    from ...processing import TaskManager
    task_manager = TaskManager()
    task_type = f'lean_conversion_{converter_type}'  # Unique task type per converter
    active_task = task_manager.get_active_task(task_type)
    if active_task:
        return jsonify({
            'error': f'{converter_type.upper()} Lean conversion already in progress',
            'task_id': active_task.task_id,
            'progress': active_task.get_progress()
        }), 400

    # Map converter type to converter name
    converter_name_map = {
        'kimina': 'Kimina-Legacy',
        'llm': 'GLM-LLM-Agent'
    }
    converter_name = converter_name_map.get(converter_type, 'Kimina-Legacy')

    # Get questions ready for conversion (preprocessed but not yet converted by this converter)
    questions = db.get_questions_not_converted_by(converter_name, limit=limit)

    if not questions:
        return jsonify({'message': f'No questions ready for {converter_name} conversion'})

    # Create task with converter-specific type
    task = task_manager.create_task(task_type, len(questions))

    # Import and instantiate the appropriate converter
    try:
        settings = current_app.config['settings']

        # Choose converter based on request parameter
        if converter_type == 'llm':
            # Use LLM-based converter
            from ...processing import LLMLeanConverter

            converter = LLMLeanConverter(
                db_manager=db,
                api_key=settings.zhipu_api_key,
                model=settings.glm_lean_model,
                kimina_url=settings.kimina_url,
                max_iterations=settings.lean_max_iterations,
                temperature=0.2,
                max_tokens=4096,
                converter_name=converter_name  # Pass converter name
            )
        else:
            # Use local Kimina converter
            from ...processing import LeanConverter

            converter = LeanConverter(
                db_manager=db,
                vllm_base_url=settings.vllm_base_url,
                model_path=settings.vllm_model_path,
                converter_name=converter_name  # Pass converter name
            )

        def process_questions():
            for q in questions:
                # Check if task is paused
                task.wait_if_paused()

                # Check if task is stopped
                if task.is_stopped():
                    break

                if site_id and q['site_id'] != site_id:
                    continue

                task.current_question_id = q['id']
                try:
                    converter.convert_question(q['id'])
                    task.increment_progress(success=True)
                except Exception as e:
                    print(f"Error converting question {q['id']}: {e}")
                    task.increment_progress(success=False)

            # Mark task as completed
            task.status = 'completed'
            task.completed_at = task.completed_at or __import__('datetime').datetime.now()
            task.current_question_id = None

        thread = threading.Thread(target=process_questions, daemon=True)
        thread.start()

        return jsonify({
            'message': f'Started Lean conversion for {len(questions)} questions',
            'task_id': task.task_id,
            'count': len(questions),
            'progress': task.get_progress()
        })

    except Exception as e:
        task.status = 'error'
        task.error_message = str(e)
        return jsonify({'error': str(e)}), 500


@processing_bp.route('/preprocess', methods=['POST', 'OPTIONS'])
def start_preprocessing():
    """Start LLM preprocessing for raw questions."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    limit = data.get('limit', 10)
    site_id = data.get('site_id')

    db = current_app.config['db']

    # Check if there's an active task
    from ...processing import TaskManager
    task_manager = TaskManager()
    active_task = task_manager.get_active_task('preprocessing')
    if active_task:
        return jsonify({
            'error': 'Preprocessing already in progress',
            'task_id': active_task.task_id,
            'progress': active_task.get_progress()
        }), 400

    # Get raw questions
    questions = db.get_questions_by_status('raw', limit=limit)

    if not questions:
        return jsonify({'message': 'No questions to preprocess'})

    # Create task
    task = task_manager.create_task('preprocessing', len(questions))

    try:
        from ...processing import LLMProcessor

        settings = current_app.config['settings']
        processor = LLMProcessor(
            db_manager=db,
            api_key=settings.zhipu_api_key,
            text_model=settings.glm_text_model,
            vision_model=settings.glm_vision_model,
            max_length=settings.preprocessing_max_length
        )

        concurrency = settings.preprocessing_concurrency

        def process_questions():
            # Process questions in batches with concurrency
            batch_size = concurrency * 2  # Process in batches to avoid overwhelming the system

            try:
                for batch_start in range(0, len(questions), batch_size):
                    # Check if task is paused
                    task.wait_if_paused()

                    # Check if task is stopped
                    if task.is_stopped():
                        break

                    batch = questions[batch_start:batch_start + batch_size]

                    # Filter by site_id if specified
                    if site_id:
                        batch = [q for q in batch if q['site_id'] == site_id]

                    if not batch:
                        continue

                    # Extract question IDs
                    question_ids = [q['id'] for q in batch]

                    # Process batch concurrently
                    results = processor.process_questions_batch(
                        question_ids,
                        concurrency=concurrency
                    )

                    # Update task progress
                    for result in results:
                        success = result.get('success', False)
                        task.increment_progress(success=success)

                    # Add delay between batches to avoid rate limiting
                    if batch_start + batch_size < len(questions):
                        time.sleep(3)  # Wait 3 seconds between batches

                # Mark task as completed
                task.status = 'completed'
                task.completed_at = task.completed_at or __import__('datetime').datetime.now()
                task.current_question_id = None

            finally:
                # Always clean up any stuck preprocessing status when task ends
                try:
                    db.cleanup_stuck_preprocessing()
                except Exception as e:
                    logging = __import__('logging').getLogger(__name__)
                    logging.error(f'Error cleaning up stuck preprocessing after task completion: {e}')

        thread = threading.Thread(target=process_questions, daemon=True)
        thread.start()

        return jsonify({
            'message': f'Started preprocessing for {len(questions)} questions with concurrency={concurrency}',
            'task_id': task.task_id,
            'count': len(questions),
            'concurrency': concurrency,
            'progress': task.get_progress()
        })

    except Exception as e:
        task.status = 'error'
        task.error_message = str(e)
        return jsonify({'error': str(e)}), 500


@processing_bp.route('/task/<task_type>/progress', methods=['GET', 'OPTIONS'])
def get_task_progress(task_type: str):
    """Get progress of current task of given type."""
    if request.method == 'OPTIONS':
        return '', 200

    from ...processing import TaskManager
    task_manager = TaskManager()

    task = task_manager.get_active_task(task_type)
    if not task:
        return jsonify({'active': False})

    return jsonify({
        'active': True,
        'progress': task.get_progress()
    })


@processing_bp.route('/task/<task_id>/pause', methods=['POST', 'OPTIONS'])
def pause_task(task_id: str):
    """Pause a running task."""
    if request.method == 'OPTIONS':
        return '', 200

    from ...processing import TaskManager
    task_manager = TaskManager()

    if task_manager.pause_task(task_id):
        return jsonify({'message': 'Task paused'})

    return jsonify({'error': 'Task not found'}), 404


@processing_bp.route('/task/<task_id>/resume', methods=['POST', 'OPTIONS'])
def resume_task(task_id: str):
    """Resume a paused task."""
    if request.method == 'OPTIONS':
        return '', 200

    from ...processing import TaskManager
    task_manager = TaskManager()

    if task_manager.resume_task(task_id):
        return jsonify({'message': 'Task resumed'})

    return jsonify({'error': 'Task not found'}), 404


@processing_bp.route('/task/<task_id>/stop', methods=['POST', 'OPTIONS'])
def stop_task(task_id: str):
    """Stop a running or paused task."""
    if request.method == 'OPTIONS':
        return '', 200

    from ...processing import TaskManager
    task_manager = TaskManager()

    if task_manager.stop_task(task_id):
        # Clean up any questions stuck in preprocessing status
        db = current_app.config['db']
        try:
            count = db.cleanup_stuck_preprocessing()
            if count > 0:
                return jsonify({'message': f'Task stopped and cleaned up {count} stuck questions'})
        except Exception as e:
            # Log error but don't fail the stop operation
            logging = __import__('logging').getLogger(__name__)
            logging.error(f'Error cleaning up stuck preprocessing after stopping task: {e}')

        return jsonify({'message': 'Task stopped'})

    return jsonify({'error': 'Task not found'}), 404


@processing_bp.route('/status/<int:question_id>', methods=['GET', 'OPTIONS'])
def get_processing_status(question_id: int):
    """Get processing status for a specific question."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    question = db.get_question(question_id)

    if not question:
        return jsonify({'error': 'Question not found'}), 404

    return jsonify(question.get('processing_status', {}))


@processing_bp.route('/retry/<int:question_id>', methods=['POST', 'OPTIONS'])
def retry_processing(question_id: int):
    """Retry failed processing for a question."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    question = db.get_question(question_id)

    if not question:
        return jsonify({'error': 'Question not found'}), 404

    status = question.get('processing_status', {})
    if status.get('status') != 'failed':
        return jsonify({'error': 'Question is not in failed state'}), 400

    # Reset to raw for retry
    db.update_processing_status(
        question_id,
        status='raw',
        current_stage=None,
        lean_error=None
    )

    return jsonify({'message': 'Question reset to raw status for retry'})
