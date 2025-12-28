"""
Unit tests for Lean verification functionality.
"""
import json
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from backend.processing.lean_verifier import (
    LeanVerifier,
    VerificationResult,
    VerificationMessage
)
from backend.database import DatabaseManager


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_from_kimina_response_success_no_messages(self):
        """Test parsing successful response with no messages."""
        response_data = {
            'results': [
                {
                    'time': 1.5,
                    'response': {
                        'messages': []
                    }
                }
            ]
        }

        result = VerificationResult.from_kimina_response(response_data)

        assert result.success == True
        assert result.has_errors == False
        assert result.has_warnings == False
        assert len(result.messages) == 0
        assert result.total_time == 1.5

    def test_from_kimina_response_with_errors(self):
        """Test parsing response with error messages."""
        response_data = {
            'results': [
                {
                    'time': 0.5,
                    'response': {
                        'messages': [
                            {
                                'severity': 'error',
                                'pos': {'line': 5, 'column': 10},
                                'endPos': {'line': 5, 'column': 15},
                                'data': 'type mismatch'
                            },
                            {
                                'severity': 'error',
                                'pos': {'line': 7, 'column': 3},
                                'endPos': {'line': 7, 'column': 8},
                                'data': 'unknown identifier'
                            }
                        ]
                    }
                }
            ]
        }

        result = VerificationResult.from_kimina_response(response_data)

        assert result.success == False
        assert result.has_errors == True
        assert result.has_warnings == False
        assert len(result.messages) == 2
        assert result.messages[0].severity == 'error'
        assert result.messages[0].line == 5
        assert result.messages[0].message == 'type mismatch'
        assert result.total_time == 0.5

    def test_from_kimina_response_with_warnings(self):
        """Test parsing response with warning messages."""
        response_data = {
            'results': [
                {
                    'time': 1.0,
                    'response': {
                        'messages': [
                            {
                                'severity': 'warning',
                                'pos': {'line': 3, 'column': 1},
                                'endPos': {'line': 3, 'column': 20},
                                'data': 'deprecated theorem'
                            }
                        ]
                    }
                }
            ]
        }

        result = VerificationResult.from_kimina_response(response_data)

        assert result.success == True
        assert result.has_errors == False
        assert result.has_warnings == True
        assert len(result.messages) == 1
        assert result.messages[0].severity == 'warning'
        assert result.messages[0].message == 'deprecated theorem'

    def test_from_kimina_response_mixed_severity(self):
        """Test parsing response with both errors and warnings."""
        response_data = {
            'results': [
                {
                    'time': 2.0,
                    'response': {
                        'messages': [
                            {
                                'severity': 'warning',
                                'pos': {'line': 1, 'column': 1},
                                'endPos': {'line': 1, 'column': 10},
                                'data': 'unused variable'
                            },
                            {
                                'severity': 'error',
                                'pos': {'line': 5, 'column': 5},
                                'endPos': {'line': 5, 'column': 12},
                                'data': 'type error'
                            }
                        ]
                    }
                }
            ]
        }

        result = VerificationResult.from_kimina_response(response_data)

        assert result.success == False
        assert result.has_errors == True
        assert result.has_warnings == True
        assert len(result.messages) == 2

    def test_from_kimina_response_multiple_results(self):
        """Test parsing response with multiple result entries."""
        response_data = {
            'results': [
                {'time': 1.0, 'response': {'messages': []}},
                {'time': 0.5, 'response': {'messages': []}},
                {'time': 0.3, 'response': {'messages': []}}
            ]
        }

        result = VerificationResult.from_kimina_response(response_data)

        assert result.total_time == 1.8  # Sum of all times

    def test_from_kimina_response_missing_position(self):
        """Test parsing message with missing position data."""
        response_data = {
            'results': [
                {
                    'time': 0.1,
                    'response': {
                        'messages': [
                            {
                                'severity': 'info',
                                'data': 'general information'
                            }
                        ]
                    }
                }
            ]
        }

        result = VerificationResult.from_kimina_response(response_data)

        assert len(result.messages) == 1
        assert result.messages[0].line == 0
        assert result.messages[0].column == 0

    def test_from_kimina_response_missing_end_position(self):
        """Test parsing message with missing end position."""
        response_data = {
            'results': [
                {
                    'time': 0.1,
                    'response': {
                        'messages': [
                            {
                                'severity': 'error',
                                'pos': {'line': 10, 'column': 5},
                                'data': 'syntax error'
                            }
                        ]
                    }
                }
            ]
        }

        result = VerificationResult.from_kimina_response(response_data)

        assert result.messages[0].end_line == 10  # Should default to line
        assert result.messages[0].end_column == 5  # Should default to column


class TestLeanVerifier:
    """Test LeanVerifier class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database manager."""
        db = Mock(spec=DatabaseManager)
        return db

    @pytest.fixture
    def verifier(self, mock_db):
        """Create a LeanVerifier instance."""
        return LeanVerifier(db_manager=mock_db, kimina_url="http://127.0.0.1:9000")

    @pytest.fixture
    def mock_kimina_response(self):
        """Create a mock kimina client response."""
        def _make_response(results):
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {'results': results}
            return mock_response
        return _make_response

    @pytest.fixture
    def mock_kimina_client(self, mock_kimina_response):
        """Create a mock kimina client."""
        def _make_client(results):
            mock_response = mock_kimina_response(results)
            mock_client = MagicMock()
            mock_client.check.return_value = mock_response
            return mock_client
        return _make_client

    def test_init_default_url(self, mock_db):
        """Test initialization with default URL."""
        verifier = LeanVerifier(db_manager=mock_db)
        assert verifier.kimina_url == "http://127.0.0.1:9000"

    def test_init_custom_url(self, mock_db):
        """Test initialization with custom URL."""
        verifier = LeanVerifier(
            db_manager=mock_db,
            kimina_url="http://localhost:8000"
        )
        assert verifier.kimina_url == "http://localhost:8000"

    def test_init_url_stripped(self, mock_db):
        """Test that trailing slash is stripped from URL."""
        verifier = LeanVerifier(
            db_manager=mock_db,
            kimina_url="http://127.0.0.1:9000/"
        )
        assert verifier.kimina_url == "http://127.0.0.1:9000"

    def _setup_kimina_mock(self, mock_client):
        """Helper to setup kimina mock in sys.modules."""
        mock_kimina_module = MagicMock()
        mock_kimina_module.KiminaClient = Mock(return_value=mock_client)
        sys.modules['kimina_client'] = mock_kimina_module
        return mock_kimina_module

    def _teardown_kimina_mock(self):
        """Helper to remove kimina mock from sys.modules."""
        if 'kimina_client' in sys.modules:
            del sys.modules['kimina_client']

    def test_verify_question_success_passed(self, verifier, mock_db, mock_kimina_client):
        """Test successful verification with no issues."""
        mock_db.get_question.return_value = {
            'id': 1,
            'title': 'Test Question',
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': 'theorem test : True := by trivial',
                'lean_code': 'theorem test : True := by trivial'
            }
        }

        mock_client = mock_kimina_client([{'time': 1.5, 'response': {'messages': []}}])
        self._setup_kimina_mock(mock_client)

        try:
            result = verifier.verify_question(question_internal_id=1)

            assert result['success'] == True
            assert result['verification_status'] == 'passed'
            assert result['has_errors'] == False
            assert result['has_warnings'] == False
            assert result['message_count'] == 0
            assert result['total_time'] == 1.5

            calls = mock_db.update_processing_status.call_args_list
            assert calls[0][1]['verification_status'] == 'verifying'
            assert calls[1][1]['verification_status'] == 'passed'
        finally:
            self._teardown_kimina_mock()

    def test_verify_question_with_warnings(self, verifier, mock_db, mock_kimina_client):
        """Test verification with warnings."""
        mock_db.get_question.return_value = {
            'id': 2,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': 'theorem test : Prop := by sorry'
            }
        }

        mock_client = mock_kimina_client([{
            'time': 1.0,
            'response': {
                'messages': [
                    {
                        'severity': 'warning',
                        'pos': {'line': 1, 'column': 1},
                        'endPos': {'line': 1, 'column': 25},
                        'data': 'used sorry'
                    }
                ]
            }
        }])
        self._setup_kimina_mock(mock_client)

        try:
            result = verifier.verify_question(question_internal_id=2)

            assert result['success'] == True
            assert result['verification_status'] == 'warning'
            assert result['has_warnings'] == True
            assert result['message_count'] == 1
        finally:
            self._teardown_kimina_mock()

    def test_verify_question_with_errors(self, verifier, mock_db, mock_kimina_client):
        """Test verification with errors."""
        mock_db.get_question.return_value = {
            'id': 3,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': 'theorem test : Type := by nonsense'
            }
        }

        mock_client = mock_kimina_client([{
            'time': 0.5,
            'response': {
                'messages': [
                    {
                        'severity': 'error',
                        'pos': {'line': 1, 'column': 25},
                        'endPos': {'line': 1, 'column': 33},
                        'data': 'unknown identifier nonsense'
                    }
                ]
            }
        }])
        self._setup_kimina_mock(mock_client)

        try:
            result = verifier.verify_question(question_internal_id=3)

            assert result['success'] == True
            assert result['verification_status'] == 'failed'
            assert result['has_errors'] == True
            assert result['message_count'] == 1
        finally:
            self._teardown_kimina_mock()

    def test_verify_question_not_found(self, verifier, mock_db):
        """Test verifying a non-existent question."""
        mock_db.get_question.return_value = None

        with pytest.raises(ValueError, match="Question 999 not found"):
            verifier.verify_question(question_internal_id=999)

    def test_verify_question_wrong_status(self, verifier, mock_db):
        """Test verifying a question that hasn't been converted to Lean."""
        mock_db.get_question.return_value = {
            'id': 4,
            'processing_status': {
                'status': 'preprocessed'
            }
        }

        with pytest.raises(ValueError, match="not in lean_converted status"):
            verifier.verify_question(question_internal_id=4)

    def test_verify_question_no_lean_code(self, verifier, mock_db):
        """Test verifying a question with no Lean code."""
        mock_db.get_question.return_value = {
            'id': 5,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': None,
                'lean_code': ''
            }
        }

        with pytest.raises(ValueError, match="has no Lean code to verify"):
            verifier.verify_question(question_internal_id=5)

    def test_verify_question_fallback_to_lean_code(self, verifier, mock_db, mock_kimina_client):
        """Test that lean_code field is used when question_lean_code is missing."""
        mock_db.get_question.return_value = {
            'id': 6,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': None,
                'lean_code': 'theorem test : True := by trivial'
            }
        }

        mock_client = mock_kimina_client([{'time': 1.0, 'response': {'messages': []}}])
        self._setup_kimina_mock(mock_client)

        try:
            result = verifier.verify_question(question_internal_id=6)

            assert result['success'] == True
            mock_client.check.assert_called_once()
            call_args = mock_client.check.call_args[0][0]
            assert 'theorem test : True := by trivial' in call_args
        finally:
            self._teardown_kimina_mock()

    def test_verify_question_connection_error(self, verifier, mock_db):
        """Test handling of connection errors."""
        mock_db.get_question.return_value = {
            'id': 7,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': 'theorem test : True := by trivial'
            }
        }

        mock_client_instance = MagicMock()
        mock_client_instance.check.side_effect = Exception("Connection refused")
        self._setup_kimina_mock(mock_client_instance)

        try:
            with pytest.raises(ConnectionError, match="Failed to connect to kimina-lean-server"):
                verifier.verify_question(question_internal_id=7)

            calls = mock_db.update_processing_status.call_args_list
            final_call = calls[-1]
            assert final_call[1]['verification_status'] == 'connection_error'
            assert 'verification_error' in final_call[1]
        finally:
            self._teardown_kimina_mock()

    def test_verify_question_kimina_not_installed(self, verifier, mock_db):
        """Test handling when kimina_client is not installed."""
        mock_db.get_question.return_value = {
            'id': 8,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': 'theorem test : True := by trivial'
            }
        }

        # Mock __import__ to raise ImportError for kimina_client
        real_import = __import__

        def custom_import(name, *args, **kwargs):
            if name == 'kimina_client':
                raise ImportError("No module named 'kimina_client'")
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=custom_import):
            with pytest.raises(ImportError, match="kimina_client not installed"):
                verifier.verify_question(question_internal_id=8)

    def test_verify_question_non_connection_error(self, verifier, mock_db):
        """Test handling of non-connection errors."""
        mock_db.get_question.return_value = {
            'id': 9,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': 'theorem test : True := by trivial'
            }
        }

        mock_client_instance = MagicMock()
        mock_client_instance.check.side_effect = ValueError("Invalid Lean syntax")
        self._setup_kimina_mock(mock_client_instance)

        try:
            with pytest.raises(ValueError, match="Invalid Lean syntax"):
                verifier.verify_question(question_internal_id=9)

            calls = mock_db.update_processing_status.call_args_list
            final_call = calls[-1]
            assert final_call[1]['verification_status'] == 'error'
        finally:
            self._teardown_kimina_mock()

    def test_is_connection_error(self, verifier):
        """Test connection error detection."""
        assert verifier._is_connection_error("Connection refused") == True
        assert verifier._is_connection_error("Request timeout") == True
        assert verifier._is_connection_error("Network unreachable") == True
        assert verifier._is_connection_error("ECONNREFUSED") == True
        assert verifier._is_connection_error("ETIMEDOUT") == True

        assert verifier._is_connection_error("Invalid syntax") == False
        assert verifier._is_connection_error("Type error") == False
        assert verifier._is_connection_error("ValueError: something") == False

    def test_verify_code_with_model_dump(self, verifier, mock_kimina_client):
        """Test _verify_code with model_dump method."""
        mock_client = mock_kimina_client([{'time': 1.0, 'response': {'messages': []}}])
        self._setup_kimina_mock(mock_client)

        try:
            result = verifier._verify_code('theorem test : True := by trivial')

            assert result.success == True
            assert result.total_time == 1.0
        finally:
            self._teardown_kimina_mock()

    def test_verify_code_with_dict_method(self, verifier):
        """Test _verify_code with dict method (older pydantic)."""
        mock_response = MagicMock()
        del mock_response.model_dump
        mock_response.dict.return_value = {
            'results': [{'time': 0.5, 'response': {'messages': []}}]
        }

        mock_client = MagicMock()
        mock_client.check.return_value = mock_response
        self._setup_kimina_mock(mock_client)

        try:
            result = verifier._verify_code('theorem test : True := by trivial')

            assert result.success == True
            assert result.total_time == 0.5
        finally:
            self._teardown_kimina_mock()

    def test_verify_code_fallback_no_methods(self, verifier):
        """Test _verify_code when response has neither model_dump nor dict."""
        # For this test, we patch json.dumps to avoid serialization issues
        # The test verifies that the fallback path can handle non-standard response objects
        class DictLikeResult:
            def __init__(self):
                self.time = 0.3
                self.response = {'messages': []}

            def get(self, key, default=None):
                if key == 'time':
                    return self.time
                elif key == 'response':
                    return self.response
                return default

        class SimpleResponse:
            def __init__(self):
                self.results = [DictLikeResult()]

        mock_response = SimpleResponse()

        mock_client = MagicMock()
        mock_client.check.return_value = mock_response
        self._setup_kimina_mock(mock_client)

        try:
            # Patch json.dumps to avoid serialization issues with custom objects
            with patch('json.dumps', return_value='{"mock": "response"}'):
                result = verifier._verify_code('theorem test : True := by trivial')

                # The fallback should work with dict-like objects
                assert isinstance(result, VerificationResult)
                assert result.success == True
                assert result.total_time == 0.3
        finally:
            self._teardown_kimina_mock()

    def test_verify_uses_correct_kimina_url(self, mock_db, mock_kimina_client):
        """Test that verifier uses the correct kimina URL."""
        custom_verifier = LeanVerifier(
            db_manager=mock_db,
            kimina_url="http://custom:8080"
        )

        mock_db.get_question.return_value = {
            'id': 10,
            'processing_status': {
                'status': 'lean_converted',
                'question_lean_code': 'theorem test : True := by trivial'
            }
        }

        mock_client = mock_kimina_client([{'time': 1.0, 'response': {'messages': []}}])
        mock_kimina_module = self._setup_kimina_mock(mock_client)

        try:
            custom_verifier.verify_question(question_internal_id=10)

            mock_kimina_module.KiminaClient.assert_called_once_with(api_url="http://custom:8080")
        finally:
            self._teardown_kimina_mock()

    def test_now_method(self, verifier):
        """Test _now method returns ISO format timestamp."""
        timestamp = verifier._now()
        assert isinstance(timestamp, str)
        assert 'T' in timestamp or len(timestamp) > 10


class TestVerificationMessage:
    """Test VerificationMessage dataclass."""

    def test_create_message(self):
        """Test creating a verification message."""
        msg = VerificationMessage(
            severity='error',
            line=5,
            column=10,
            end_line=5,
            end_column=20,
            message='type mismatch'
        )

        assert msg.severity == 'error'
        assert msg.line == 5
        assert msg.column == 10
        assert msg.end_line == 5
        assert msg.end_column == 20
        assert msg.message == 'type mismatch'

    def test_message_to_dict(self):
        """Test converting message to dict."""
        msg = VerificationMessage(
            severity='warning',
            line=1,
            column=1,
            end_line=2,
            end_column=10,
            message='deprecated'
        )

        msg_dict = msg.__dict__

        assert msg_dict == {
            'severity': 'warning',
            'line': 1,
            'column': 1,
            'end_line': 2,
            'end_column': 10,
            'message': 'deprecated'
        }


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
