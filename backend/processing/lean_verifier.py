"""
Lean verifier using kimina-lean-server.
Validates Lean 4 code for syntax and type errors.
"""
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from ..database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class VerificationMessage:
    """A message from Lean verification."""
    severity: str  # 'error', 'warning', 'info'
    line: int
    column: int
    end_line: int
    end_column: int
    message: str


@dataclass
class VerificationResult:
    """Result of Lean code verification."""
    success: bool
    has_errors: bool
    has_warnings: bool
    messages: List[VerificationMessage]
    total_time: float
    raw_response: str = ""

    @classmethod
    def from_kimina_response(cls, response_data: Dict) -> 'VerificationResult':
        """Create VerificationResult from kimina-lean-server response.

        Response format when verification passes:
        {
          "results": [{
            "id": "...",
            "time": 0.047723,
            "response": {"env": 2}  # Only 'env' field means success, no errors/warnings
          }]
        }

        Response format with errors/warnings:
        {
          "results": [{
            "response": {
              "env": 2,
              "messages": [
                {"severity": "error", "pos": {...}, "endPos": {...}, "data": "error message"}
              ]
            }
          }]
        }
        """
        messages = []
        has_errors = False
        has_warnings = False

        for result in response_data.get('results', []):
            resp = result.get('response', {})

            # If response only has 'env' field (e.g., {"env": 2}), verification passed
            # No errors or warnings
            if 'messages' not in resp:
                logger.debug(f"Verification passed: response only contains 'env' field: {resp}")
                continue

            # Process messages if present
            for msg in resp.get('messages', []):
                severity = msg.get('severity', 'info')
                pos = msg.get('pos', {})
                end_pos = msg.get('endPos', {})

                if severity == 'error':
                    has_errors = True
                elif severity == 'warning':
                    has_warnings = True

                messages.append(VerificationMessage(
                    severity=severity,
                    line=pos.get('line', 0),
                    column=pos.get('column', 0),
                    end_line=end_pos.get('line', pos.get('line', 0)),
                    end_column=end_pos.get('column', pos.get('column', 0)),
                    message=msg.get('data', '')
                ))

        success = not has_errors
        total_time = sum(r.get('time', 0) for r in response_data.get('results', []))

        return cls(
            success=success,
            has_errors=has_errors,
            has_warnings=has_warnings,
            messages=messages,
            total_time=total_time,
            raw_response=json.dumps(response_data, indent=2)
        )


class LeanVerifier:
    """Verify Lean 4 code using kimina-lean-server."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        kimina_url: str = "http://127.0.0.1:9000"
    ):
        """
        Initialize Lean verifier.

        Args:
            db_manager: Database manager instance
            kimina_url: URL of kimina-lean-server
        """
        self.db = db_manager
        self.kimina_url = kimina_url.rstrip('/')
        self.timeout = 60  # seconds

    def verify_question(self, question_internal_id: int) -> Dict[str, Any]:
        """
        Verify Lean code for a question.

        Args:
            question_internal_id: Internal database question ID

        Returns:
            Verification result
        """
        # Get question
        question = self.db.get_question(question_internal_id)
        if not question:
            raise ValueError(f"Question {question_internal_id} not found")

        # Check if Lean code exists
        status = question.get('processing_status', {})
        current_status = status.get('status')

        if current_status != 'lean_converted':
            raise ValueError(f"Question {question_internal_id} is not in lean_converted status (current: {current_status})")

        # Get Lean code
        lean_code = status.get('question_lean_code') or status.get('lean_code', '')
        if not lean_code:
            raise ValueError(f"Question {question_internal_id} has no Lean code to verify")

        # Update status to verifying
        self.db.update_processing_status(
            question_internal_id,
            verification_status='verifying',
            verification_started_at=self._now()
        )

        try:
            # Verify the code
            result = self._verify_code(lean_code)

            # Determine overall status
            if result.has_errors:
                verification_status = 'failed'
            elif result.has_warnings:
                verification_status = 'warning'
            else:
                verification_status = 'passed'

            # Update database with verification results
            self.db.update_processing_status(
                question_internal_id,
                verification_status=verification_status,
                verification_has_errors=result.has_errors,
                verification_has_warnings=result.has_warnings,
                verification_messages=json.dumps([m.__dict__ for m in result.messages]),
                verification_time=result.total_time,
                verification_completed_at=self._now()
            )

            return {
                'success': True,
                'verification_status': verification_status,
                'has_errors': result.has_errors,
                'has_warnings': result.has_warnings,
                'message_count': len(result.messages),
                'total_time': result.total_time,
                'messages': [m.__dict__ for m in result.messages]
            }

        except Exception as e:
            error_msg = str(e)
            is_connection_error = self._is_connection_error(error_msg)

            if is_connection_error:
                # Connection error - mark as failed but retryable
                verification_status = 'connection_error'
            else:
                verification_status = 'error'

            self.db.update_processing_status(
                question_internal_id,
                verification_status=verification_status,
                verification_error=error_msg,
                verification_completed_at=self._now()
            )

            if is_connection_error:
                raise ConnectionError(f"Failed to connect to kimina-lean-server: {error_msg}")
            else:
                raise

    def verify_conversion_result(self, result_id: int) -> Dict[str, Any]:
        """
        Verify Lean code for a specific conversion result.

        Args:
            result_id: Lean conversion result ID

        Returns:
            Verification result
        """
        from ..database import LeanConversionResult

        # Get conversion result
        session = self.db.get_session()
        try:
            result = session.query(LeanConversionResult).filter(
                LeanConversionResult.id == result_id
            ).first()

            if not result:
                raise ValueError(f"Conversion result {result_id} not found")

            # Get the Lean code to verify (prefer answer_lean_code, fallback to question_lean_code)
            lean_code = result.answer_lean_code or result.question_lean_code
            if not lean_code:
                raise ValueError(f"Conversion result {result_id} has no Lean code to verify")

            # Mark as verifying
            result.verification_status = 'verifying'
            session.commit()
        finally:
            session.close()

        try:
            # Verify the code
            verification_result = self._verify_code(lean_code)

            # Determine overall status
            if verification_result.has_errors:
                verification_status = 'failed'
            elif verification_result.has_warnings:
                verification_status = 'warning'
            else:
                verification_status = 'passed'

            # Update database with verification results
            self.db.update_lean_verification(
                result_id=result_id,
                verification_status=verification_status,
                has_errors=verification_result.has_errors,
                has_warnings=verification_result.has_warnings,
                messages=[m.__dict__ for m in verification_result.messages],
                verification_time=verification_result.total_time
            )

            return {
                'success': True,
                'result_id': result_id,
                'verification_status': verification_status,
                'has_errors': verification_result.has_errors,
                'has_warnings': verification_result.has_warnings,
                'message_count': len(verification_result.messages),
                'total_time': verification_result.total_time,
                'messages': [m.__dict__ for m in verification_result.messages]
            }

        except Exception as e:
            error_msg = str(e)
            is_connection_error = self._is_connection_error(error_msg)

            if is_connection_error:
                verification_status = 'connection_error'
            else:
                verification_status = 'error'

            # Update with error status
            session = self.db.get_session()
            try:
                result = session.query(LeanConversionResult).filter(
                    LeanConversionResult.id == result_id
                ).first()
                if result:
                    result.verification_status = verification_status
                    session.commit()
            finally:
                session.close()

            if is_connection_error:
                raise ConnectionError(f"Failed to connect to kimina-lean-server: {error_msg}")
            else:
                raise

    def _verify_code(self, lean_code: str) -> VerificationResult:
        """
        Verify Lean code using kimina-lean-server.

        Args:
            lean_code: Lean 4 code to verify

        Returns:
            VerificationResult
        """
        # Import kimina_client
        try:
            from kimina_client import KiminaClient
        except ImportError:
            raise ImportError(
                "kimina_client not installed. "
                "Install it with: pip install kimina-client"
            )

        # Create client and check
        client = KiminaClient(api_url=self.kimina_url)

        try:
            response = client.check(lean_code)

            # Parse response
            # The kimina_client returns a CheckResponse object
            # We need to convert it to dict
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            elif hasattr(response, 'dict'):
                response_dict = response.dict()
            else:
                # Fallback: try to extract results
                response_dict = {'results': []}
                if hasattr(response, 'results'):
                    for r in response.results:
                        if hasattr(r, 'model_dump'):
                            response_dict['results'].append(r.model_dump())
                        elif hasattr(r, 'dict'):
                            response_dict['results'].append(r.dict())
                        else:
                            response_dict['results'].append(r)

            return VerificationResult.from_kimina_response(response_dict)

        except Exception as e:
            logger.error(f"Kimina verification error: {e}")
            raise

    def _is_connection_error(self, error_msg: str) -> bool:
        """Check if error is a connection error."""
        connection_keywords = [
            'connection',
            'timeout',
            'refused',
            'unreachable',
            'network',
            'ECONNREFUSED',
            'ETIMEDOUT'
        ]
        error_msg_lower = error_msg.lower()
        return any(kw.lower() in error_msg_lower for kw in connection_keywords)

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
