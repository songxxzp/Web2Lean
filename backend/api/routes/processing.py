"""
Processing API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
import threading

processing_bp = Blueprint('processing', __name__)


@processing_bp.route('/start-lean', methods=['POST', 'OPTIONS'])
def start_lean_conversion():
    """Start Lean conversion for pending questions."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    limit = data.get('limit', 10)
    site_id = data.get('site_id')

    db = current_app.config['db']

    # Get questions ready for conversion (preprocessed but not yet converted)
    questions = db.get_questions_by_status('preprocessed', limit=limit)

    if not questions:
        return jsonify({'message': 'No questions ready for Lean conversion'})

    # Import processor
    try:
        from ...processing import LeanConverter

        converter = LeanConverter(
            db_manager=db,
            vllm_base_url=current_app.config['settings'].vllm_base_url,
            model_path=current_app.config['settings'].vllm_model_path
        )

        def process_questions():
            for q in questions:
                if site_id and q['site_id'] != site_id:
                    continue
                try:
                    converter.convert_question(q['id'])
                except Exception as e:
                    print(f"Error converting question {q['id']}: {e}")

        thread = threading.Thread(target=process_questions, daemon=True)
        thread.start()

        return jsonify({
            'message': f'Started Lean conversion for {len(questions)} questions',
            'count': len(questions)
        })

    except Exception as e:
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

    # Get raw questions
    questions = db.get_questions_by_status('raw', limit=limit)

    if not questions:
        return jsonify({'message': 'No questions to preprocess'})

    try:
        from ...processing import LLMProcessor

        processor = LLMProcessor(
            db_manager=db,
            api_key=current_app.config['settings'].zhipu_api_key
        )

        def process_questions():
            for q in questions:
                if site_id and q['site_id'] != site_id:
                    continue
                try:
                    processor.process_question(q['id'])
                except Exception as e:
                    print(f"Error preprocessing question {q['id']}: {e}")

        thread = threading.Thread(target=process_questions, daemon=True)
        thread.start()

        return jsonify({
            'message': f'Started preprocessing for {len(questions)} questions',
            'count': len(questions)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
