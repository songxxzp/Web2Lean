"""
Lean converter using Kimina-Autoformalizer-7B via VLLM.
"""
from typing import Dict, Any

from ..database import DatabaseManager
from ..utils import VLLMClient


class LeanConverter:
    """Convert mathematical problems to Lean 4 using Kimina-Autoformalizer-7B."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        vllm_base_url: str = "http://localhost:8000/v1",
        model_path: str = "/root/Kimina-Autoformalizer-7B"
    ):
        """
        Initialize Lean converter.

        Args:
            db_manager: Database manager instance
            vllm_base_url: VLLM server base URL
            model_path: Model path/name
        """
        self.db = db_manager
        self.client = VLLMClient(base_url=vllm_base_url, model_path=model_path)

    def convert_question(self, question_internal_id: int) -> Dict[str, Any]:
        """
        Convert a question to Lean 4.

        Args:
            question_internal_id: Internal database question ID

        Returns:
            Conversion result
        """
        # Get question
        question = self.db.get_question(question_internal_id)
        if not question:
            raise ValueError(f"Question {question_internal_id} not found")

        # Check if preprocessed
        status = question.get('processing_status', {})
        if status.get('status') != 'preprocessed':
            raise ValueError(f"Question {question_internal_id} is not preprocessed")

        # Update status
        self.db.update_processing_status(
            question_internal_id,
            current_stage='lean_conversion',
            processing_started_at=self._now()
        )

        try:
            # Use preprocessed content if available
            body = status.get('preprocessed_body') or question['body']
            answer = status.get('preprocessed_answer')

            # Format problem for conversion
            problem_text = self._format_problem(question['title'], body, answer)

            # Convert to Lean
            lean_code = self.client.convert_to_lean(
                problem_text=problem_text,
                max_tokens=2048,
                temperature=0.6
            )

            # Update processing status
            self.db.update_processing_status(
                question_internal_id,
                status='lean_converted',
                lean_code=lean_code,
                processing_completed_at=self._now()
            )

            return {
                'success': True,
                'lean_code': lean_code
            }

        except Exception as e:
            error_msg = str(e)
            self.db.update_processing_status(
                question_internal_id,
                status='failed',
                lean_error=error_msg,
                processing_completed_at=self._now()
            )
            raise

    def _format_problem(self, title: str, body: str, answer: str = None) -> str:
        """
        Format problem for Lean conversion.

        Args:
            title: Question title
            body: Question body
            answer: Optional answer

        Returns:
            Formatted problem text
        """
        problem = f"Problem: {title}\n\n{body}"
        if answer:
            problem += f"\n\nSolution: {answer}"
        return problem

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
