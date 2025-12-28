#!/usr/bin/env python3
"""
Interactive CLI tool for testing preprocess functionality.

Usage:
    python test_preprocess_cli.py [options]

Options:
    --write, -w    Enable write mode (save results to database)
                   Default: read-only mode (results NOT saved)

Examples:
    # Read-only mode (default)
    python test_preprocess_cli.py

    # Write mode (save results to database)
    python test_preprocess_cli.py --write
    python test_preprocess_cli.py -w
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_question_from_db(db, question_id: int) -> dict:
    """Get question details from database."""
    session = db.get_session()
    try:
        from backend.database.schema import Question, Answer

        question = session.query(Question).filter(Question.id == question_id).first()
        if not question:
            return None

        # Get answers
        answers = session.query(Answer).filter(Answer.question_id == question_id).all()

        result = {
            'id': question.id,
            'title': question.title,
            'body': question.body,
            'site_id': question.site_id,
            'score': question.score,
            'answer_count': question.answer_count,
            'answers': [
                {
                    'id': a.id,
                    'body': a.body,
                    'score': a.score,
                    'is_accepted': a.is_accepted
                }
                for a in answers
            ]
        }
        return result
    finally:
        session.close()


def format_json_output(data: dict, indent: int = 0) -> str:
    """Format JSON output for display."""
    import json
    return json.dumps(data, indent=2, ensure_ascii=False)


def display_question_info(question: dict):
    """Display question information."""
    print("\n" + "=" * 80)
    print(f"QUESTION ID: {question['id']}")
    print(f"Title: {question['title'][:100]}...")
    print(f"Body: {question['body'][:200]}...")
    print(f"Score: {question['score']}")
    print(f"Answers: {question['answer_count']}")
    print("=" * 80)


def display_llm_response(llm_result: dict):
    """Display LLM API response."""
    print("\n" + "-" * 80)
    print("📥 LLM API RESPONSE")
    print("-" * 80)

    # Format and display the result
    print(format_json_output(llm_result))

    # Show summary
    print("\n📊 SUMMARY:")
    if 'is_valid_question' in llm_result:
        status = "✅ VALID" if llm_result.get('is_valid_question') else "❌ INVALID"
        print(f"  Question: {status}")

    if 'is_valid_answer' in llm_result:
        status = "✅ VALID" if llm_result.get('is_valid_answer') else "❌ INVALID"
        print(f"  Answer: {status}")

    if 'has_errors' in llm_result and llm_result.get('has_errors'):
        print(f"  Errors: {llm_result.get('errors', [])}")

    if 'worth_formalizing' in llm_result:
        status = "✅ YES" if llm_result.get('worth_formalizing') else "❌ NO"
        print(f"  Worth Formalizing: {status}")

    if 'formalization_value' in llm_result:
        value = llm_result.get('formalization_value', 'unknown')
        emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(value, "⚪")
        print(f"  Formalization Value: {emoji} {value.upper()}")

    if 'corrected_question' in llm_result:
        cq = llm_result.get('corrected_question', '')
        print(f"\n  Corrected Question Preview:")
        print(f"    {cq[:150]}{'...' if len(cq) > 150 else ''}")

    if 'corrected_answer' in llm_result and llm_result.get('corrected_answer'):
        ca = llm_result.get('corrected_answer', '')
        print(f"\n  Corrected Answer Preview:")
        print(f"    {ca[:150]}{'...' if len(ca) > 150 else ''}")

    print("-" * 80)


def display_raw_api_response(api_response: dict):
    """Display raw LLM API response with all metadata.

    Args:
        api_response: Raw response from chat_completion API
    """
    print("\n" + "=" * 80)
    print("🌐 RAW LLM API RESPONSE")
    print("=" * 80)

    # Display model info
    print(f"\n📋 Model: {api_response.get('model', 'unknown')}")

    # Display usage statistics
    usage = api_response.get('usage', {})
    if usage:
        print("\n📊 Token Usage:")
        print(f"  Prompt Tokens: {usage.get('prompt_tokens', 0):,}")
        print(f"  Completion Tokens: {usage.get('completion_tokens', 0):,}")
        print(f"  Total Tokens: {usage.get('total_tokens', 0):,}")

    # Display finish reason
    choices = api_response.get('choices', [])
    if choices and len(choices) > 0:
        choice = choices[0]
        finish_reason = choice.get('finish_reason', 'unknown')
        print(f"\n🏁 Finish Reason: {finish_reason}")

        # Display role
        message = choice.get('message', {})
        role = message.get('role', 'assistant')
        print(f"👤 Role: {role}")

    # Display raw content
    print("\n📝 Raw Content:")
    content = choices[0].get('message', {}).get('content', '') if choices else ''
    print(content)

    print("\n" + "=" * 80)


def parse_llm_response(api_response: dict) -> dict:
    """Parse LLM response from raw API response.

    Args:
        api_response: Raw response from chat_completion API

    Returns:
        Parsed JSON dict
    """
    from backend.utils.llm_client import parse_json_from_llm_response

    content = api_response.get('choices', [{}])[0].get('message', {}).get('content', '')

    try:
        return parse_json_from_llm_response(content)
    except Exception as e:
        # Return error result
        return {
            "is_valid_question": True,
            "is_valid_answer": True,
            "has_errors": False,
            "errors": [],
            "corrected_question": "",
            "corrected_answer": "",
            "correction_notes": f"JSON parsing failed: {str(e)}",
            "worth_formalizing": True,
            "formalization_value": "medium"
        }


def display_processing_result(result: dict):
    """Display final processing result."""
    print("\n" + "-" * 80)
    print("📤 BACKEND PROCESSING RESULT")
    print("-" * 80)

    print(f"Status: {result.get('status')}")

    if result.get('status') == 'preprocessed':
        print("\n✅ Preprocessing completed successfully!")

        if result.get('preprocessed_body'):
            print(f"\nPreprocessed Body:")
            print(f"  {result['preprocessed_body'][:200]}...")

        if result.get('preprocessed_answer'):
            print(f"\nPreprocessed Answer:")
            print(f"  {result['preprocessed_answer'][:200]}...")

        if result.get('correction_notes'):
            print(f"\nCorrection Notes:")
            print(f"  {result['correction_notes']}")

        if result.get('ocr_count'):
            print(f"\nOCR Processed: {result['ocr_count']} images")

        if 'has_answer' in result:
            has_ans = "✅ YES" if result['has_answer'] else "❌ NO"
            print(f"Has Answer: {has_ans}")

    elif result.get('status') == 'cant_convert':
        print("\n❌ Question marked as 'cant_convert'")
        reason = result.get('reason') or result.get('correction_notes', 'Unknown reason')
        print(f"Reason: {reason}")

    elif result.get('status') == 'failed':
        print("\n❌ Processing failed")
        if result.get('error'):
            print(f"Error: {result['error']}")

    print("-" * 80)


def test_preprocess(question_id: int, write_to_db: bool = False):
    """Test preprocessing for a question.

    Args:
        question_id: Question ID to test
        write_to_db: If True, write results back to database. Default: False (read-only)
    """
    from backend.config import get_settings
    from backend.database import DatabaseManager
    from backend.utils import ZhipuClient

    print(f"\n🚀 Starting preprocess test for question ID: {question_id}")
    if write_to_db:
        print("⚠️  WRITE MODE ENABLED - Results will be saved to database")
    else:
        print("📖 READ-ONLY MODE - Results will NOT be saved to database")

    # Initialize
    settings = get_settings()
    db = DatabaseManager(settings.db_path)
    client = ZhipuClient(api_key=settings.zhipu_api_key)

    # Get question info
    print("\n📋 Fetching question from database...")
    question = get_question_from_db(db, question_id)
    if not question:
        print(f"❌ Question {question_id} not found in database!")
        return

    display_question_info(question)

    # Get current processing status
    current_status = db.get_question(question_id).get('processing_status', {})
    if current_status.get('status') in ['preprocessed', 'lean_converted']:
        print(f"\n⚠️  Question is already '{current_status.get('status')}'")
        choice = input("Do you want to reprocess? (y/N): ").strip().lower()
        if choice != 'y':
            print("Aborted.")
            return

    # Run preprocessing
    print("\n🔄 Running LLM preprocessing...")
    print("⏳ Please wait, this may take 10-30 seconds...\n")

    try:
        # Combine title and body
        question_text = f"{question['title']}\n\n{question['body']}"
        answers = question.get('answers', [])

        # Prepare prompt based on answer count
        from backend.utils.prompts import (
            QUESTION_ONLY_PROMPT,
            QUESTION_WITH_ANSWER_PROMPT,
            QUESTION_WITH_MULTIPLE_ANSWERS_PROMPT,
            format_answers_text
        )

        user_prompt = None
        if not answers:
            print("📝 Processing: Question only (no answers)")
            user_prompt = QUESTION_ONLY_PROMPT.format(question=question_text)
        elif len(answers) == 1:
            print("📝 Processing: Question + Single Answer")
            user_prompt = QUESTION_WITH_ANSWER_PROMPT.format(
                question=question_text,
                answer=answers[0]['body']
            )
        else:
            print(f"📝 Processing: Question + {len(answers)} Answers")
            answers_text = format_answers_text(answers)
            user_prompt = QUESTION_WITH_MULTIPLE_ANSWERS_PROMPT.format(
                question=question_text,
                answers_text=answers_text
            )

        # Call LLM API directly to get raw response
        messages = [{"role": "user", "content": user_prompt}]

        print("🌐 Calling LLM API...")
        raw_api_response = client.chat_completion(
            messages=messages,
            model=settings.glm_text_model,
            temperature=0.2,
            max_tokens=16000,
            response_format={"type": "json_object"}
        )

        # Display raw API response
        display_raw_api_response(raw_api_response)

        # Parse the result from response
        llm_result = parse_llm_response(raw_api_response)

        # Build processing result (same format as process_question would return)
        result = build_processing_result(llm_result, question)

        # Display final result
        display_processing_result(result)

        # Optionally write to database
        if write_to_db:
            print("\n💾 Writing results to database...")
            write_result_to_db(db, question_id, llm_result, question)
            print("✅ Results saved to database")
        else:
            print("\n📖 READ-ONLY MODE: Results NOT saved to database")
            print("   Use --write flag to enable saving")

    except Exception as e:
        print(f"\n❌ Error during preprocessing:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        print("\n📋 Traceback:")
        traceback.print_exc()


def build_processing_result(llm_result: dict, question: dict) -> dict:
    """Build processing result dict from LLM result.

    Args:
        llm_result: Result from LLM API
        question: Original question data

    Returns:
        Processing result dict
    """
    # Check if question is valid
    if not llm_result.get('is_valid_question'):
        return {
            'success': False,
            'status': 'cant_convert',
            'correction_notes': llm_result.get('correction_notes', 'Question is not valid')
        }

    # Build result based on LLM response
    result = {
        'success': True,
        'status': 'preprocessed',
        'preprocessed_body': llm_result.get('corrected_question'),
        'preprocessed_answer': llm_result.get('corrected_answer'),
        'correction_notes': llm_result.get('correction_notes', '')
    }

    # Check if we should include the answer
    if 'is_valid_answer' in llm_result:
        if not llm_result.get('is_valid_answer'):
            result['preprocessed_answer'] = None
            result['correction_notes'] += " [No valid answer found]"

    return result


def write_result_to_db(db, question_id: int, llm_result: dict, question: dict):
    """Write preprocessing result to database.

    Args:
        db: DatabaseManager instance
        question_id: Question ID
        llm_result: Result from LLM API
        question: Original question data
    """
    from datetime import datetime

    # Check if question is valid
    if not llm_result.get('is_valid_question'):
        # Mark as cant_convert
        db.update_processing_status(
            question_id,
            status='cant_convert',
            correction_notes=llm_result.get('correction_notes', 'Question cannot be formalized'),
            processing_completed_at=datetime.now().isoformat()
        )
        return

    # Update with preprocessed data
    update_data = {
        'status': 'preprocessed',
        'preprocessed_body': llm_result.get('corrected_question'),
        'preprocessed_answer': llm_result.get('corrected_answer'),
        'correction_notes': llm_result.get('correction_notes', ''),
        'processing_completed_at': datetime.now().isoformat()
    }

    db.update_processing_status(question_id, **update_data)


def main():
    """Main CLI loop."""
    import sys

    # Check for --write flag
    write_to_db = '--write' in sys.argv or '-w' in sys.argv

    print("\n" + "=" * 80)
    print("🧪 PREPROCESS CLI TEST TOOL")
    print("=" * 80)
    print("\nThis tool allows you to test the preprocessing pipeline for specific questions.")
    print("You will see:")
    print("  1. Question information")
    print("  2. Raw LLM API response")
    print("  3. Final backend processing result")
    if write_to_db:
        print("\n⚠️  WRITE MODE ENABLED (--write flag detected)")
        print("   Results WILL be saved to database")
    else:
        print("\n📖 READ-ONLY MODE (default)")
        print("   Results will NOT be saved to database")
        print("   Use --write or -w flag to enable saving")
    print("\n" + "=" * 80)

    from backend.database import DatabaseManager
    from backend.config import get_settings

    settings = get_settings()
    db = DatabaseManager(settings.db_path)

    # Show available questions
    print("\n📊 Available questions in database:")
    stats = db.get_statistics()
    total = stats.get('total_questions', 0)

    # Count by status
    status_counts = {}
    for status in ['raw', 'preprocessed', 'lean_converted', 'failed', 'cant_convert']:
        count = db.list_questions(status=status, limit=1).get('count', 0)
        status_counts[status] = count

    print(f"  Total: {total}")
    print(f"  Raw: {status_counts.get('raw', 0)}")
    print(f"  Preprocessed: {status_counts.get('preprocessed', 0)}")
    print(f"  Lean Converted: {status_counts.get('lean_converted', 0)}")
    print(f"  Failed: {status_counts.get('failed', 0)}")
    print(f"  Can't Convert: {status_counts.get('cant_convert', 0)}")

    # Get some sample questions
    print("\n📋 Sample questions (first 5):")
    all_questions = db.list_questions(limit=5)
    if all_questions.get('questions'):
        for q in all_questions['questions']:
            status_emoji = {
                'raw': '📝',
                'preprocessed': '✅',
                'lean_converted': '🔷',
                'failed': '❌',
                'cant_convert': '⚠️'
            }.get(q.get('status'), '❓')
            print(f"  ID {q['id']}: {status_emoji} {q['title'][:60]}...")

    while True:
        print("\n" + "=" * 80)
        question_id = input("Enter question ID to test (or 'q' to quit): ").strip()

        if question_id.lower() == 'q':
            print("\n👋 Goodbye!")
            break

        if not question_id:
            print("❌ Please enter a valid question ID")
            continue

        try:
            question_id = int(question_id)
            test_preprocess(question_id, write_to_db=write_to_db)
        except ValueError:
            print("❌ Invalid input. Please enter a numeric ID.")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()
