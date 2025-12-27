"""
Lean converter using Kimina-Autoformalizer-7B via VLLM.
Converts questions and answers separately to Lean 4.
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
        Convert a question and its answer to Lean 4 (separately).

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
        current_status = status.get('status')

        # Allow conversion from preprocessed or cant_convert status
        if current_status not in ['preprocessed', 'cant_convert']:
            raise ValueError(f"Question {question_internal_id} is not ready for Lean conversion (status: {current_status})")

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

            # Convert question to Lean
            question_lean = self._convert_question_to_lean(question['title'], body)

            # Convert answer to Lean if available
            answer_lean = None
            if answer:
                answer_lean = self._convert_answer_to_lean(answer)

            # Combine question and answer Lean code
            combined_lean = self._combine_lean_code(question_lean, answer_lean)

            # Update processing status
            self.db.update_processing_status(
                question_internal_id,
                status='lean_converted',
                lean_code=combined_lean,
                processing_completed_at=self._now()
            )

            return {
                'success': True,
                'lean_code': combined_lean,
                'has_answer': answer_lean is not None
            }

        except Exception as e:
            # Determine if this is a program error
            error_msg = str(e)
            is_program_error = self._is_program_error(error_msg)

            if is_program_error:
                # Program error - mark as failed (can retry)
                self.db.update_processing_status(
                    question_internal_id,
                    status='failed',
                    lean_error=f"Lean conversion program error: {error_msg}",
                    processing_completed_at=self._now()
                )
                raise
            else:
                # Other error - also mark as failed but with different message
                self.db.update_processing_status(
                    question_internal_id,
                    status='failed',
                    lean_error=f"Lean conversion error: {error_msg}",
                    processing_completed_at=self._now()
                )
                raise

    def _convert_question_to_lean(self, title: str, body: str) -> str:
        """
        Convert a question to Lean 4 theorem/definition.

        Args:
            title: Question title
            body: Question body

        Returns:
            Lean 4 code for the question
        """
        problem_text = f"Problem: {title}\n\n{body}"

        prompt = f"""Convert the following mathematical problem statement to a Lean 4 theorem or definition.
Focus on formalizing the mathematical statement itself.

{problem_text}

Provide the Lean 4 code with appropriate imports and structure."""

        lean_code = self.client.convert_to_lean(
            problem_text=prompt,
            max_tokens=2048,
            temperature=0.6
        )

        return lean_code

    def _convert_answer_to_lean(self, answer: str) -> str:
        """
        Convert an answer/solution to Lean 4 proof.

        Args:
            answer: Answer text

        Returns:
            Lean 4 code for the proof
        """
        prompt = f"""Convert the following mathematical solution or proof to Lean 4.
This should be a proof that can be used with the corresponding theorem.

Solution/Proof:
{answer}

Provide the Lean 4 proof code with appropriate structure."""

        lean_code = self.client.convert_to_lean(
            problem_text=prompt,
            max_tokens=2048,
            temperature=0.6
        )

        return lean_code

    def _combine_lean_code(self, question_lean: str, answer_lean: str = None) -> str:
        """
        Combine question and answer Lean code into a complete formalization.

        Args:
            question_lean: Lean code for question (theorem/definition)
            answer_lean: Lean code for answer (proof), if available

        Returns:
            Combined Lean 4 code
        """
        if answer_lean:
            # Combine question and answer
            combined = f"{question_lean}\n\n{answer_lean}"
        else:
            # Question only
            combined = question_lean

        return combined

    def _is_program_error(self, error_msg: str) -> bool:
        """
        Determine if an error is a program error (retryable) or content error.

        Program errors:
        - VLLM server errors (timeout, connection, 500)
        - GPU errors
        - Model loading errors

        Args:
            error_msg: Error message string

        Returns:
            True if program error, False otherwise
        """
        program_error_keywords = [
            'timeout',
            'connection',
            'network',
            'VLLM',
            'vllm',
            'GPU',
            'CUDA',
            'OOM',
            'out of memory',
            '500',
            '502',
            '503',
            '504'
        ]

        error_msg_lower = error_msg.lower()
        return any(keyword.lower() in error_msg_lower for keyword in program_error_keywords)

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
