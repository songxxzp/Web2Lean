"""
LLM Processor for preprocessing mathematical content.
"""
import json
import base64
from typing import Dict, Any, Optional

from ..database import DatabaseManager
from ..utils import ZhipuClient


class LLMProcessor:
    """Process questions using GLM-4V/4 for OCR and content correction."""

    def __init__(self, db_manager: DatabaseManager, api_key: str):
        """
        Initialize LLM processor.

        Args:
            db_manager: Database manager instance
            api_key: Zhipu API key
        """
        self.db = db_manager
        self.client = ZhipuClient(api_key=api_key)

    def process_question(self, question_internal_id: int) -> Dict[str, Any]:
        """
        Process a question through LLM preprocessing.

        Args:
            question_internal_id: Internal database question ID

        Returns:
            Processing result
        """
        # Get question
        question = self.db.get_question(question_internal_id)
        if not question:
            raise ValueError(f"Question {question_internal_id} not found")

        # Update status
        self.db.update_processing_status(
            question_internal_id,
            status='preprocessing',
            current_stage='llm_correction',
            processing_started_at=self._now()
        )

        try:
            # Step 1: Process images (OCR if applicable)
            ocr_results = {}
            if question.get('images'):
                for img in question['images']:
                    ocr_text = self._process_image(img)
                    if ocr_text:
                        ocr_results[img['original_url']] = ocr_text

            # Step 2: Correct content using GLM-4
            corrected = self._correct_content(
                question['title'],
                question['body'],
                question.get('answers', [])
            )

            # Update processing status
            self.db.update_processing_status(
                question_internal_id,
                status='preprocessed',
                ocr_completed=bool(ocr_results),
                preprocessed_body=corrected.get('corrected_body', question['body']),
                preprocessed_answer=corrected.get('corrected_answer'),
                correction_notes=corrected.get('correction_notes'),
                processing_completed_at=self._now()
            )

            return {
                'success': True,
                'ocr_count': len(ocr_results),
                'corrected': corrected.get('has_errors', False)
            }

        except Exception as e:
            self.db.update_processing_status(
                question_internal_id,
                status='failed',
                current_stage='llm_correction',
                lean_error=str(e),
                processing_completed_at=self._now()
            )
            raise

    def _process_image(self, image_info: Dict[str, Any]) -> Optional[str]:
        """
        Process an image with GLM-4V for OCR.

        Args:
            image_info: Image information dict

        Returns:
            OCR text or None
        """
        try:
            # Prepare image for GLM-4V
            # If image_data exists, convert to base64
            if 'image_data' not in image_info:
                return None

            image_data = image_info['image_data']
            # For large images, we'd need to save to file or use URL
            # For now, skip if no URL available
            if not image_info.get('original_url'):
                return None

            # Use GLM-4V to analyze
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
            print(f"Error processing image: {e}")
            return None

    def _correct_content(
        self,
        title: str,
        body: str,
        answers: list
    ) -> Dict[str, Any]:
        """
        Correct question/answer content using GLM-4.

        Args:
            title: Question title
            body: Question body
            answers: List of answers

        Returns:
            Correction result dict
        """
        # Combine title and body
        question_text = f"{title}\n\n{body}"

        # Get best answer (accepted or highest score)
        best_answer = None
        if answers:
            accepted = [a for a in answers if a.get('is_accepted')]
            if accepted:
                best_answer = accepted[0]['body']
            else:
                # Get highest score answer
                best_answer = max(answers, key=lambda a: a.get('score', 0))['body']

        # If no answer, just validate question
        if not best_answer:
            return {
                'has_errors': False,
                'corrected_body': body,
                'correction_notes': 'No answer to validate against'
            }

        # Use GLM-4 to validate and correct
        result = self.client.correct_content(
            question=question_text,
            answer=best_answer,
            temperature=0.2
        )

        return {
            'has_errors': result.get('has_errors', False),
            'errors': result.get('errors', []),
            'corrected_body': result.get('corrected_question', body),
            'corrected_answer': result.get('corrected_answer', best_answer),
            'correction_notes': result.get('correction_notes', ''),
            'worth_formalizing': result.get('worth_formalizing', True),
        }

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
