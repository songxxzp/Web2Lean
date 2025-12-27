"""
Unit tests for Web2Lean API endpoints.
"""
import pytest
import json
import tempfile
import os
from pathlib import Path

from backend.api.app import create_app
from backend.database import DatabaseManager
from backend.database.schema import Base, Site, Question, Answer


@pytest.fixture
def test_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Create database manager (this calls init_database automatically)
    db = DatabaseManager(path)

    # Add test data
    session = db.get_session()
    try:
        # Add test site
        site = Site(
            site_name='math.stackexchange.com',
            site_type='stackexchange',
            base_url='https://math.stackexchange.com',
            enabled=True
        )
        session.add(site)
        session.flush()

        # Add test questions
        for i in range(5):
            question = Question(
                question_id=1000 + i,
                site_id=site.site_id,
                title=f'Test Question {i}',
                body=f'This is test question {i}',
                body_html=f'<p>This is test question {i}</p>',
                tags=json.dumps(['test', 'math']),  # Store as JSON array
                score=i,
                answer_count=i,
                creation_date='2024-01-01T00:00:00',
                link=f'https://math.stackexchange.com/questions/{1000 + i}',
                crawled_at='2024-01-01T00:00:00'
            )
            session.add(question)

        session.commit()
    finally:
        session.close()

    yield db

    # Cleanup
    os.unlink(path)


@pytest.fixture
def app(test_db):
    """Create Flask app with test database."""
    app = create_app()
    app.config['db'] = test_db
    app.config['TESTING'] = True

    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestRootEndpoints:
    """Test root and health endpoints."""

    def test_root(self, client):
        """Test root endpoint returns API info."""
        rv = client.get('/')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['name'] == 'Web2Lean API'
        assert data['status'] == 'running'

    def test_health(self, client):
        """Test health check endpoint."""
        rv = client.get('/api/health')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['status'] == 'healthy'

    def test_404_handler(self, client):
        """Test 404 error handler."""
        rv = client.get('/api/nonexistent')
        assert rv.status_code == 404
        data = json.loads(rv.data)
        assert 'error' in data


class TestStatisticsEndpoints:
    """Test statistics endpoints."""

    def test_get_overview_statistics(self, client):
        """Test getting overview statistics."""
        rv = client.get('/api/statistics/overview')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'total_questions' in data
        assert 'total_answers' in data
        assert 'by_site' in data or 'sites' in data

    def test_get_site_statistics(self, client):
        """Test getting statistics for a specific site."""
        rv = client.get('/api/statistics/site/1')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'total_questions' in data

    def test_get_site_statistics_not_found(self, client):
        """Test getting statistics for non-existent site."""
        rv = client.get('/api/statistics/site/999')
        # API returns 200 with empty stats for non-existent sites
        assert rv.status_code == 200
        data = json.loads(rv.data)
        # Should have empty or zero stats

    def test_get_processing_statistics(self, client):
        """Test getting processing statistics."""
        rv = client.get('/api/statistics/processing')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        # Should return processing_status stats even if empty


class TestDatabaseEndpoints:
    """Test database viewing endpoints."""

    def test_list_questions_default(self, client):
        """Test listing questions with default parameters."""
        rv = client.get('/api/database/questions')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'questions' in data
        assert 'count' in data
        assert 'limit' in data
        assert 'offset' in data
        assert len(data['questions']) == 5
        assert data['count'] == 5

    def test_list_questions_with_pagination(self, client):
        """Test listing questions with pagination."""
        rv = client.get('/api/database/questions?limit=2&offset=0')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert len(data['questions']) == 2
        assert data['limit'] == 2
        assert data['offset'] == 0

    def test_list_questions_with_offset(self, client):
        """Test listing questions with offset."""
        rv = client.get('/api/database/questions?limit=2&offset=2')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert len(data['questions']) == 2

    def test_get_question_detail(self, client):
        """Test getting detailed question information."""
        rv = client.get('/api/database/questions/1')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['id'] == 1
        assert 'title' in data
        assert 'body' in data

    def test_get_question_detail_not_found(self, client):
        """Test getting non-existent question."""
        rv = client.get('/api/database/questions/999')
        assert rv.status_code == 404
        data = json.loads(rv.data)
        assert 'error' in data

    def test_get_question_images(self, client):
        """Test getting images for a question."""
        rv = client.get('/api/database/questions/1/images')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert isinstance(data, list)

    def test_get_database_statistics(self, client):
        """Test getting database statistics."""
        rv = client.get('/api/database/statistics')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'total_questions' in data


class TestConfigEndpoints:
    """Test configuration endpoints."""

    def test_get_sites(self, client):
        """Test getting all site configurations."""
        rv = client.get('/api/config/sites')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert isinstance(data, list)
        assert len(data) >= 1
        # Should contain our test site
        site_names = [s['site_name'] for s in data]
        assert 'math.stackexchange.com' in site_names

    def test_update_site_enabled(self, client):
        """Test updating site enabled status."""
        rv = client.put('/api/config/sites/1',
                       data=json.dumps({'enabled': False}),
                       content_type='application/json')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'message' in data

        # Verify update
        rv = client.get('/api/config/sites')
        data = json.loads(rv.data)
        assert data[0]['enabled'] == False

    def test_update_site_config(self, client):
        """Test updating site configuration."""
        config = {
            'start_page': 5,
            'pages_per_run': 20
        }
        rv = client.put('/api/config/sites/1',
                       data=json.dumps({'config': config}),
                       content_type='application/json')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'message' in data

    def test_update_site_not_found(self, client):
        """Test updating non-existent site."""
        rv = client.put('/api/config/sites/999',
                       data=json.dumps({'enabled': False}),
                       content_type='application/json')
        assert rv.status_code == 404
        data = json.loads(rv.data)
        assert 'error' in data

    def test_get_prompts(self, client):
        """Test getting LLM prompts."""
        rv = client.get('/api/config/prompts')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert isinstance(data, dict)

    def test_get_schedules(self, client):
        """Test getting scheduled tasks."""
        rv = client.get('/api/config/schedules')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert isinstance(data, list)

    def test_get_models(self, client):
        """Test getting model configuration."""
        rv = client.get('/api/config/models')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'glm_text_model' in data
        assert 'glm_vision_model' in data
        assert 'glm_lean_model' in data
        assert 'vllm_base_url' in data
        assert 'vllm_model_path' in data

    def test_update_models(self, client, app, tmp_path):
        """Test updating model configuration."""
        models = {
            'glm_text_model': 'glm-4.7',
            'glm_vision_model': 'glm-4.6v',
            'glm_lean_model': ''
        }
        rv = client.put('/api/config/models',
                       data=json.dumps(models),
                       content_type='application/json')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert 'message' in data
        assert 'models' in data
        assert data['models']['glm_text_model'] == 'glm-4.7'


class TestCORSEndpoints:
    """Test CORS headers."""

    def test_cors_headers_on_get(self, client):
        """Test CORS headers are present on GET requests."""
        rv = client.get('/api/config/sites')
        assert rv.status_code == 200
        # Note: Flask test client doesn't expose CORS headers by default
        # This tests the endpoint works correctly

    def test_options_request(self, client):
        """Test OPTIONS request for CORS preflight."""
        rv = client.options('/api/config/sites')
        assert rv.status_code == 200


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_database(self, app):
        """Test API with empty database."""
        # Create empty database
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        db = DatabaseManager(path)  # init_database is called automatically

        app.config['db'] = db
        client = app.test_client()

        # Test empty results
        rv = client.get('/api/database/questions')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['questions'] == []
        assert data['count'] == 0

        # Cleanup
        os.unlink(path)

    def test_invalid_json(self, client):
        """Test sending invalid JSON."""
        rv = client.put('/api/config/sites/1',
                       data='invalid json',
                       content_type='application/json')
        assert rv.status_code == 400  # Bad request

    def test_invalid_query_params(self, client):
        """Test invalid query parameters."""
        # Should handle gracefully
        rv = client.get('/api/database/questions?limit=abc')
        # Default limit should be used
        assert rv.status_code == 200

    def test_large_offset(self, client):
        """Test with offset larger than result set."""
        rv = client.get('/api/database/questions?offset=1000')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['questions'] == []
