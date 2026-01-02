#!/usr/bin/env python3
"""
Interactive CLI for testing Lean Agent Converter

Debugging tool for LLM-based Lean conversion with detailed logging.
Shows API calls, responses, verification results, and error messages.

Usage:
    # Interactive mode
    python test_lean_converter.py

    # Non-interactive mode
    python test_lean_converter.py --question-id 123
    python test_lean_converter.py --question-id 123 --show-requests --show-responses
    python test_lean_converter.py --question-id 123 --verify-only
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.database import DatabaseManager
from backend.config.settings import Settings
from backend.processing.lean_converter import LLMLeanConverter
from backend.utils.prompts import (
    LEAN_QUESTION_PROMPT,
    LEAN_WITH_ANSWER_PROMPT,
    LEAN_CORRECTION_PROMPT
)


class DebugLLMLeanConverter(LLMLeanConverter):
    """Extended LLM Lean Converter with debug output"""

    def __init__(self, *args, verbose=True, show_requests=False, show_responses=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = verbose
        self.show_requests = show_requests
        self.show_responses = show_responses
        self.api_calls = []

    def _log_section(self, title: str):
        """Print a section header"""
        if self.verbose:
            print(f"\n{'='*80}")
            print(f"  {title}")
            print(f"{'='*80}\n")

    def _log_request(self, endpoint: str, data: Dict[str, Any]):
        """Log API request"""
        if not self.show_requests:
            return

        print(f"\n[API REQUEST] {datetime.now().strftime('%H:%M:%S')}")
        print(f"Endpoint: {endpoint}")
        print(f"Data:")
        if 'messages' in data:
            # Show message structure but truncate content
            print(f"  Messages: {len(data['messages'])} messages")
            for i, msg in enumerate(data['messages']):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                content_preview = content[:200] + "..." if len(content) > 200 else content
                print(f"    [{i}] {role}: {content_preview}")
        else:
            print(f"  {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
        print()

    def _log_response(self, endpoint: str, response: Any, error: str = None):
        """Log API response"""
        if not self.show_responses:
            return

        print(f"\n[API RESPONSE] {datetime.now().strftime('%H:%M:%S')}")
        print(f"Endpoint: {endpoint}")

        if error:
            print(f"Status: ERROR")
            print(f"Error: {error}")
        else:
            print(f"Status: SUCCESS")

            if isinstance(response, dict):
                # Show structured response
                if 'choices' in response:
                    print(f"Choices: {len(response['choices'])}")
                    if response['choices']:
                        content = response['choices'][0].get('message', {}).get('content', '')
                        print(f"Content length: {len(content)} chars")
                        print(f"Content preview:\n{content[:500]}")
                        if len(content) > 500:
                            print("... (truncated)")
                else:
                    print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)[:500]}")
            else:
                print(f"Response: {str(response)[:500]}")

        print()

    def _log_lean_code(self, lean_code: str, label: str = "LEAN CODE"):
        """Log generated Lean code"""
        if not self.verbose:
            return

        print(f"\n[{label}]")
        print(f"Length: {len(lean_code)} chars")
        print(f"Lines: {len(lean_code.split(chr(10)))} lines")
        print(f"\n{lean_code}")
        print()

    def _log_verification(self, verification: Dict[str, Any]):
        """Log verification result"""
        if not self.verbose:
            return

        print(f"\n[VERIFICATION RESULT]")
        print(f"Status: {verification.get('status', 'unknown')}")
        print(f"Has errors: {verification.get('has_errors', False)}")
        print(f"Has warnings: {verification.get('has_warnings', False)}")
        print(f"Time: {verification.get('time', 0):.2f}s")

        messages = verification.get('messages', [])
        if messages:
            print(f"\nMessages ({len(messages)}):")
            for msg in messages[:10]:  # Show first 10 messages
                severity = msg.get('severity', 'info')
                line = msg.get('line', '?')
                text = msg.get('message', '')
                print(f"  [{severity.upper()}] Line {line}: {text}")

            if len(messages) > 10:
                print(f"  ... and {len(messages) - 10} more messages")
        print()

    def _call_llm(self, prompt: str) -> str:
        """Call GLM API with logging"""
        endpoint = f"GLM API ({self.model})"

        request_data = {
            "messages": [
                {"role": "system", "content": "You are an expert Lean 4 formalizer. Output only valid Lean 4 code without explanations."},
                {"role": "user", "content": prompt}
            ],
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        self._log_request(endpoint, request_data)

        try:
            response = self.client.chat_completion(
                messages=request_data["messages"],
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            self._log_response(endpoint, response)

            # Store for later analysis
            self.api_calls.append({
                'timestamp': datetime.now().isoformat(),
                'endpoint': endpoint,
                'request': request_data,
                'response': str(response)[:1000] if response else None,
                'success': True
            })

            # Extract content
            if isinstance(response, dict):
                if 'choices' in response and len(response['choices']) > 0:
                    content = response['choices'][0].get('message', {}).get('content', '')
                else:
                    content = str(response)
            else:
                content = str(response)

            # Extract Lean code
            lean_code = self._extract_lean_code(content)
            return lean_code

        except Exception as e:
            error_msg = str(e)
            self._log_response(endpoint, None, error=error_msg)

            self.api_calls.append({
                'timestamp': datetime.now().isoformat(),
                'endpoint': endpoint,
                'request': request_data,
                'error': error_msg,
                'success': False
            })
            # Print traceback for debugging
            import traceback
            traceback.print_exc()

            raise


    def _verify_lean_code(self, lean_code: str) -> Dict[str, Any]:
        """Verify Lean code with logging"""
        # Note: Now using KiminaClient.check() instead of /verify endpoint

        if self.show_requests:
            print(f"\n[VERIFICATION REQUEST] {datetime.now().strftime('%H:%M:%S')}")
            print(f"Method: KiminaClient.check()")
            print(f"URL: {self.kimina_url}")
            print(f"Code length: {len(lean_code)} chars")
            print(f"Code preview:\n{lean_code[:300]}")
            if len(lean_code) > 300:
                print("... (truncated)")
            print()

        # Call parent method (now uses KiminaClient)
        result = super()._verify_lean_code(lean_code)

        self._log_verification(result)

        return result

    def _convert_with_correction(
        self,
        theorem_name: str,
        body: str,
        answer: str = None,
        lean_type: str = "question"
    ) -> Dict[str, Any]:
        """Convert to Lean with detailed logging"""
        self._log_section(f"CONVERTING: {lean_type.upper()} - Theorem: {theorem_name}")

        # Show input
        if self.verbose:
            print(f"[INPUT]")
            print(f"Theorem name: {theorem_name}")
            print(f"Body length: {len(body)} chars")
            print(f"Body preview:\n{body[:300]}")
            if len(body) > 300:
                print("... (truncated)")
            if answer:
                print(f"\nAnswer length: {len(answer)} chars")
                print(f"Answer preview:\n{answer[:300]}")
                if len(answer) > 300:
                    print("... (truncated)")
            print()

        # Generate initial Lean code
        if lean_type == "question" or answer is None:
            prompt = LEAN_QUESTION_PROMPT.replace('{problem}', body)
        else:
            prompt = LEAN_WITH_ANSWER_PROMPT.replace('{problem}', body).replace('{answer}', answer)

        prompt += f"\n\nUse the theorem name: {theorem_name}"

        if self.show_requests:
            print(f"\n[PROMPT]")
            print(f"Length: {len(prompt)} chars")
            print(f"Preview:\n{prompt[:400]}")
            if len(prompt) > 400:
                print("... (truncated)")
            print()

        current_lean = self._call_llm(prompt)
        iteration = 0

        self._log_lean_code(current_lean, f"GENERATED LEAN CODE (Iteration {iteration})")

        # Iterative correction
        while iteration < self.max_iterations:
            self._log_section(f"VERIFICATION - Iteration {iteration}")

            # Verify current Lean code
            verification = self._verify_lean_code(current_lean)

            # If passed or has only warnings, we're done
            if verification['status'] in ['passed', 'warning']:
                if self.verbose:
                    print(f"✓ Lean verification {verification['status']} after {iteration} iterations")
                break

            # If no errors (or max iterations reached), stop
            if not verification.get('has_errors') or iteration >= self.max_iterations - 1:
                if self.verbose:
                    print(f"ℹ Stopping after {iteration + 1} iterations (max: {self.max_iterations})")
                break

            # Generate correction prompt
            error_message = self._format_error_message(verification.get('messages', []))
            correction_prompt = LEAN_CORRECTION_PROMPT.replace('{previous_lean}', current_lean).replace('{error_message}', error_message)

            if self.show_requests:
                print(f"\n[CORRECTION PROMPT]")
                print(f"Errors to fix:\n{error_message[:500]}")
                if len(error_message) > 500:
                    print("... (truncated)")
                print()

            # Get corrected code
            try:
                current_lean = self._call_llm(correction_prompt)
                iteration += 1

                if self.verbose:
                    print(f"✓ Iteration {iteration}: Generated corrected Lean code")

                self._log_lean_code(current_lean, f"CORRECTED LEAN CODE (Iteration {iteration})")

            except Exception as e:
                import traceback
                traceback.print_exc()
                if self.verbose:
                    print(f"✗ Error during correction iteration {iteration}: {e}")
                break

        self._log_section("CONVERSION COMPLETE")

        return {
            'lean_code': current_lean,
            'verification': verification,
            'iterations': iteration + 1
        }

    def convert_question(self, question_internal_id: int, verify_only: bool = False) -> Dict[str, Any]:
        """Convert with full logging"""
        self._log_section(f"STARTING CONVERSION - Question ID: {question_internal_id}")

        # Get question
        question = self.db.get_question(question_internal_id)
        if not question:
            raise ValueError(f"Question {question_internal_id} not found")

        if self.verbose:
            print(f"[QUESTION INFO]")
            print(f"Title: {question.get('title', 'N/A')}")
            print(f"Status: {question.get('processing_status', {}).get('status', 'unknown')}")

        # Check if preprocessed
        status = question.get('processing_status', {})
        current_status = status.get('status')

        if current_status not in ['preprocessed', 'cant_convert']:
            raise ValueError(f"Question {question_internal_id} is not ready for Lean conversion (status: {current_status})")

        if verify_only:
            # Just verify existing code
            self._log_section("VERIFY-ONLY MODE")

            question_lean = status.get('question_lean_code')
            answer_lean = status.get('answer_lean_code')

            if not question_lean:
                print("No Lean code found for this question")
                return {}

            result = {
                'question_lean_code': question_lean,
                'answer_lean_code': answer_lean,
            }

            if question_lean:
                print("\n[VERIFYING QUESTION LEAN CODE]")
                self._log_lean_code(question_lean, "QUESTION LEAN CODE")
                question_verification = self._verify_lean_code(question_lean)
                result['question_verification'] = question_verification

            if answer_lean:
                print("\n[VERIFYING ANSWER LEAN CODE]")
                self._log_lean_code(answer_lean, "ANSWER LEAN CODE")
                answer_verification = self._verify_lean_code(answer_lean)
                result['answer_verification'] = answer_verification

            return result

        # Normal conversion
        try:
            from backend.utils.prompts import sanitize_theorem_name

            # Use preprocessed content if available
            body = status.get('preprocessed_body') or question['body']
            answer = status.get('preprocessed_answer')
            theorem_name = status.get('theorem_name') or sanitize_theorem_name(question['title'])

            if self.verbose:
                print(f"\n[PREPROCESSED DATA]")
                print(f"Theorem name: {theorem_name}")
                print(f"Has preprocessed body: {bool(status.get('preprocessed_body'))}")
                print(f"Has preprocessed answer: {bool(status.get('preprocessed_answer'))}")

            # Convert question to Lean (with sorry)
            question_result = self._convert_with_correction(
                theorem_name=theorem_name,
                body=body,
                answer=None,
                lean_type="question"
            )
            question_lean = question_result['lean_code']

            # Convert answer to Lean if available
            answer_lean = None
            verification_result = None

            if answer:
                answer_result = self._convert_with_correction(
                    theorem_name=theorem_name,
                    body=body,
                    answer=answer,
                    lean_type="answer"
                )
                answer_lean = answer_result['lean_code']
                verification_result = answer_result['verification']

            # Summary
            self._log_section("SUMMARY")
            print(f"✓ Question Lean code: {len(question_lean)} chars")
            if answer_lean:
                print(f"✓ Answer Lean code: {len(answer_lean)} chars")
            if verification_result:
                print(f"✓ Verification status: {verification_result.get('status', 'unknown')}")

            print(f"\nTotal API calls: {len(self.api_calls)}")
            print(f"Successful calls: {sum(1 for c in self.api_calls if c['success'])}")
            print(f"Failed calls: {sum(1 for c in self.api_calls if not c['success'])}")

            return {
                'success': True,
                'question_lean_code': question_lean,
                'answer_lean_code': answer_lean,
                'has_answer': answer_lean is not None,
                'converter_name': self.converter_name,
                'verification': verification_result,
                'api_calls': self.api_calls
            }

        except Exception as e:
            self._log_section("ERROR")
            print(f"✗ Conversion failed: {e}")
            import traceback
            traceback.print_exc()
            raise


def print_banner():
    """Print CLI banner"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║           Web2Lean Lean Agent Converter - Debug Tool              ║
║                                                                    ║
║           Interactive testing for LLM-based Lean conversion       ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)


def print_menu():
    """Print main menu"""
    print("""
Main Menu:
─────────────────────────────────────────────────────────────────────
  1. List preprocessed questions
  2. Convert a question (by ID)
  3. Verify existing Lean code (by ID)
  4. View question details
  5. Exit
─────────────────────────────────────────────────────────────────────
    """)


def list_preprocessed_questions(db: DatabaseManager, limit: int = 20):
    """List preprocessed questions"""
    session = db.get_session()
    try:
        from backend.database.schema import ProcessingStatus

        questions = session.query(ProcessingStatus).filter(
            ProcessingStatus.status == 'preprocessed'
        ).order_by(ProcessingStatus.question_id.desc()).limit(limit).all()

        if not questions:
            print("No preprocessed questions found")
            return

        print(f"\nFound {len(questions)} preprocessed questions:")
        print("─" * 80)
        print(f"{'ID':<8} {'Title':<50} {'Has Answer':<12}")
        print("─" * 80)

        for q in questions:
            title = q.question.title if q.question else 'N/A'
            title = title[:47] + "..." if len(title) > 50 else title
            has_answer = "Yes" if q.preprocessed_answer else "No"
            print(f"{q.question_id:<8} {title:<50} {has_answer:<12}")

        print()

    finally:
        session.close()


def view_question_details(db: DatabaseManager, question_id: int):
    """View question details"""
    question = db.get_question(question_id)
    if not question:
        print(f"Question {question_id} not found")
        return

    status = question.get('processing_status', {})

    print(f"\nQuestion Details:")
    print("─" * 80)
    print(f"ID: {question_id}")
    print(f"Title: {question.get('title', 'N/A')}")
    print(f"Status: {status.get('status', 'unknown')}")
    print(f"Body length: {len(question.get('body', ''))} chars")

    if status.get('theorem_name'):
        print(f"Theorem name: {status.get('theorem_name')}")

    if status.get('preprocessed_body'):
        print(f"Preprocessed body: {len(status.get('preprocessed_body', ''))} chars")

    if status.get('preprocessed_answer'):
        print(f"Preprocessed answer: {len(status.get('preprocessed_answer', ''))} chars")

    if status.get('question_lean_code'):
        print(f"Question Lean code: {len(status.get('question_lean_code', ''))} chars")

    if status.get('answer_lean_code'):
        print(f"Answer Lean code: {len(status.get('answer_lean_code', ''))} chars")

    if status.get('lean_error'):
        print(f"Lean error: {status.get('lean_error')}")

    print()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Web2Lean Lean Agent Converter Debug Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python test_lean_converter.py

  # Convert specific question
  python test_lean_converter.py --question-id 123

  # Show API requests and responses
  python test_lean_converter.py --question-id 123 --show-requests --show-responses

  # Verify existing Lean code only
  python test_lean_converter.py --question-id 123 --verify-only

  # Quiet mode (less output)
  python test_lean_converter.py --question-id 123 --quiet
        """
    )

    parser.add_argument(
        '--question-id', '-q',
        type=int,
        help='Question ID to convert'
    )

    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify existing Lean code, do not convert'
    )

    parser.add_argument(
        '--show-requests',
        action='store_true',
        help='Show API requests (prompts, parameters)'
    )

    parser.add_argument(
        '--show-responses',
        action='store_true',
        help='Show API responses (LLM output, verification results)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Quiet mode (less verbose output)'
    )

    parser.add_argument(
        '--max-iterations',
        type=int,
        default=1,
        help='Maximum correction iterations (default: 1)'
    )

    return parser.parse_args()


def interactive_mode(settings):
    """Run interactive mode"""
    print_banner()

    # Initialize database
    db = DatabaseManager(settings.db_path)
    print(f"Database: {settings.db_path}\n")

    while True:
        print_menu()
        choice = input("Select option (1-5): ").strip()

        if choice == '1':
            # List preprocessed questions
            try:
                list_limit = input("How many to show? [default: 20]: ").strip()
                limit = int(list_limit) if list_limit.isdigit() else 20
                list_preprocessed_questions(db, limit)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error: {e}")

        elif choice == '2':
            # Convert question
            try:
                question_id = input("Enter question ID: ").strip()
                if not question_id.isdigit():
                    print("Invalid question ID")
                    continue

                question_id = int(question_id)

                show_requests = input("Show API requests? (y/n) [default: n]: ").strip().lower() == 'y'
                show_responses = input("Show API responses? (y/n) [default: n]: ").strip().lower() == 'y'

                converter = DebugLLMLeanConverter(
                    db_manager=db,
                    api_key=settings.zhipu_api_key,
                    model=settings.glm_lean_model,
                    kimina_url=settings.kimina_url,
                    max_iterations=settings.lean_max_iterations,
                    temperature=settings.preprocessing_temperature,
                    max_tokens=settings.lean_conversion_max_tokens,
                    verbose=True,
                    show_requests=show_requests,
                    show_responses=show_responses
                )

                result = converter.convert_question(question_id)

                print("\n✓ Conversion completed!")

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"\n✗ Error: {e}")

        elif choice == '3':
            # Verify existing code
            try:
                question_id = input("Enter question ID: ").strip()
                if not question_id.isdigit():
                    print("Invalid question ID")
                    continue

                question_id = int(question_id)

                converter = DebugLLMLeanConverter(
                    db_manager=db,
                    api_key=settings.zhipu_api_key,
                    model=settings.glm_lean_model,
                    kimina_url=settings.kimina_url,
                    verbose=True
                )

                result = converter.convert_question(question_id, verify_only=True)

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"\n✗ Error: {e}")

        elif choice == '4':
            # View details
            try:
                question_id = input("Enter question ID: ").strip()
                if not question_id.isdigit():
                    print("Invalid question ID")
                    continue

                view_question_details(db, int(question_id))

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error: {e}")

        elif choice == '5':
            print("Goodbye!")
            break

        else:
            print("Invalid choice, please try again\n")


def main():
    """Main entry point"""
    args = parse_args()

    # Load settings
    settings = Settings()

    # Check API key
    if not settings.zhipu_api_key:
        print("Error: ZHIPU_API_KEY not set in .env file")
        sys.exit(1)

    # Non-interactive mode
    if args.question_id:
        if not args.quiet:
            print_banner()
            print(f"Running in non-interactive mode")
            print(f"Question ID: {args.question_id}")
            print(f"Verify only: {args.verify_only}")
            print(f"Show requests: {args.show_requests}")
            print(f"Show responses: {args.show_responses}")
            print()

        # Initialize database and converter
        db = DatabaseManager(settings.db_path)

        converter = DebugLLMLeanConverter(
            db_manager=db,
            api_key=settings.zhipu_api_key,
            model=settings.glm_lean_model,
            kimina_url=settings.kimina_url,
            max_iterations=args.max_iterations,
            temperature=settings.preprocessing_temperature,
            max_tokens=settings.lean_conversion_max_tokens,
            verbose=not args.quiet,
            show_requests=args.show_requests,
            show_responses=args.show_responses
        )

        try:
            result = converter.convert_question(args.question_id, verify_only=args.verify_only)

            if not args.quiet:
                print("\n✓ Operation completed successfully!")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # Interactive mode
        interactive_mode(settings)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
