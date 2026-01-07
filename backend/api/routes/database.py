"""
Database viewing API endpoints.
"""
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func

database_bp = Blueprint('database', __name__)


@database_bp.route('/clear', methods=['POST', 'OPTIONS'])
def clear_data():
    """Clear data by stage or completely."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    stage = data.get('stage')  # 'lean', 'verification', 'preprocess', 'failed', 'raw', or 'all'
    versions = data.get('versions', [])  # For preprocess: list of versions to clear, or ['all'] for all

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

            # Also clear lean_conversion_results
            from backend.database.schema import LeanConversionResult
            lc_count = session.query(LeanConversionResult).delete()
            session.commit()
            return jsonify({'message': f'Cleared lean code from {count} questions and {lc_count} conversion results'})

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

            # Also clear verification status in lean_conversion_results
            from backend.database.schema import LeanConversionResult
            lc_count = session.query(LeanConversionResult).filter(
                LeanConversionResult.verification_status.isnot(None)
            ).update({
                LeanConversionResult.verification_status: None,
                LeanConversionResult.verification_has_errors: None,
                LeanConversionResult.verification_has_warnings: None,
                LeanConversionResult.verification_messages: None,
                LeanConversionResult.verification_time: None,
                # Question verification
                LeanConversionResult.question_verification_status: None,
                LeanConversionResult.question_verification_messages: None,
                LeanConversionResult.question_verification_time: None,
                # Answer verification
                LeanConversionResult.answer_verification_status: None,
                LeanConversionResult.answer_verification_messages: None,
                LeanConversionResult.answer_verification_time: None
            }, synchronize_session=False)
            session.commit()
            return jsonify({'message': f'Cleared verification status from {count} questions and {lc_count} conversion results'})

        elif stage == 'preprocess':
            # Clear preprocessed data by version(s)
            if not versions or len(versions) == 0:
                return jsonify({'error': 'No versions specified'}), 400

            # Build query
            if 'all' in versions:
                # Clear all preprocessed data
                ps_query = session.query(ProcessingStatus).filter(
                    ProcessingStatus.status.in_(['preprocessed', 'lean_converted', 'failed', 'cant_convert'])
                )
                count = ps_query.count()
                ps_query.update({
                    ProcessingStatus.status: 'raw',
                    ProcessingStatus.preprocessed_body: None,
                    ProcessingStatus.preprocessed_answer: None,
                    ProcessingStatus.correction_notes: None,
                    ProcessingStatus.theorem_name: None,
                    ProcessingStatus.formalization_value: None,
                    ProcessingStatus.preprocessing_version: None,
                    ProcessingStatus.lean_code: None,
                    ProcessingStatus.lean_error: None,
                    ProcessingStatus.current_stage: None,
                    ProcessingStatus.verification_status: None,
                    ProcessingStatus.verification_has_errors: None,
                    ProcessingStatus.verification_has_warnings: None,
                    ProcessingStatus.verification_messages: None,
                    ProcessingStatus.verification_error: None,
                    ProcessingStatus.verification_time: None,
                    ProcessingStatus.verification_completed_at: None,
                    ProcessingStatus.processing_started_at: None,
                    ProcessingStatus.processing_completed_at: None
                }, synchronize_session=False)
                session.commit()
                return jsonify({'message': f'Cleared preprocessed data from {count} questions'})
            else:
                # Clear specific versions
                ps_query = session.query(ProcessingStatus).filter(
                    ProcessingStatus.preprocessing_version.in_(versions)
                )
                count = ps_query.count()
                ps_query.update({
                    ProcessingStatus.status: 'raw',
                    ProcessingStatus.preprocessed_body: None,
                    ProcessingStatus.preprocessed_answer: None,
                    ProcessingStatus.correction_notes: None,
                    ProcessingStatus.theorem_name: None,
                    ProcessingStatus.formalization_value: None,
                    ProcessingStatus.preprocessing_version: None,
                    ProcessingStatus.lean_code: None,
                    ProcessingStatus.lean_error: None,
                    ProcessingStatus.current_stage: None,
                    ProcessingStatus.verification_status: None,
                    ProcessingStatus.verification_has_errors: None,
                    ProcessingStatus.verification_has_warnings: None,
                    ProcessingStatus.verification_messages: None,
                    ProcessingStatus.verification_error: None,
                    ProcessingStatus.verification_time: None,
                    ProcessingStatus.verification_completed_at: None,
                    ProcessingStatus.processing_started_at: None,
                    ProcessingStatus.processing_completed_at: None
                }, synchronize_session=False)
                session.commit()
                return jsonify({'message': f'Cleared preprocessed data from {count} questions (versions: {", ".join(versions)})'})

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

            # Also clear lean_conversion_results for this question
            from backend.database.schema import LeanConversionResult
            lc_count = session.query(LeanConversionResult).filter(
                LeanConversionResult.question_id == question_id
            ).delete()
            session.commit()
            return jsonify({'message': f'Cleared lean code and {lc_count} conversion results'})

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

            # Also clear lean_conversion_results for this question
            from backend.database.schema import LeanConversionResult
            lc_count = session.query(LeanConversionResult).filter(
                LeanConversionResult.question_id == question_id
            ).delete()
            session.commit()
            return jsonify({'message': f'Cleared preprocessed data and {lc_count} conversion results'})

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

    # Debug: print theorem_name
    print(f"[DEBUG] Question {question_id} theorem_name: {(question.get('processing_status') or {}).get('theorem_name')}")

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


@database_bp.route('/export/verified-lean', methods=['GET', 'OPTIONS'])
def export_verified_lean():
    """Export verified Lean data as JSONL."""
    if request.method == 'OPTIONS':
        return '', 200

    from flask import Response
    import json
    from datetime import datetime

    db = current_app.config['db']

    try:
        # Get all verified Lean data
        data = db.export_verified_lean_data()

        # Convert to JSONL (JSON Lines format)
        jsonl_lines = [json.dumps(item, ensure_ascii=False) for item in data]
        jsonl_content = '\n'.join(jsonl_lines) + '\n'

        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'lean_verified_{timestamp}.jsonl'

        # Return as file download
        return Response(
            jsonl_content,
            mimetype='application/jsonl',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@database_bp.route('/questions/<int:question_id>/lean-conversions', methods=['GET', 'OPTIONS'])
def get_lean_conversions(question_id: int):
    """Get all Lean conversion results for a question."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']

    # Verify question exists
    question = db.get_question(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    results = db.get_lean_conversion_results(question_id)
    return jsonify({'results': results})


@database_bp.route('/lean-conversions/<int:result_id>', methods=['PUT', 'OPTIONS'])
def update_lean_conversion(result_id: int):
    """Update a Lean conversion result (mainly for verification)."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    db = current_app.config['db']

    try:
        success = db.update_lean_verification(
            result_id=result_id,
            verification_status=data.get('verification_status'),
            has_errors=data.get('verification_has_errors', False),
            has_warnings=data.get('verification_has_warnings', False),
            messages=data.get('verification_messages'),
            verification_time=data.get('verification_time')
        )

        if success:
            return jsonify({'message': 'Lean conversion result updated successfully'})
        else:
            return jsonify({'error': 'Result not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@database_bp.route('/lean-conversions/converters', methods=['GET', 'OPTIONS'])
def get_converters():
    """Get list of all available converters."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']

    try:
        converters = db.get_available_converters()
        return jsonify({'converters': converters})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@database_bp.route('/lean-conversions/clear', methods=['POST', 'OPTIONS'])
def clear_lean_conversions():
    """Clear Lean conversion results for specific converters."""
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    converters = data.get('converters', [])  # List of converter names, or ['all'] for all

    db = current_app.config['db']
    session = db.get_session()

    try:
        from backend.database.schema import LeanConversionResult, ProcessingStatus

        if not converters or len(converters) == 0:
            return jsonify({'error': 'No converters specified'}), 400

        # Count before deletion
        if 'all' in converters:
            # Clear all conversion results
            conversion_count = session.query(LeanConversionResult).count()
            session.query(LeanConversionResult).delete()

            # Also clear legacy lean_code fields in processing_status
            legacy_count = session.query(ProcessingStatus).filter(
                (ProcessingStatus.lean_code.isnot(None)) |
                (ProcessingStatus.question_lean_code.isnot(None)) |
                (ProcessingStatus.answer_lean_code.isnot(None))
            ).count()

            session.query(ProcessingStatus).filter(
                (ProcessingStatus.lean_code.isnot(None)) |
                (ProcessingStatus.question_lean_code.isnot(None)) |
                (ProcessingStatus.answer_lean_code.isnot(None))
            ).update({
                ProcessingStatus.lean_code: None,
                ProcessingStatus.question_lean_code: None,
                ProcessingStatus.answer_lean_code: None,
                ProcessingStatus.lean_error: None,
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
            total_count = conversion_count + legacy_count
            return jsonify({'message': f'Cleared all {total_count} Lean conversion results ({conversion_count} from converters, {legacy_count} legacy)'})

        elif 'legacy' in converters:
            # Clear only legacy lean_code fields in processing_status
            legacy_count = session.query(ProcessingStatus).filter(
                (ProcessingStatus.lean_code.isnot(None)) |
                (ProcessingStatus.question_lean_code.isnot(None)) |
                (ProcessingStatus.answer_lean_code.isnot(None))
            ).count()

            session.query(ProcessingStatus).filter(
                (ProcessingStatus.lean_code.isnot(None)) |
                (ProcessingStatus.question_lean_code.isnot(None)) |
                (ProcessingStatus.answer_lean_code.isnot(None))
            ).update({
                ProcessingStatus.lean_code: None,
                ProcessingStatus.question_lean_code: None,
                ProcessingStatus.answer_lean_code: None,
                ProcessingStatus.lean_error: None,
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
            return jsonify({'message': f'Cleared {legacy_count} legacy Lean conversion results'})

        else:
            # Clear specific converters (excluding legacy)
            count = session.query(LeanConversionResult).filter(
                LeanConversionResult.converter_name.in_(converters)
            ).count()

            session.query(LeanConversionResult).filter(
                LeanConversionResult.converter_name.in_(converters)
            ).delete()

            session.commit()
            return jsonify({'message': f'Cleared {count} Lean conversion results from {len(converters)} converter(s)'})

    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@database_bp.route('/preprocessing-versions', methods=['GET', 'OPTIONS'])
def get_preprocessing_versions():
    """Get list of all available preprocessing versions."""
    if request.method == 'OPTIONS':
        return '', 200

    db = current_app.config['db']
    session = db.get_session()

    try:
        from backend.database.schema import ProcessingStatus

        # Get all distinct preprocessing versions with their counts
        results = session.query(
            ProcessingStatus.preprocessing_version,
            func.count(ProcessingStatus.id).label('count')
        ).filter(
            ProcessingStatus.preprocessing_version.isnot(None)
        ).group_by(
            ProcessingStatus.preprocessing_version
        ).all()

        versions = [
            {'version': r.preprocessing_version, 'count': r.count}
            for r in results
        ]

        # Sort by version (newest first)
        versions.sort(key=lambda x: x['version'], reverse=True)

        return jsonify({'versions': versions})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
