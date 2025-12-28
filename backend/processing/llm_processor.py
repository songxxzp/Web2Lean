"""
LLM Processor for preprocessing mathematical content with improved answer handling.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..database import DatabaseManager
from ..utils import ZhipuClient

logger = logging.getLogger(__name__)

# Backend version for tracking preprocessing changes
BACKEND_VERSION = "1.0.1"


class LLMProcessor:
    """Process questions using GLM-4V/4 for OCR and content correction."""

    def __init__(self, db_manager: DatabaseManager, api_key: str, text_model: str = None,
                 vision_model: str = None, max_length: int = 16000):
        """
        Initialize LLM processor.

        Args:
            db_manager: Database manager instance
            api_key: Zhipu API key
            text_model: Model name for text processing (default: from settings)
            vision_model: Model name for image OCR (default: from settings)
            max_length: Max token length for LLM calls (default: 16000)
        """
        self.db = db_manager
        self.text_model = text_model or "glm-4.7"
        self.vision_model = vision_model or "glm-4.6v"
        self.max_length = max_length
        self.client = ZhipuClient(api_key=api_key)

    def process_question(self, question_internal_id: int) -> Dict[str, Any]:
        """
        Process a question through LLM preprocessing with new logic:
        - No answer: process question only
        - One answer: validate and process question+answer
        - Multiple answers: LLM selects best, process question+best answer
        - No correct answer: process question only (if question valid)
        - Invalid question: mark as cant_convert

        Args:
            question_internal_id: Internal database question ID

        Returns:
            Processing result
        """
        # Get question
        question = self.db.get_question(question_internal_id)
        if not question:
            raise ValueError(f"Question {question_internal_id} not found")

        logger.info(f"Processing question {question_internal_id}: {question['title'][:50]}...")

        # Update status
        self.db.update_processing_status(
            question_internal_id,
            status='preprocessing',
            current_stage='llm_correction',
            processing_started_at=self._now()
        )

        try:
            # Combine title and body
            question_text = f"{question['title']}\n\n{question['body']}"
            answers = question.get('answers', [])

            # Step 1: Process images (OCR if applicable)
            ocr_results = {}
            if question.get('images'):
                for img in question['images']:
                    ocr_text = self._process_image(img)
                    if ocr_text:
                        ocr_results[img['original_url']] = ocr_text

            # Step 2: Determine processing strategy based on answers
            if not answers:
                # No answers - process question only
                logger.info(f"Question {question_internal_id} has no answers, processing question only")
                result = self._process_question_only(question_text)

            elif len(answers) == 1:
                # One answer - validate both
                logger.info(f"Question {question_internal_id} has 1 answer, validating question+answer")
                result = self._process_question_with_answer(
                    question_text,
                    answers[0]['body']
                )

            else:
                # Multiple answers - let LLM select best
                logger.info(f"Question {question_internal_id} has {len(answers)} answers, selecting best")
                result = self._process_with_multiple_answers(
                    question_text,
                    answers
                )

            # Handle result
            if result.get('status') == 'cant_convert':
                # Question is invalid, mark as cant_convert
                self.db.update_processing_status(
                    question_internal_id,
                    status='cant_convert',
                    ocr_completed=bool(ocr_results),
                    correction_notes=result.get('correction_notes', 'Question cannot be formalized'),
                    processing_completed_at=self._now()
                )
                return {
                    'success': True,
                    'status': 'cant_convert',
                    'reason': result.get('correction_notes')
                }

            # Validate response
            if not result or not isinstance(result, dict):
                raise ValueError(f"Invalid processing result: {result}")

            # Fallback: if LLM didn't return theorem_name, generate one from title
            theorem_name = result.get('theorem_name')
            if not theorem_name or not theorem_name.strip():
                from ..utils.prompts import sanitize_theorem_name
                theorem_name = sanitize_theorem_name(question['title'])
                logger.warning(f"LLM did not return theorem_name for question {question_internal_id}, using fallback: {theorem_name}")

            logger.info(f"LLM completed for question {question_internal_id}: has_answer={bool(result.get('preprocessed_answer'))}, theorem_name={theorem_name}")

            # Update processing status with preprocessed data
            self.db.update_processing_status(
                question_internal_id,
                status='preprocessed',
                ocr_completed=bool(ocr_results),
                preprocessed_body=result.get('preprocessed_body', question['body']),
                preprocessed_answer=result.get('preprocessed_answer'),
                theorem_name=theorem_name,
                correction_notes=result.get('correction_notes'),
                preprocessing_version=BACKEND_VERSION,
                processing_completed_at=self._now()
            )

            return {
                'success': True,
                'status': 'preprocessed',
                'ocr_count': len(ocr_results),
                'has_answer': bool(result.get('preprocessed_answer'))
            }

        except Exception as e:
            # Determine if this is a program error or invalid content
            error_msg = str(e)
            is_program_error = self._is_program_error(error_msg)

            if is_program_error:
                # Program error - mark as failed (can retry)
                logger.error(f"Program error processing question {question_internal_id}: {e}")
                self.db.update_processing_status(
                    question_internal_id,
                    status='failed',
                    current_stage='llm_correction',
                    preprocessing_error=f"Preprocessing program error: {error_msg}",
                    processing_completed_at=self._now()
                )
                raise
            else:
                # Content error - mark as cant_convert (won't be fixed by retry)
                logger.warning(f"Content error processing question {question_internal_id}: {e}")
                self.db.update_processing_status(
                    question_internal_id,
                    status='cant_convert',
                    preprocessing_error=f"Content validation error: {error_msg}",
                    correction_notes=f"Content validation error: {error_msg}",
                    processing_completed_at=self._now()
                )
                return {
                    'success': False,
                    'status': 'cant_convert',
                    'error': error_msg
                }

    def _process_question_only(self, question_text: str) -> Dict[str, Any]:
        """
        Process a question without any answer.

        Args:
            question_text: Question text

        Returns:
            Processing result dict
        """
        try:
            result = self.client.correct_question_only(
                question=question_text,
                temperature=0.2,
                model=self.text_model,
                max_tokens=self.max_length
            )

            # Check if question is valid
            if not result.get('is_valid_question'):
                return {
                    'status': 'cant_convert',
                    'correction_notes': result.get('correction_notes', 'Question is not valid for formalization')
                }

            return {
                'status': 'preprocessed',
                'preprocessed_body': result.get('corrected_question', question_text),
                'theorem_name': result.get('theorem_name'),
                'correction_notes': result.get('correction_notes', '')
            }

        except Exception as e:
            # Re-raise to be caught by outer handler
            raise ValueError(f"Question validation failed: {e}")

    def _process_question_with_answer(self, question_text: str, answer_text: str) -> Dict[str, Any]:
        """
        Process a question with a single answer.

        Args:
            question_text: Question text
            answer_text: Answer text

        Returns:
            Processing result dict
        """
        try:
            result = self.client.correct_content(
                question=question_text,
                answer=answer_text,
                temperature=0.2,
                model=self.text_model,
                max_tokens=self.max_length
            )

            # Check if question is valid
            if not result.get('is_valid_question'):
                return {
                    'status': 'cant_convert',
                    'correction_notes': result.get('correction_notes', 'Question is not valid')
                }

            # Determine if we should include the answer
            should_include_answer = (
                result.get('is_valid_answer', False) and
                result.get('worth_formalizing', True)
            )

            if should_include_answer:
                return {
                    'status': 'preprocessed',
                    'preprocessed_body': result.get('corrected_question', question_text),
                    'preprocessed_answer': result.get('corrected_answer', answer_text),
                    'theorem_name': result.get('theorem_name'),
                    'correction_notes': result.get('correction_notes', '')
                }
            else:
                # Answer is not valid, process question only
                return {
                    'status': 'preprocessed',
                    'preprocessed_body': result.get('corrected_question', question_text),
                    'theorem_name': result.get('theorem_name'),
                    'correction_notes': result.get('correction_notes', '') + " [Answer excluded: not valid]"
                }

        except Exception as e:
            raise ValueError(f"Question+answer validation failed: {e}")

    def _process_with_multiple_answers(self, question_text: str, answers: list) -> Dict[str, Any]:
        """
        Process a question with multiple answers using LLM to produce single correct answer.

        Args:
            question_text: Question text
            answers: List of answer dicts

        Returns:
            Processing result dict
        """
        try:
            result = self.client.validate_and_select_answer(
                question=question_text,
                answers=answers,
                temperature=0.2,
                model=self.text_model,
                max_tokens=self.max_length
            )

            # Check if question is valid
            if not result.get('is_valid_question'):
                return {
                    'status': 'cant_convert',
                    'correction_notes': result.get('correction_notes', 'Question is not valid')
                }

            # Check if a valid answer exists
            if not result.get('is_valid_answer'):
                # No valid answer, process question only
                return {
                    'status': 'preprocessed',
                    'preprocessed_body': result.get('corrected_question', question_text),
                    'preprocessed_answer': None,
                    'theorem_name': result.get('theorem_name'),
                    'correction_notes': result.get('correction_notes', '') + " [No valid answer found]"
                }

            # Use LLM-corrected question and answer directly
            return {
                'status': 'preprocessed',
                'preprocessed_body': result.get('corrected_question', question_text),
                'preprocessed_answer': result.get('corrected_answer'),
                'theorem_name': result.get('theorem_name'),
                'correction_notes': result.get('correction_notes', '')
            }

        except Exception as e:
            raise ValueError(f"Multiple answer validation failed: {e}")

    def _process_image(self, image_info: Dict[str, Any]) -> Optional[str]:
        """
        Process an image with GLM-4V for OCR.

        Args:
            image_info: Image information dict

        Returns:
            OCR text or None
        """
        try:
            if 'image_data' not in image_info:
                return None

            if not image_info.get('original_url'):
                return None

            prompt = """You are a mathematical content analyzer. Examine this image and determine:

1. Does this image contain primarily mathematical notation, text, or diagrams that can be converted to text/LaTeX?
2. Or is it primarily a complex plot, graph, or visual that should remain as an image?

Respond in JSON format:
{
  "can_convert_to_text": true/false,
  "reasoning": "Brief explanation",
  "content_type": "latex/text/diagram/graph/other",
  "extracted_text": "If convertible, provide LaTeX or text representation"
}"""

            result = self.client.analyze_image(
                image_url=image_info['original_url'],
                prompt=prompt,
                model=self.vision_model,
                temperature=0.1
            )

            # Parse result
            try:
                parsed = json.loads(result)
                if parsed.get('can_convert_to_text') and parsed.get('extracted_text'):
                    return parsed['extracted_text']
            except json.JSONDecodeError:
                pass

            return None

        except Exception as e:
            logger.warning(f"Error processing image: {e}")
            return None

    def _is_program_error(self, error_msg: str) -> bool:
        """
        Determine if an error is a program error (retryable) or content error (not retryable).

        Program errors:
        - API errors (timeout, rate limit, connection)
        - JSON parsing errors (LLM returned invalid format)
        - Network errors

        Content errors:
        - Validation failures (question invalid)
        - Content issues

        Args:
            error_msg: Error message string

        Returns:
            True if program error, False if content error
        """
        program_error_keywords = [
            'timeout',
            'connection',
            'network',
            'rate limit',
            '429',
            '500',
            '502',
            '503',
            '504',
            'JSON',
            'parse',
            'API',
            'zhipu',
            'zai-sdk'
        ]

        error_msg_lower = error_msg.lower()
        return any(keyword.lower() in error_msg_lower for keyword in program_error_keywords)

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    def process_questions_batch(self, question_ids: List[int], concurrency: int = 2) -> List[Dict[str, Any]]:
        """
        Process multiple questions concurrently with ThreadPoolExecutor.

        Args:
            question_ids: List of question IDs to process
            concurrency: Number of concurrent LLM API calls (default: 2)

        Returns:
            List of processing results
        """
        logger.info(f"Starting batch preprocessing of {len(question_ids)} questions with concurrency={concurrency}")

        results = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # Submit all tasks
            future_to_qid = {
                executor.submit(self.process_question, qid): qid
                for qid in question_ids
            }

            # Process completed tasks
            for future in as_completed(future_to_qid):
                qid = future_to_qid[future]
                try:
                    result = future.result()
                    results.append({
                        'question_id': qid,
                        'success': result.get('success', False),
                        'status': result.get('status'),
                        'result': result
                    })
                    logger.info(f"✓ Completed question {qid}: {result.get('status')}")
                except Exception as e:
                    logger.error(f"✗ Failed question {qid}: {e}")
                    results.append({
                        'question_id': qid,
                        'success': False,
                        'error': str(e)
                    })

        logger.info(f"Batch preprocessing complete: {len(results)}/{len(question_ids)} processed")
        return results
