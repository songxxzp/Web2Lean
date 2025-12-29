"""
Database schema definitions for Web2Lean.
Using SQLAlchemy ORM for type safety and migrations.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, LargeBinary, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Site(Base):
    """Website configuration for crawling."""
    __tablename__ = 'sites'

    site_id = Column(Integer, primary_key=True, autoincrement=True)
    site_name = Column(String(100), unique=True, nullable=False, index=True)
    site_type = Column(String(50), nullable=False)  # 'math_se', 'mathoverflow', 'amm', 'custom'
    base_url = Column(Text, nullable=False)
    api_base = Column(Text)
    enabled = Column(Boolean, default=True, nullable=False)
    config_json = Column(Text)  # Site-specific configuration as JSON
    created_at = Column(Text, default=lambda: datetime.now().isoformat())
    updated_at = Column(Text, default=lambda: datetime.now().isoformat(), onupdate=lambda: datetime.now().isoformat())

    # Relationships
    questions = relationship('Question', back_populates='site')
    crawler_runs = relationship('CrawlerRun', back_populates='site')


class Question(Base):
    """Mathematical questions from various sites."""
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, nullable=False)
    site_id = Column(Integer, ForeignKey('sites.site_id'), nullable=False)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    body_html = Column(Text)  # Original HTML
    tags = Column(Text)  # JSON array of tags
    score = Column(Integer, default=0)
    view_count = Column(Integer, default=0)
    answer_count = Column(Integer, default=0)
    creation_date = Column(Text)
    last_activity_date = Column(Text)
    owner = Column(Text)  # JSON
    link = Column(Text)
    is_answered = Column(Boolean, default=False)
    accepted_answer_id = Column(Integer)
    crawled_at = Column(Text, default=lambda: datetime.now().isoformat())

    # Relationships
    site = relationship('Site', back_populates='questions')
    answers = relationship('Answer', back_populates='question', cascade='all, delete-orphan')
    images = relationship('Image', back_populates='question', cascade='all, delete-orphan')
    processing_status = relationship('ProcessingStatus', back_populates='question', uselist=False, cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_questions_site', 'site_id'),
        Index('idx_questions_question_site', 'question_id', 'site_id', unique=True),
    )


class Answer(Base):
    """Answers to mathematical questions."""
    __tablename__ = 'answers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    answer_id = Column(Integer, nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    site_id = Column(Integer, ForeignKey('sites.site_id'), nullable=False)
    body = Column(Text, nullable=False)
    body_html = Column(Text)  # Original HTML
    score = Column(Integer, default=0)
    creation_date = Column(Text)
    last_activity_date = Column(Text)
    owner = Column(Text)  # JSON
    is_accepted = Column(Boolean, default=False)
    crawled_at = Column(Text, default=lambda: datetime.now().isoformat())

    # Relationships
    question = relationship('Question', back_populates='answers')
    images = relationship('Image', back_populates='answer', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_answers_question', 'question_id'),
        Index('idx_answers_answer_site', 'answer_id', 'site_id', unique=True),
    )


class Image(Base):
    """Images stored in database (BLOB) with OCR results."""
    __tablename__ = 'images'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey('questions.id'))
    answer_id = Column(Integer, ForeignKey('answers.id'))
    site_id = Column(Integer, ForeignKey('sites.site_id'), nullable=False)
    original_url = Column(Text, nullable=False)
    local_path = Column(Text)
    image_data = Column(LargeBinary)  # Store original image binary
    mime_type = Column(String(50))
    file_size = Column(Integer)
    ocr_text = Column(Text)  # OCR result if processed
    created_at = Column(Text, default=lambda: datetime.now().isoformat())

    # Relationships
    question = relationship('Question', back_populates='images')
    answer = relationship('Answer', back_populates='images')

    __table_args__ = (
        Index('idx_images_question', 'question_id'),
        Index('idx_images_answer', 'answer_id'),
    )


class ProcessingStatus(Base):
    """Processing status for each question through the pipeline."""
    __tablename__ = 'processing_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    site_id = Column(Integer, ForeignKey('sites.site_id'), nullable=False)
    status = Column(Text, nullable=False)  # 'raw', 'preprocessed', 'deduplicated', 'lean_converted', 'failed'
    current_stage = Column(Text)  # Current stage in pipeline
    stages_completed = Column(Text)  # JSON array of completed stages
    ocr_completed = Column(Boolean, default=False)
    preprocessed_body = Column(Text)
    preprocessed_answer = Column(Text)
    correction_notes = Column(Text)
    theorem_name = Column(Text)  # Generated theorem name for Lean conversion
    preprocessing_version = Column(Text)  # Backend version used for preprocessing
    formalization_value = Column(Text, default='medium')  # 'low', 'medium', 'high' - value for formalization
    preprocessing_error = Column(Text)  # Error message if preprocessing failed
    question_lean_code = Column(Text)  # Lean code for question (theorem/definition)
    answer_lean_code = Column(Text)  # Lean code for answer (proof)
    lean_code = Column(Text)  # Deprecated - kept for backward compatibility
    lean_error = Column(Text)

    # Lean verification fields
    verification_status = Column(Text)  # 'not_verified', 'verifying', 'passed', 'warning', 'failed', 'connection_error', 'error'
    verification_has_errors = Column(Boolean, default=False)
    verification_has_warnings = Column(Boolean, default=False)
    verification_messages = Column(Text)  # JSON array of verification messages
    verification_error = Column(Text)  # Error if verification failed
    verification_time = Column(Float)  # Total verification time in seconds
    verification_started_at = Column(Text)
    verification_completed_at = Column(Text)

    processing_started_at = Column(Text)
    processing_completed_at = Column(Text)
    last_updated = Column(Text, default=lambda: datetime.now().isoformat(), onupdate=lambda: datetime.now().isoformat())

    # Relationships
    question = relationship('Question', back_populates='processing_status')

    __table_args__ = (
        Index('idx_processing_status_question_site', 'question_id', 'site_id', unique=True),
        Index('idx_processing_status_stage', 'status', 'current_stage'),
    )


class CrawlerRun(Base):
    """Crawler execution logs."""
    __tablename__ = 'crawler_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(Integer, ForeignKey('sites.site_id'), nullable=False)
    run_id = Column(Text, unique=True, nullable=False, index=True)
    start_time = Column(Text)
    end_time = Column(Text)
    questions_crawled = Column(Integer, default=0)
    answers_crawled = Column(Integer, default=0)
    images_crawled = Column(Integer, default=0)
    status = Column(Text)  # 'running', 'completed', 'failed', 'stopped'
    error_message = Column(Text)
    run_mode = Column(Text)  # 'incremental', 'history'

    # Relationships
    site = relationship('Site', back_populates='crawler_runs')

    __table_args__ = (
        Index('idx_crawler_runs_site', 'site_id', 'start_time'),
    )


class ScheduledTask(Base):
    """Scheduled tasks for automatic crawling and processing."""
    __tablename__ = 'scheduled_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(100), unique=True, nullable=False, index=True)
    task_type = Column(Text, nullable=False)  # 'crawl', 'convert_lean', 'preprocess'
    site_id = Column(Integer, ForeignKey('sites.site_id'))
    interval_hours = Column(Integer)
    interval_minutes = Column(Integer)
    last_run = Column(Text)
    next_run = Column(Text)
    enabled = Column(Boolean, default=True)
    config_json = Column(Text)  # Additional task configuration

    __table_args__ = (
        Index('idx_scheduled_tasks_type', 'task_type'),
    )


class LeanConversionResult(Base):
    """Lean conversion results from different converters."""
    __tablename__ = 'lean_conversion_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    converter_name = Column(String(100), nullable=False, index=True)  # e.g., 'kimina-7b', 'glm-4'
    converter_type = Column(String(50), nullable=False)  # 'local_model', 'api_llm', 'manual'
    converter_version = Column(String(50))  # Version of the converter (e.g., GLM_AGENT_VERSION, KIMINA_VERSION)
    question_lean_code = Column(Text)  # Lean code for question (theorem/definition)
    answer_lean_code = Column(Text)  # Lean code for answer (proof)
    verification_status = Column(Text)  # 'not_verified', 'verifying', 'passed', 'warning', 'failed', 'error'
    verification_has_errors = Column(Boolean, default=False)
    verification_has_warnings = Column(Boolean, default=False)
    verification_messages = Column(Text)  # JSON array of verification messages
    verification_time = Column(Float)  # Verification time in seconds
    conversion_time = Column(Float)  # Conversion time in seconds
    error_message = Column(Text)  # Error if conversion failed
    created_at = Column(Text, default=lambda: datetime.now().isoformat())

    __table_args__ = (
        Index('idx_lean_conversion_results_question', 'question_id'),
        Index('idx_lean_conversion_results_converter', 'converter_name', 'question_id', unique=True),
    )
