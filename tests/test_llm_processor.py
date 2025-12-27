"""
Unit tests for LLM preprocessing functionality.
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.utils.llm_client import ZhipuClient
from backend.processing.llm_processor import LLMProcessor
from backend.database import DatabaseManager


class TestJSONEscapeFixing:
    """Test the JSON escape fixing logic."""

    def test_fix_json_escapes_valid_escapes(self):
        """Test that valid JSON escapes are preserved."""
        client = ZhipuClient(api_key="test_key")

        # Mock the API response
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"text": "Hello\\nWorld", "quote": "\\"test\\""}'
                }
            }]
        }

        with patch.object(client, 'chat_completion', return_value=mock_response):
            result = client.correct_content(question="Test", answer="Test")
            assert result is not None

    def test_fix_json_escapes_latex_backslash(self):
        """Test that LaTeX backslashes are handled correctly."""
        client = ZhipuClient(api_key="test_key")

        # This simulates a response with LaTeX escapes
        # Use raw string to avoid Python interpreting backslashes
        content = r'''{
  "is_valid_question": true,
  "corrected_question": "Test $\frac{1}{2}$ with \\mathbb{R}",
  "corrected_answer": "Answer with \(x^2\)"
}'''

        mock_response = {
            "choices": [{
                "message": {
                    "content": content
                }
            }]
        }

        with patch.object(client, 'chat_completion', return_value=mock_response):
            result = client.correct_content(question="Test", answer="Test")
            assert result['is_valid_question'] == True
            # LaTeX should be preserved (with double backslashes after JSON encoding/decoding)
            assert 'mathbb' in result['corrected_question']

    def test_fix_json_escapes_invalid_sequences(self):
        """Test that invalid escape sequences are handled."""
        client = ZhipuClient(api_key="test_key")

        # Response with invalid escapes like \( and \)
        mock_response = {
            "choices": [{
                "message": {
                    "content": '''{
  "corrected_question": "Use \\(x^2\\) notation",
  "has_errors": false
}'''
                }
            }]
        }

        with patch.object(client, 'chat_completion', return_value=mock_response):
            result = client.correct_content(question="Test", answer="Test")
            assert result['has_errors'] == False


class TestZhipuClient:
    """Test Zhipu API client."""

    def test_client_requires_api_key(self):
        """Test that client requires API key."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="API key is required"):
                ZhipuClient(api_key=None)

    def test_client_accepts_api_key(self):
        """Test that client accepts valid API key."""
        client = ZhipuClient(api_key="test_key_123")
        assert client.api_key == "test_key_123"

    @patch('backend.utils.llm_client.ZhipuAiClient')
    def test_correct_content_success(self, mock_sdk):
        """Test successful content correction."""
        # Mock the SDK response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '''{
  "is_valid_question": true,
  "is_valid_answer": true,
  "has_errors": false,
  "errors": [],
  "corrected_question": "What is 2+2?",
  "corrected_answer": "The answer is 4.",
  "correction_notes": "Question is clear.",
  "worth_formalizing": true
}'''
        mock_completion.choices[0].message.role = "assistant"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 10
        mock_completion.usage.completion_tokens = 20
        mock_completion.usage.total_tokens = 30

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_completion
        mock_sdk.return_value = mock_client_instance

        client = ZhipuClient(api_key="test_key")
        result = client.correct_content(
            question="What is 2+2?",
            answer="It's 4"
        )

        assert result['is_valid_question'] == True
        assert result['corrected_question'] == "What is 2+2?"
        assert result['has_errors'] == False

    @patch('backend.utils.llm_client.ZhipuAiClient')
    def test_correct_content_with_html_entities(self, mock_sdk):
        """Test handling of HTML entities in response."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"test": "a &gt; b", "valid": true}'
        mock_completion.choices[0].message.role = "assistant"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 5
        mock_completion.usage.completion_tokens = 10
        mock_completion.usage.total_tokens = 15

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_completion
        mock_sdk.return_value = mock_client_instance

        client = ZhipuClient(api_key="test_key")
        result = client.correct_content(
            question="Test a > b",
            answer="Yes"
        )

        # HTML entity should be decoded
        assert 'a > b' in result['test']

    @patch('backend.utils.llm_client.ZhipuAiClient')
    def test_correct_content_with_extra_text(self, mock_sdk):
        """Test handling of extra text after JSON."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '''Here's the analysis:

{
  "is_valid_question": true,
  "corrected_question": "Test"
}

Additional notes: The question looks good.'''
        mock_completion.choices[0].message.role = "assistant"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 10
        mock_completion.usage.completion_tokens = 15
        mock_completion.usage.total_tokens = 25

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_completion
        mock_sdk.return_value = mock_client_instance

        client = ZhipuClient(api_key="test_key")
        result = client.correct_content(question="Test", answer="Answer")

        assert result['is_valid_question'] == True

    @patch('backend.utils.llm_client.ZhipuAiClient')
    def test_correct_content_invalid_json_raises_error(self, mock_sdk):
        """Test that invalid JSON raises an error."""
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "This is not JSON at all"
        mock_completion.choices[0].message.role = "assistant"
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.prompt_tokens = 5
        mock_completion.usage.completion_tokens = 10
        mock_completion.usage.total_tokens = 15

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_completion
        mock_sdk.return_value = mock_client_instance

        client = ZhipuClient(api_key="test_key")

        with pytest.raises(ValueError, match="Could not parse"):
            client.correct_content(question="Test", answer="Answer")


class TestLLMProcessor:
    """Test LLM processor."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database manager."""
        db = Mock(spec=DatabaseManager)
        return db

    @pytest.fixture
    def mock_client(self):
        """Create a mock Zhipu client."""
        with patch('backend.processing.llm_processor.ZhipuClient') as mock:
            yield mock

    def test_process_question_with_answers(self, mock_db, mock_client):
        """Test processing a question with answers."""
        # Setup mock question
        mock_db.get_question.return_value = {
            'id': 1,
            'title': 'Test Question',
            'body': 'What is 2+2?',
            'images': [],
            'answers': [
                {'body': 'The answer is 4.', 'is_accepted': True, 'score': 5}
            ]
        }

        # Setup mock LLM response
        mock_client_instance = Mock()
        mock_client_instance.correct_content.return_value = {
            'has_errors': False,
            'errors': [],
            'corrected_question': 'What is 2+2?',
            'corrected_answer': 'The answer is 4.',
            'correction_notes': 'Question is clear.',
            'worth_formalizing': True
        }
        mock_client.return_value = mock_client_instance

        # Create processor and process
        processor = LLMProcessor(db_manager=mock_db, api_key="test_key")
        result = processor.process_question(question_internal_id=1)

        assert result['success'] == True
        assert mock_db.update_processing_status.called

        # Check that status was updated to preprocessed
        call_args = mock_db.update_processing_status.call_args_list
        assert any('status' in str(ca) and 'preprocessed' in str(ca) for ca in call_args)

    def test_process_question_without_answers(self, mock_db, mock_client):
        """Test processing a question without answers."""
        # Setup mock question with no answers
        mock_db.get_question.return_value = {
            'id': 2,
            'title': 'Test Question',
            'body': 'What is the meaning of life?',
            'images': [],
            'answers': []
        }

        # Setup mock LLM response
        mock_client_instance = Mock()
        mock_client_instance.correct_content.return_value = {
            'has_errors': False,
            'errors': [],
            'corrected_question': 'What is the meaning of life?',
            'corrected_answer': 'No answer provided',
            'correction_notes': 'Question is philosophical.',
            'worth_formalizing': False
        }
        mock_client.return_value = mock_client_instance

        # Create processor and process
        processor = LLMProcessor(db_manager=mock_db, api_key="test_key")
        result = processor.process_question(question_internal_id=2)

        assert result['success'] == True
        # Should still call LLM even without answer

    def test_process_question_with_llm_error(self, mock_db, mock_client):
        """Test handling of LLM errors."""
        # Setup mock question
        mock_db.get_question.return_value = {
            'id': 3,
            'title': 'Test',
            'body': 'Test question',
            'images': [],
            'answers': []
        }

        # Mock LLM to raise an error
        mock_client_instance = Mock()
        mock_client_instance.correct_content.side_effect = ValueError("LLM API error")
        mock_client.return_value = mock_client_instance

        # Create processor and process
        processor = LLMProcessor(db_manager=mock_db, api_key="test_key")

        with pytest.raises(ValueError):
            processor.process_question(question_internal_id=3)

        # Check that failure was recorded
        call_args = mock_db.update_processing_status.call_args_list
        assert any('status' in str(ca) and 'failed' in str(ca) for ca in call_args)

    def test_process_question_with_images(self, mock_db, mock_client):
        """Test processing a question with images."""
        # Setup mock question with images
        mock_db.get_question.return_value = {
            'id': 4,
            'title': 'Test with Image',
            'body': 'Solve this equation.',
            'images': [
                {'id': 1, 'original_url': 'http://example.com/image.png', 'image_data': b'fake'}
            ],
            'answers': []
        }

        # Setup mock LLM responses
        mock_client_instance = Mock()
        mock_client_instance.analyze_image.return_value = '{"can_convert_to_text": true}'
        mock_client_instance.correct_content.return_value = {
            'has_errors': False,
            'corrected_question': 'Solve this equation.',
            'correction_notes': 'OK'
        }
        mock_client.return_value = mock_client_instance

        # Create processor and process
        processor = LLMProcessor(db_manager=mock_db, api_key="test_key")
        result = processor.process_question(question_internal_id=4)

        assert result['success'] == True
        # Image analysis should have been called
        mock_client_instance.analyze_image.assert_called()


class TestEndToEndPreprocessing:
    """End-to-end tests for preprocessing workflow."""

    @pytest.fixture
    def real_db(self):
        """Create a real in-memory database for testing."""
        from backend.database import DatabaseManager
        # Use in-memory database for tests
        db = DatabaseManager(':memory:')
        yield db
        # Cleanup happens automatically

    def test_full_preprocessing_workflow(self, real_db):
        """Test the complete preprocessing workflow."""
        # First add a test question
        question_data = {
            'question_id': 999,
            'site_id': 1,
            'title': 'Test Question',
            'body': 'What is the integral of x^2?',
            'tags': '["calculus"]',
            'score': 5,
            'answer_count': 1,
            'link': 'http://test.com/q/999'
        }

        q_id, is_new = real_db.save_question(question_data)
        assert is_new == True

        # Verify the question was saved
        q = real_db.get_question(q_id)
        assert q is not None
        assert q['title'] == 'Test Question'

        # Check that processing status is 'raw'
        status = real_db.get_question(q_id).get('processing_status')
        assert status['status'] == 'raw'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
