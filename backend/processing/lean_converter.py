"""
Lean converter using Kimina-Autoformalizer-7B via VLLM and GLM-based LLM agent.

Conversion strategy:
- Question Lean Code → Theorem declaration only (imports, setup, theorem with ':= by')
- Answer Lean Code → Complete theorem with proof (from problem + solution)
- Combined → Returns answer_lean if available, otherwise question_lean

This approach ensures:
1. question_lean_code can be displayed as the formalized problem statement
2. answer_lean_code is a complete, verifiable Lean formalization
3. Frontend can display both separately for clarity
"""
from typing import Dict, Any, List, Tuple
import logging

from ..database import DatabaseManager
from ..utils import VLLMClient, ZhipuClient
from ..utils.prompts import (
    LEAN_QUESTION_PROMPT,
    LEAN_WITH_ANSWER_PROMPT,
    LEAN_CORRECTION_PROMPT,
    sanitize_theorem_name
)

logger = logging.getLogger(__name__)


class LeanConverter:
    """Convert mathematical problems to Lean 4 using Kimina-Autoformalizer-7B."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        vllm_base_url: str = "http://localhost:8000/v1",
        model_path: str = "/root/Kimina-Autoformalizer-7B",
        converter_name: str = "Kimina-Legacy"
        # TODO: add max_tokens
    ):
        """
        Initialize Lean converter.

        Args:
            db_manager: Database manager instance
            vllm_base_url: VLLM server base URL
            model_path: Model path/name
            converter_name: Name of this converter for tracking
        """
        self.db = db_manager
        self.converter_name = converter_name
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
            theorem_name = status.get('theorem_name') or sanitize_theorem_name(question['title'])

            # Convert question to Lean
            question_lean = self._convert_question_to_lean(theorem_name, body)

            # Convert answer to Lean if available
            answer_lean = None
            if answer:
                answer_lean = self._convert_answer_to_lean(theorem_name, body, answer)

            # Combine question and answer Lean code (for backward compatibility)
            combined_lean = self._combine_lean_code(question_lean, answer_lean)

            # Store in lean_conversion_results table
            self.db.save_lean_conversion_result(
                question_id=question_internal_id,
                converter_name=self.converter_name,
                converter_type='kimina_vllm',
                question_lean_code=question_lean,
                answer_lean_code=answer_lean,
                conversion_time=0.0,  # TODO: track actual time
                error_message=None
            )

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
            # Log error but don't change status - record in lean_error field only
            error_msg = str(e)
            logger.error(f"Lean conversion error for question {question_internal_id}: {error_msg}")

            # Keep status as 'preprocessed', just record the error
            # This allows users to see the error in the UI without marking the question as failed
            self.db.update_processing_status(
                question_internal_id,
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


class LLMLeanConverter:
    """Convert mathematical problems to Lean 4 using GLM LLM with iterative correction."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        api_key: str,
        model: str = "glm-4.7",
        kimina_url: str = "http://127.0.0.1:9000",
        max_iterations: int = 1,
        temperature: float = 0.2,
        max_tokens: int = 16000,
        converter_name: str = None
    ):
        """
        Initialize LLM Lean converter.

        Args:
            db_manager: Database manager instance
            api_key: Zhipu AI API key
            model: Model name (default: glm-4.7)
            kimina_url: Lean verification server URL
            max_iterations: Maximum correction iterations
            temperature: LLM temperature
            max_tokens: Maximum tokens for generation
            converter_name: Name of this converter for tracking (auto-generated if None)
        """
        self.db = db_manager
        self.client = ZhipuClient(api_key=api_key)
        self.model = model
        self.kimina_url = kimina_url
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        # Auto-generate converter_name if not provided
        self.converter_name = converter_name or f"glm-{self.model.replace('.', '-')}"

    def convert_question(self, question_internal_id: int) -> Dict[str, Any]:
        """
        Convert a question and its answer to Lean 4 with iterative correction.

        Args:
            question_internal_id: Internal database question ID

        Returns:
            Conversion result with verification status
        """
        # Get question
        question = self.db.get_question(question_internal_id)
        if not question:
            raise ValueError(f"Question {question_internal_id} not found")

        # Check if preprocessed
        status = question.get('processing_status', {})
        current_status = status.get('status')

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
            theorem_name = status.get('theorem_name') or sanitize_theorem_name(question['title'])

            # Convert question to Lean (with sorry)
            question_lean = self._convert_with_correction(
                theorem_name=theorem_name,
                body=body,
                answer=None,
                lean_type="question"
            )

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

            # Store in lean_conversion_results table
            self.db.save_lean_conversion_result(
                question_id=question_internal_id,
                converter_name=self.converter_name,
                converter_type='api_llm',
                question_lean_code=question_lean,
                answer_lean_code=answer_lean,
                conversion_time=0.0,  # TODO: track actual time
                error_message=None
            )

            # Update processing status
            self.db.update_processing_status(
                question_internal_id,
                status='lean_converted',
                question_lean_code=question_lean,
                answer_lean_code=answer_lean,
                processing_completed_at=self._now()
            )

            # Update verification status if available
            if verification_result:
                self.db.update_lean_verification(
                    result_id=question_internal_id,  # Need to get actual result_id
                    verification_status=verification_result['status'],
                    has_errors=verification_result.get('has_errors', False),
                    has_warnings=verification_result.get('has_warnings', False),
                    messages=verification_result.get('messages', []),
                    verification_time=verification_result.get('time', 0)
                )

            return {
                'success': True,
                'question_lean_code': question_lean,
                'answer_lean_code': answer_lean,
                'has_answer': answer_lean is not None,
                'converter_name': self.converter_name,
                'verification': verification_result
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM Lean conversion error for question {question_internal_id}: {error_msg}")

            # Don't change status to 'failed' - just record error in lean_error field
            # Keep status as 'preprocessed' so the question remains usable
            self.db.update_processing_status(
                question_internal_id,
                lean_error=f"LLM Lean conversion error: {error_msg}",
                processing_completed_at=self._now()
            )
            raise

    def _convert_with_correction(
        self,
        theorem_name: str,
        body: str,
        answer: str = None,
        lean_type: str = "question"
    ) -> Dict[str, Any]:
        """
        Convert to Lean with iterative correction.

        Args:
            theorem_name: Name for the theorem
            body: Problem statement
            answer: Solution (optional)
            lean_type: "question" for sorry-only, "answer" for full proof

        Returns:
            Dict with lean_code and verification result
        """
        # Generate initial Lean code
        if lean_type == "question" or answer is None:
            prompt = LEAN_QUESTION_PROMPT.replace('{problem}', body)
        else:
            prompt = LEAN_WITH_ANSWER_PROMPT.replace('{problem}', body).replace('{answer}', answer)

        prompt += f"\n\nUse the theorem name: {theorem_name}"

        current_lean = self._call_llm(prompt)
        iteration = 0

        # Iterative correction
        while iteration < self.max_iterations:
            # Verify current Lean code
            verification = self._verify_lean_code(current_lean)

            # If passed or has only warnings, we're done
            if verification['status'] in ['passed', 'warning']:
                logger.info(f"Lean verification {verification['status']} after {iteration} iterations")
                break

            # If no errors (or max iterations reached), stop
            if not verification.get('has_errors') or iteration >= self.max_iterations - 1:
                logger.info(f"Stopping after {iteration + 1} iterations (max: {self.max_iterations})")
                break

            # Generate correction prompt
            error_message = self._format_error_message(verification.get('messages', []))
            correction_prompt = LEAN_CORRECTION_PROMPT.replace('{previous_lean}', current_lean).replace('{error_message}', error_message)

            # Get corrected code
            try:
                current_lean = self._call_llm(correction_prompt)
                iteration += 1
                logger.info(f"Iteration {iteration}: Correcting Lean code")
            except Exception as e:
                logger.error(f"Error during correction iteration {iteration}: {e}")
                break

        return {
            'lean_code': current_lean,
            'verification': verification,
            'iterations': iteration + 1
        }

    def _call_llm(self, prompt: str) -> str:
        """Call GLM API to generate Lean code."""
        response = self.client.chat_completion(
            messages=[
                {"role": "system", "content": "You are an expert Lean 4 formalizer. Output only valid Lean 4 code without explanations."},
                {"role": "user", "content": prompt}
            ],
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        # Extract content from response dict
        if isinstance(response, dict):
            if 'choices' in response and len(response['choices']) > 0:
                content = response['choices'][0].get('message', {}).get('content', '')
            else:
                content = str(response)
        else:
            content = str(response)

        # Extract Lean code from response
        lean_code = self._extract_lean_code(content)
        return lean_code

    def _verify_lean_code(self, lean_code: str) -> Dict[str, Any]:
        """
        Verify Lean code using Kimina verifier.

        Args:
            lean_code: Lean 4 code to verify

        Returns:
            Verification result dict
        """
        try:
            from kimina_client import KiminaClient

            client = KiminaClient(api_url=self.kimina_url)
            response = client.check(lean_code, show_progress=False)

            # Parse KiminaClient response
            # env: nevermind
            # messages_raw: nevermind if not exist(Passed).
            # severity - info, warning: passed with minor issue.
            # severity - error: not passed.
            if not response.results or len(response.results) == 0:
                return {
                    'status': 'error',
                    'messages': [{'severity': 'error', 'line': 0, 'message': 'No response from verifier'}],
                    'has_errors': True,
                    'has_warnings': False,
                    'time': 0.0
                }

            result = response.results[0]
            resp_data = result.response
            # env = resp_data.get('env', 0)
            messages_raw = resp_data.get('messages', [])
            verification_time = result.time

            # Map env to status
            if len(messages_raw) == 0:  # Passed
                status = 'passed'
                has_errors = False
                has_warnings = False
            else:
                # Unknown env value, check messages
                has_errors = any(msg.get('severity') == 'error' for msg in messages_raw)
                has_warnings = any(msg.get('severity') == 'warning' for msg in messages_raw)
                status = 'error' if has_errors else ('warning' if has_warnings else 'passed')

            # Parse messages into our format
            messages = []
            for msg in messages_raw:
                severity = msg.get('severity', 'error')
                pos = msg.get('pos', {})
                line = pos.get('line', 0)
                message_text = msg.get('data', 'Unknown error')

                messages.append({
                    'severity': severity,
                    'line': line,
                    'message': message_text
                })

            return {
                'status': status,
                'messages': messages,
                'has_errors': has_errors,
                'has_warnings': has_warnings,
                'time': verification_time
            }

        except ImportError:
            logger.error("kimina_client not installed. Install with: pip install kimina-client")
            return {
                'status': 'error',
                'messages': [{'severity': 'error', 'line': 0, 'message': 'kimina_client not installed'}],
                'has_errors': True,
                'has_warnings': False,
                'time': 0.0
            }
        except Exception as e:
            logger.error(f"Lean verification error: {e}")
            return {
                'status': 'error',
                'messages': [{'severity': 'error', 'line': 0, 'message': str(e)}],
                'has_errors': True,
                'has_warnings': False,
                'time': 0.0
            }

    def _format_error_message(self, messages: List[Dict]) -> str:
        """Format error messages for correction prompt."""
        if not messages:
            return "No specific errors provided."

        formatted = []
        for msg in messages:
            if msg.get('severity') == 'error':
                line = msg.get('line', '?')
                message = msg.get('message', 'Unknown error')
                formatted.append(f"Line {line}: {message}")

        return '\n'.join(formatted) if formatted else "No errors to fix."

    def _extract_lean_code(self, response: str) -> str:
        """Extract Lean code from LLM response."""
        if not response:
            return ""

        # Find code blocks
        import re
        code_blocks = re.findall(r'```lean\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()

        # Try generic code blocks
        code_blocks = re.findall(r'```\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()

        # Return as-is if no blocks found
        return response.strip()

    def _is_program_error(self, error_msg: str) -> bool:
        """Determine if error is program error (retryable)."""
        program_error_keywords = [
            'timeout',
            'connection',
            'network',
            'API',
            'zhipu',
            'zai-sdk',
            'rate limit',
            '429',
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
