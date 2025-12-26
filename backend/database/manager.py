"""
Database manager for Web2Lean.
Handles database connections, queries, and initialization.
"""
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .schema import (
    Base, Site, Question, Answer, Image, ProcessingStatus,
    CrawlerRun, ScheduledTask
)


class DatabaseManager:
    """Database manager for Web2Lean."""

    def __init__(self, db_path: str = None):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file. If None, uses default.
        """
        if db_path is None:
            os.makedirs('/datadisk/Web2Lean/data/databases', exist_ok=True)
            db_path = '/datadisk/Web2Lean/data/databases/web2lean.db'

        self.db_path = db_path
        # SQLite connection with thread-safe settings
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.init_database()

    def init_database(self):
        """Initialize database tables."""
        Base.metadata.create_all(self.engine)
        self._init_default_sites()

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def _init_default_sites(self):
        """Initialize default sites if not exists."""
        session = self.get_session()
        try:
            if session.query(Site).count() == 0:
                default_sites = [
                    {
                        'site_name': 'math_stackexchange',
                        'site_type': 'math_se',
                        'base_url': 'https://math.stackexchange.com',
                        'api_base': 'https://api.stackexchange.com/2.3',
                        'enabled': True,
                        'config_json': json.dumps({
                            'pages_per_run': 10,
                            'request_delay': 8.0,
                            'max_retries': 3
                        })
                    },
                    {
                        'site_name': 'mathoverflow',
                        'site_type': 'mathoverflow',
                        'base_url': 'https://mathoverflow.net',
                        'enabled': True,
                        'config_json': json.dumps({
                            'pages_per_run': 5,
                            'request_delay': 10.0,
                        })
                    },
                    {
                        'site_name': 'amm',
                        'site_type': 'amm',
                        'base_url': 'https://www.mat.uniroma2.it/~tauraso/AMM/amm.html',
                        'enabled': False,  # Disabled by default
                        'config_json': json.dumps({})
                    }
                ]
                for site_data in default_sites:
                    site = Site(**site_data)
                    session.add(site)
                session.commit()
        finally:
            session.close()

    # ===== Site Management =====

    def get_sites(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """Get all sites."""
        session = self.get_session()
        try:
            query = session.query(Site)
            if enabled_only:
                query = query.filter(Site.enabled == True)
            sites = query.all()
            return [
                {
                    'site_id': s.site_id,
                    'site_name': s.site_name,
                    'site_type': s.site_type,
                    'base_url': s.base_url,
                    'api_base': s.api_base,
                    'enabled': s.enabled,
                    'config_json': s.config_json,
                }
                for s in sites
            ]
        finally:
            session.close()

    def get_site(self, site_id: int) -> Optional[Dict[str, Any]]:
        """Get site by ID."""
        session = self.get_session()
        try:
            site = session.query(Site).filter(Site.site_id == site_id).first()
            if site:
                return {
                    'site_id': site.site_id,
                    'site_name': site.site_name,
                    'site_type': site.site_type,
                    'base_url': site.base_url,
                    'api_base': site.api_base,
                    'enabled': site.enabled,
                    'config_json': site.config_json,
                }
            return None
        finally:
            session.close()

    def get_site_by_name(self, site_name: str) -> Optional[Dict[str, Any]]:
        """Get site by name."""
        session = self.get_session()
        try:
            site = session.query(Site).filter(Site.site_name == site_name).first()
            if site:
                return {
                    'site_id': site.site_id,
                    'site_name': site.site_name,
                    'site_type': site.site_type,
                    'base_url': site.base_url,
                    'api_base': site.api_base,
                    'enabled': site.enabled,
                    'config_json': site.config_json,
                }
            return None
        finally:
            session.close()

    # ===== Question Management =====

    def save_question(self, question_data: Dict[str, Any]) -> tuple[int, bool]:
        """
        Save or update a question.

        Returns:
            Tuple of (question_internal_id, is_new)
        """
        session = self.get_session()
        try:
            # Check if question exists
            existing = session.query(Question).filter(
                Question.question_id == question_data['question_id'],
                Question.site_id == question_data['site_id']
            ).first()

            if existing:
                # Update existing - don't update crawled_at to track original crawl time
                question_data_copy = question_data.copy()
                question_data_copy.pop('crawled_at', None)  # Don't update crawl time
                for key, value in question_data_copy.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                session.commit()
                return existing.id, False
            else:
                # Create new
                question = Question(**question_data)
                session.add(question)
                session.commit()
                session.refresh(question)

                # Create processing status
                status = ProcessingStatus(
                    question_id=question.id,
                    site_id=question.site_id,
                    status='raw'
                )
                session.add(status)
                session.commit()

                return question.id, True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def question_exists(self, question_id: int, site_id: int) -> bool:
        """Check if a question already exists."""
        session = self.get_session()
        try:
            return session.query(Question).filter(
                Question.question_id == question_id,
                Question.site_id == site_id
            ).first() is not None
        finally:
            session.close()

    def get_last_crawl_time(self, site_id: int) -> Optional[int]:
        """
        Get the timestamp of the most recent question for a site.

        Returns:
            Unix timestamp or None if no questions exist
        """
        session = self.get_session()
        try:
            # Get the most recent question by creation_date
            result = session.query(Question).filter(
                Question.site_id == site_id
            ).order_by(Question.creation_date.desc()).first()

            if result and result.creation_date:
                try:
                    return int(result.creation_date)
                except (ValueError, TypeError):
                    # If creation_date is not a timestamp, return None
                    return None
            return None
        finally:
            session.close()

    def get_question(self, question_id: int) -> Optional[Dict[str, Any]]:
        """Get question by internal ID."""
        session = self.get_session()
        try:
            q = session.query(Question).filter(Question.id == question_id).first()
            if not q:
                return None

            # Get processing status
            ps = session.query(ProcessingStatus).filter(
                ProcessingStatus.question_id == question_id
            ).first()

            # Get images
            images = session.query(Image).filter(Image.question_id == question_id).all()

            # Get answers
            answers = session.query(Answer).filter(Answer.question_id == question_id).all()

            return {
                'id': q.id,
                'question_id': q.question_id,
                'site_id': q.site_id,
                'title': q.title,
                'body': q.body,
                'body_html': q.body_html,
                'tags': json.loads(q.tags) if q.tags else [],
                'score': q.score,
                'answer_count': q.answer_count,
                'link': q.link,
                'crawled_at': q.crawled_at,
                'processing_status': {
                    'status': ps.status if ps else 'raw',
                    'ocr_completed': ps.ocr_completed if ps else False,
                    'preprocessed_body': ps.preprocessed_body if ps else None,
                    'lean_code': ps.lean_code if ps else None,
                } if ps else None,
                'images': [
                    {
                        'id': img.id,
                        'original_url': img.original_url,
                        'ocr_text': img.ocr_text,
                    }
                    for img in images
                ],
                'answers': [
                    {
                        'id': a.id,
                        'answer_id': a.answer_id,
                        'body': a.body,
                        'score': a.score,
                        'is_accepted': a.is_accepted,
                    }
                    for a in answers
                ]
            }
        finally:
            session.close()

    def list_questions(self, site_id: Optional[int] = None,
                      status: Optional[str] = None,
                      limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """List questions with optional filters. Returns dict with questions and total count."""
        session = self.get_session()
        try:
            # Build base query
            base_query = session.query(Question, ProcessingStatus).outerjoin(
                ProcessingStatus,
                Question.id == ProcessingStatus.question_id
            )

            if site_id is not None:
                base_query = base_query.filter(Question.site_id == site_id)
            if status is not None:
                base_query = base_query.filter(ProcessingStatus.status == status)

            # Get total count
            total = base_query.count()

            # Get paginated results
            query = base_query.order_by(Question.id.desc()).offset(offset).limit(limit)
            results = query.all()

            questions = [
                {
                    'id': q.id,
                    'question_id': q.question_id,
                    'site_id': q.site_id,
                    'title': q.title,
                    'score': q.score,
                    'answer_count': q.answer_count,
                    'status': ps.status if ps else 'raw',
                    'crawled_at': q.crawled_at,
                }
                for q, ps in results
            ]

            return {
                'questions': questions,
                'total': total
            }
        finally:
            session.close()

    # ===== Statistics =====

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics."""
        session = self.get_session()
        try:
            total_questions = session.query(func.count(Question.id)).scalar()
            total_answers = session.query(func.count(Answer.id)).scalar()
            total_images = session.query(func.count(Image.id)).scalar()

            # Processing status counts
            raw_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'raw'
            ).scalar()
            preprocessed_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'preprocessed'
            ).scalar()
            lean_converted_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'lean_converted'
            ).scalar()
            failed_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'failed'
            ).scalar()

            # Per-site stats
            sites = self.get_sites()
            site_stats = []
            for site in sites:
                site_q_count = session.query(func.count(Question.id)).filter(
                    Question.site_id == site['site_id']
                ).scalar()
                site_lean_count = session.query(func.count(ProcessingStatus.id)).filter(
                    ProcessingStatus.site_id == site['site_id'],
                    ProcessingStatus.status == 'lean_converted'
                ).scalar()
                site_stats.append({
                    'site_name': site['site_name'],
                    'total_count': site_q_count or 0,
                    'lean_converted': site_lean_count or 0,
                })

            return {
                'total_questions': total_questions or 0,
                'total_answers': total_answers or 0,
                'total_images': total_images or 0,
                'processing_status': {
                    'raw': raw_count or 0,
                    'preprocessed': preprocessed_count or 0,
                    'lean_converted': lean_converted_count or 0,
                    'failed': failed_count or 0,
                },
                'by_site': site_stats,
            }
        finally:
            session.close()

    def get_site_statistics(self, site_id: int) -> Dict[str, Any]:
        """Get statistics for a specific site."""
        session = self.get_session()
        try:
            total_questions = session.query(func.count(Question.id)).filter(
                Question.site_id == site_id
            ).scalar()

            total_answers = session.query(func.count(Answer.id)).filter(
                Answer.site_id == site_id
            ).scalar()

            return {
                'site_id': site_id,
                'total_questions': total_questions or 0,
                'total_answers': total_answers or 0,
            }
        finally:
            session.close()

    # ===== Processing Status =====

    def update_processing_status(self, question_id: int, **kwargs) -> bool:
        """Update processing status for a question."""
        session = self.get_session()
        try:
            ps = session.query(ProcessingStatus).filter(
                ProcessingStatus.question_id == question_id
            ).first()
            if ps:
                for key, value in kwargs.items():
                    if hasattr(ps, key):
                        setattr(ps, key, value)
                ps.last_updated = datetime.now().isoformat()
                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_questions_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get questions by processing status."""
        session = self.get_session()
        try:
            results = session.query(Question, ProcessingStatus).join(
                ProcessingStatus,
                Question.id == ProcessingStatus.question_id
            ).filter(
                ProcessingStatus.status == status
            ).limit(limit).all()

            return [
                {
                    'id': q.id,
                    'question_id': q.question_id,
                    'site_id': q.site_id,
                    'title': q.title,
                    'body': q.body,
                }
                for q, ps in results
            ]
        finally:
            session.close()

    # ===== Crawler Runs =====

    def create_crawler_run(self, site_id: int, run_id: str, run_mode: str = 'incremental') -> CrawlerRun:
        """Create a new crawler run record."""
        session = self.get_session()
        try:
            run = CrawlerRun(
                site_id=site_id,
                run_id=run_id,
                start_time=datetime.now().isoformat(),
                status='running',
                run_mode=run_mode
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run
        finally:
            session.close()

    def update_crawler_run(self, run_id: str, **kwargs) -> bool:
        """Update crawler run record."""
        session = self.get_session()
        try:
            run = session.query(CrawlerRun).filter(CrawlerRun.run_id == run_id).first()
            if run:
                for key, value in kwargs.items():
                    if hasattr(run, key):
                        setattr(run, key, value)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_active_crawler_runs(self) -> List[Dict[str, Any]]:
        """Get currently active crawler runs."""
        session = self.get_session()
        try:
            runs = session.query(CrawlerRun, Site).join(
                Site, CrawlerRun.site_id == Site.site_id
            ).filter(CrawlerRun.status == 'running').all()

            return [
                {
                    'run_id': run.run_id,
                    'site_id': run.site_id,
                    'site_name': site.site_name,
                    'start_time': run.start_time,
                    'questions_crawled': run.questions_crawled,
                    'run_mode': run.run_mode,
                }
                for run, site in runs
            ]
        finally:
            session.close()
