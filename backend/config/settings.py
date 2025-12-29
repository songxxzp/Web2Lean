"""
Configuration management for Web2Lean.
Handles loading and accessing configuration from files and environment variables.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class Settings:
    """Application settings."""

    # Database
    db_path: str = '/datadisk/Web2Lean/data/databases/web2lean.db'

    # API Keys
    zhipu_api_key: str = ''
    vllm_base_url: str = 'http://localhost:8000/v1'
    vllm_model_path: str = '/root/Kimina-Autoformalizer-7B'
    kimina_url: str = 'http://127.0.0.1:9000'  # Lean verification server

    # LLM Models
    glm_text_model: str = 'glm-4.7'  # For text processing (new zai-sdk)
    glm_vision_model: str = 'glm-4.6v'  # For image OCR (new zai-sdk)
    glm_lean_model: str = 'glm-4.7'  # For Lean code conversion (GLM-based LLM agent)

    # Crawler defaults
    default_pages_per_run: int = 10
    default_request_delay: float = 8.0
    default_max_retries: int = 3
    default_timeout: int = 30

    # Processing
    lean_conversion_max_tokens: int = 16000  # Max tokens for lean conversion
    lean_conversion_temperature: float = 0.2  # Temperature for lean conversion
    lean_max_iterations: int = 1  # Max iterations for correction
    ocr_temperature: float = 0.1
    preprocessing_temperature: float = 0.2
    preprocessing_concurrency: int = 2  # Number of concurrent LLM API calls
    preprocessing_max_length: int = 16000  # Max token length for LLM calls

    # Paths
    base_dir: Path = field(default_factory=lambda: Path('/datadisk/Web2Lean'))
    data_dir: Path = field(default_factory=lambda: Path('/datadisk/Web2Lean/data'))
    log_dir: Path = field(default_factory=lambda: Path('/datadisk/Web2Lean/logs'))
    legacy_dir: Path = field(default_factory=lambda: Path('/datadisk/Web2Lean/legacy'))

    # API Server
    api_host: str = '0.0.0.0'
    api_port: int = 5000
    api_debug: bool = False

    # Scheduler
    scheduler_enabled: bool = True
    default_crawl_interval_hours: int = 6

    # Site configs (loaded from JSON)
    site_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # LLM Prompts
    prompts: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Load additional configs after initialization."""
        self._load_env()
        self._load_site_configs()
        self._load_prompts()

    def _load_env(self):
        """Load settings from environment variables."""
        # Load .env file from base directory
        env_file = self.base_dir / '.env'
        if env_file.exists():
            load_dotenv(env_file)

        self.zhipu_api_key = os.getenv('ZHIPU_API_KEY', self.zhipu_api_key)
        self.api_port = int(os.getenv('API_PORT', self.api_port))
        self.api_debug = os.getenv('API_DEBUG', 'false').lower() == 'true'
        self.glm_text_model = os.getenv('GLM_TEXT_MODEL', self.glm_text_model)
        self.glm_vision_model = os.getenv('GLM_VISION_MODEL', self.glm_vision_model)
        self.kimina_url = os.getenv('KIMINA_URL', self.kimina_url)
        # Handle "local" as empty string for Kimina model
        lean_model_env = os.getenv('GLM_LEAN_MODEL', '')
        if lean_model_env == 'local' or lean_model_env == '':
            # Use default 'glm-4.7' for LLM converter
            self.glm_lean_model = self.glm_lean_model  # Keep the default value
        else:
            self.glm_lean_model = lean_model_env

    def _load_site_configs(self):
        """Load site configurations from JSON file."""
        sites_file = self.base_dir / 'backend/config/sites.json'
        if sites_file.exists():
            with open(sites_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.site_configs = data.get('sites', {})

    def _load_prompts(self):
        """Load LLM prompts from JSON file."""
        prompts_file = self.base_dir / 'backend/config/prompts.json'
        if prompts_file.exists():
            with open(prompts_file, 'r', encoding='utf-8') as f:
                self.prompts = json.load(f)
        else:
            # Default prompts
            self.prompts = self._get_default_prompts()

    def _get_default_prompts(self) -> Dict[str, str]:
        """Get default LLM prompts."""
        return {
            'image_ocr_decision': '''You are a mathematical content analyzer. Examine this image and determine:

1. Does this image contain primarily mathematical notation, text, or diagrams that can be converted to text/LaTeX?
2. Or is it primarily a complex plot, graph, or visual that should remain as an image?

Respond in JSON format:
{
  "can_convert_to_text": true/false,
  "reasoning": "Brief explanation",
  "content_type": "latex/text/diagram/graph/other",
  "extracted_text": "If convertible, provide LaTeX or text representation"
}''',

            'content_correction': '''You are a mathematics content validator and corrector. Analyze this mathematical question and answer pair:

--- QUESTION ---
{question}

--- ANSWER ---
{answer}

Tasks:
1. Verify if the question is well-formed and mathematically valid
2. Verify if the answer is correct and addresses the question
3. Check for any obvious errors, typos, or ambiguities
4. Identify if this pair has value for formalization

Respond in JSON format:
{
  "is_valid_question": true/false,
  "is_valid_answer": true/false,
  "has_errors": true/false,
  "errors": ["list of specific issues found"],
  "corrected_question": "corrected version if needed, else original",
  "corrected_answer": "corrected version if needed, else original",
  "correction_notes": "detailed explanation of corrections made",
  "worth_formalizing": true/false,
  "formalization_value": "high/medium/low"
}''',

            'lean_conversion': '''You are an expert in mathematics and Lean 4.

Please autoformalize the following problem in Lean 4 with a header.

{content}'''
        }

    def get_prompt(self, name: str, **kwargs) -> str:
        """Get a prompt with variable substitution."""
        prompt = self.prompts.get(name, '')
        if kwargs:
            prompt = prompt.format(**kwargs)
        return prompt

    def get_site_config(self, site_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific site."""
        return self.site_configs.get(site_name)

    def save_site_config(self, site_name: str, config: Dict[str, Any]):
        """Save configuration for a specific site."""
        self.site_configs[site_name] = config
        sites_file = self.base_dir / 'backend/config/sites.json'
        sites_file.parent.mkdir(parents=True, exist_ok=True)
        with open(sites_file, 'w', encoding='utf-8') as f:
            json.dump({'sites': self.site_configs}, f, indent=2, ensure_ascii=False)

    def ensure_directories(self):
        """Ensure all required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / 'databases').mkdir(parents=True, exist_ok=True)
        (self.data_dir / 'images').mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings
