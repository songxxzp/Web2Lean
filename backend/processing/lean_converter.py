"""
Lean converter using Kimina-Autoformalizer-7B via VLLM.

Conversion strategy:
- Question Lean Code → Theorem declaration only (imports, setup, theorem with ':= by')
- Answer Lean Code → Complete theorem with proof (from problem + solution)
- Combined → Returns answer_lean if available, otherwise question_lean

This approach ensures:
1. question_lean_code can be displayed as the formalized problem statement
2. answer_lean_code is a complete, verifiable Lean formalization
3. Frontend can display both separately for clarity
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
            # Import sanitize function
            from ..utils.prompts import sanitize_theorem_name

            # Use preprocessed content if available
            body = status.get('preprocessed_body') or question['body']
            answer = status.get('preprocessed_answer')
            theorem_name = status.get('theorem_name') or sanitize_theorem_name(question['title'])

            # Convert question to Lean
            question_lean = self._convert_question_to_lean(theorem_name, body)

            # Convert answer to Lean if available
            answer_lean = None
            if answer:
                answer_lean = self._convert_answer_to_lean(theorem_name, body, answer)

            # Combine question and answer Lean code (for backward compatibility)
            combined_lean = self._combine_lean_code(question_lean, answer_lean)

            # Update processing status - store separately
            self.db.update_processing_status(
                question_internal_id,
                status='lean_converted',
                question_lean_code=question_lean,
                answer_lean_code=answer_lean,
                lean_code=combined_lean,  # Keep for backward compatibility
                processing_completed_at=self._now()
            )

            return {
                'success': True,
                'question_lean_code': question_lean,
                'answer_lean_code': answer_lean,
                'lean_code': combined_lean,  # For backward compatibility
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
        Convert a question to Lean 4 theorem declaration (without proof).

        Args:
            title: Theorem name (from preprocessing)
            body: Question body

        Returns:
            Lean 4 code for the question
        """
        problem_text = f"{body}"

        if title.strip() == "":
            title = "my_declaration"

        prompt = f"Use the following theorem names: {title}.\n\n{problem_text}"

        lean_code = self.client.convert_to_lean(
            problem_text=prompt,
            max_tokens=4096,
            temperature=0.6
        )

        # Post-process: extract only the Lean code, remove prompt text
        lean_code = self._extract_lean_code(lean_code)

        return lean_code

    def _convert_answer_to_lean(self, title: str, body: str, answer: str) -> str:
        """
        Convert a problem + solution to a complete Lean 4 theorem with proof.

        Args:
            title: Theorem name (from preprocessing)
            body: Question body
            answer: Answer text

        Returns:
            Complete Lean 4 code with theorem declaration AND proof
        """
        # Combine problem and solution
        problem_text = f"{body}\n\n{answer}"

        if title.strip() == "":
            title = "my_theorem"

        prompt = f"Use the following theorem names: {title}.\n\n{problem_text}"

        lean_code = self.client.convert_to_lean(
            problem_text=prompt,
            max_tokens=4096,  # More tokens for complete theorem + proof
            temperature=0.6
        )

        # Post-process: extract only the Lean code, remove prompt text
        lean_code = self._extract_lean_code(lean_code)

        return lean_code

    def _combine_lean_code(self, question_lean: str, answer_lean: str = None) -> str:
        """
        Combine question and answer Lean code.

        Args:
            question_lean: Lean code for question (theorem declaration only, ends with ':= by')
            answer_lean: Lean code for answer (complete theorem with proof), if available

        Returns:
            Combined Lean 4 code (answer_lean if available, otherwise question_lean)
        """
        if answer_lean:
            # answer_lean is already complete (theorem + proof from problem + solution)
            return answer_lean
        else:
            # Only have question (theorem declaration without proof)
            return question_lean

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

    def _extract_lean_code(self, raw_output: str) -> str:
        """
        Extract pure Lean code from LLM output, removing prompt text and comments.

        Args:
            raw_output: Raw LLM output that may contain prompt text

        Returns:
            Cleaned Lean code
        """
        if not raw_output:
            return raw_output

        lines = raw_output.split('\n')

        # Remove leading blank lines and prompt text
        # Find the first real Lean code line
        start_idx = 0
        found_code = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Check if this looks like prompt text (common patterns)
            if any(prompt_marker in stripped for prompt_marker in [
                'Convert the following',
                'Focus on formalizing',
                'Provide the Lean',
                'Problem:',
                'Solution/Proof:',
                'mathematical problem',
                'mathematical solution'
            ]):
                continue

            # Check if line starts with Lean keyword or symbol
            if stripped.startswith('import ') or \
               stripped.startswith('open ') or \
               stripped.startswith('theorem ') or \
               stripped.startswith('definition ') or \
               stripped.startswith('lemma ') or \
               stripped.startswith('example ') or \
               stripped.startswith('def ') or \
               stripped.startswith('structure ') or \
               stripped.startswith('class ') or \
               stripped.startswith('inductive ') or \
               stripped.startswith('axiom ') or \
               stripped.startswith('variable') or \
               stripped.startswith('universe'):
                start_idx = i
                found_code = True
                break

            # Also allow multiline comment starts that might contain code
            if stripped.startswith('/-'):
                # Check next few lines for actual code
                for j in range(i+1, min(i+10, len(lines))):
                    if any(lines[j].strip().startswith(kw) for kw in ['import ', 'theorem ', 'lemma ', 'def ']):
                        start_idx = i
                        found_code = True
                        break
                if found_code:
                    break

        # If no clear code start found, look for first non-trivial line
        if not found_code:
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('-') and not any(m in stripped for m in ['Convert', 'Focus', 'Provide', 'Problem:', 'Solution']):
                    start_idx = i
                    break

        # Extract from start_idx
        lean_code = '\n'.join(lines[start_idx:])

        # Remove prompt-containing multiline comments
        # Look for /- ... -/ blocks that contain prompt text
        prompt_markers = [
            'Convert the following',
            'Focus on formalizing',
            'Provide the Lean',
            'Problem:',
            'Solution/Proof:'
        ]

        # Find and remove comment blocks with prompt text
        lines_after_extract = lean_code.split('\n')
        cleaned_lines = []
        in_prompt_comment = False

        for line in lines_after_extract:
            # Check if we're entering a prompt comment
            if '/-' in line:
                # Check if this comment or the next few lines contain prompt markers
                comment_text = line
                # Look ahead for prompt markers in this comment block
                temp_idx = lines_after_extract.index(line)
                for j in range(temp_idx, min(temp_idx + 20, len(lines_after_extract))):
                    comment_text += lines_after_extract[j]
                    if '-/' in lines_after_extract[j]:
                        break

                if any(marker in comment_text for marker in prompt_markers):
                    in_prompt_comment = True
                    # Skip this comment line
                    if '-/' in line:
                        in_prompt_comment = False
                    continue

            # Skip lines while in prompt comment
            if in_prompt_comment:
                if '-/' in line:
                    in_prompt_comment = False
                continue

            cleaned_lines.append(line)

        lean_code = '\n'.join(cleaned_lines)

        return lean_code.strip()

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
