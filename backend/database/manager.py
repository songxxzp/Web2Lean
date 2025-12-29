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
    CrawlerRun, ScheduledTask, LeanConversionResult
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
                    'preprocessed_answer': ps.preprocessed_answer if ps else None,
                    'correction_notes': ps.correction_notes if ps else None,
                    'theorem_name': ps.theorem_name if ps else None,
                    'preprocessing_version': ps.preprocessing_version if ps else None,
                    'formalization_value': ps.formalization_value if ps else None,
                    'preprocessing_error': ps.preprocessing_error if ps else None,
                    'question_lean_code': ps.question_lean_code if ps else None,
                    'answer_lean_code': ps.answer_lean_code if ps else None,
                    'lean_code': ps.lean_code if ps else None,  # Deprecated, for backward compatibility
                    'lean_error': ps.lean_error if ps else None,
                    'verification_status': ps.verification_status if ps and ps.verification_status else 'not_verified',
                    'verification_has_errors': ps.verification_has_errors if ps else False,
                    'verification_has_warnings': ps.verification_has_warnings if ps else False,
                    'verification_messages': json.loads(ps.verification_messages) if ps and ps.verification_messages else [],
                    'verification_error': ps.verification_error if ps else None,
                    'verification_time': ps.verification_time if ps else None,
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
            # Build base query with actual answer count
            from sqlalchemy import func as sql_func

            # Subquery to get actual answer count for each question
            answer_count_subq = session.query(
                Answer.question_id,
                sql_func.count(Answer.id).label('actual_answer_count')
            ).group_by(Answer.question_id).subquery()

            base_query = session.query(
                Question,
                ProcessingStatus,
                sql_func.coalesce(answer_count_subq.c.actual_answer_count, 0).label('actual_answers')
            ).outerjoin(
                ProcessingStatus,
                Question.id == ProcessingStatus.question_id
            ).outerjoin(
                answer_count_subq,
                Question.id == answer_count_subq.c.question_id
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
                    'answer_count': actual_answers,  # Use actual answer count from database
                    'status': ps.status if ps else 'raw',
                    'verification_status': ps.verification_status if ps else None,
                    'crawled_at': q.crawled_at,
                    'processing_status': {
                        'status': ps.status if ps else 'raw',
                        'verification_status': ps.verification_status if ps else None,
                        'theorem_name': ps.theorem_name if ps else None,
                        'preprocessing_version': ps.preprocessing_version if ps else None,
                        'formalization_value': ps.formalization_value if ps else None,
                    }
                }
                for q, ps, actual_answers in results
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

            # Lean verified count (passed or warning)
            lean_verified_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'lean_converted',
                ProcessingStatus.verification_status.in_(['passed', 'warning'])
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
                    'lean_verified': lean_verified_count or 0,
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

    def get_detailed_site_statistics(self) -> List[Dict[str, Any]]:
        """Get detailed statistics for each site including averages."""
        session = self.get_session()
        try:
            sites = session.query(Site).all()
            site_stats = []

            for site in sites:
                # Count questions and answers for this site
                questions = session.query(Question).filter(Question.site_id == site.site_id).all()

                if not questions:
                    continue

                total_questions = len(questions)
                total_answers = session.query(func.count(Answer.id)).filter(
                    Answer.site_id == site.site_id
                ).scalar() or 0

                # Calculate average question length
                avg_question_length = session.query(func.avg(func.length(Question.body))).filter(
                    Question.site_id == site.site_id
                ).scalar() or 0

                # Calculate average answer length
                avg_answer_length = session.query(func.avg(func.length(Answer.body))).filter(
                    Answer.site_id == site.site_id
                ).scalar() or 0

                site_stats.append({
                    'site_id': site.site_id,
                    'site_name': site.site_name,
                    'total_questions': total_questions,
                    'total_answers': total_answers,
                    'avg_answers_per_question': round(total_answers / total_questions, 2) if total_questions > 0 else 0,
                    'avg_question_length': round(float(avg_question_length), 2),
                    'avg_answer_length': round(float(avg_answer_length), 2),
                })

            return site_stats
        finally:
            session.close()

    def get_preprocessing_statistics(self) -> Dict[str, Any]:
        """Get detailed preprocessing statistics."""
        session = self.get_session()
        try:
            # Count questions by preprocessing result
            success_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'preprocessed'
            ).scalar() or 0

            failed_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'failed',
                ProcessingStatus.preprocessing_error.isnot(None)
            ).scalar() or 0

            cant_convert_count = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.status == 'cant_convert'
            ).scalar() or 0

            total_processed = success_count + failed_count + cant_convert_count

            return {
                'total_processed': total_processed,
                'success': success_count,
                'failed': failed_count,
                'cant_convert': cant_convert_count,
            }
        finally:
            session.close()

    def get_verification_statistics(self) -> Dict[str, Any]:
        """Get detailed Lean verification statistics."""
        session = self.get_session()
        try:
            # Count by verification status from processing_status table
            # Only count records that have actually been verified (passed, warning, or failed)
            passed = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.verification_status == 'passed'
            ).scalar() or 0

            warning = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.verification_status == 'warning'
            ).scalar() or 0

            failed = session.query(func.count(ProcessingStatus.id)).filter(
                ProcessingStatus.verification_status == 'failed'
            ).scalar() or 0

            # Total checked = passed + warning + failed (only actually verified records)
            total_checked = passed + warning + failed

            # passed + warning = verified successfully
            total_verified = passed + warning

            return {
                'total_checked': total_checked,
                'passed': passed,
                'warning': warning,
                'failed': failed,
                'total_verified': total_verified,
            }
        finally:
            session.close()

    def export_verified_lean_data(self) -> List[Dict[str, Any]]:
        """Export all verified Lean data as list of dicts for JSONL export.

        Returns:
            List of dictionaries containing verified Lean data
        """
        session = self.get_session()
        try:
            # Query questions with lean_converted status AND verification status in ('passed', 'warning')
            results = session.query(Question, ProcessingStatus, Site).join(
                ProcessingStatus, Question.id == ProcessingStatus.question_id
            ).join(
                Site, Question.site_id == Site.site_id
            ).filter(
                ProcessingStatus.status == 'lean_converted',
                ProcessingStatus.verification_status.in_(['passed', 'warning'])
            ).all()

            export_data = []
            for question, ps, site in results:
                # Determine verification level
                verification_status = ps.verification_status or 'not_verified'
                if verification_status == 'passed':
                    verification_level = 'passed'
                elif verification_status == 'warning':
                    verification_level = 'warning'
                else:
                    verification_level = 'info'

                export_data.append({
                    'id': question.id,
                    'question_id': question.question_id,
                    'site_id': question.site_id,
                    'site_name': site.site_name,
                    'title': question.title,
                    'url': question.link,
                    'score': question.score,
                    'verification_status': verification_status,
                    'verification_level': verification_level,
                    'preprocessed_body': ps.preprocessed_body,
                    'preprocessed_answer': ps.preprocessed_answer,
                    'question_lean_code': ps.question_lean_code,
                    'answer_lean_code': ps.answer_lean_code,
                    'lean_code': ps.lean_code,
                    'verification_time': ps.verification_time,
                    'verification_completed_at': ps.verification_completed_at,
                    'has_errors': ps.verification_has_errors,
                    'has_warnings': ps.verification_has_warnings,
                    'crawled_at': question.crawled_at,
                    'processing_started_at': ps.processing_started_at,
                    'processing_completed_at': ps.processing_completed_at
                })

            return export_data
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

    def cleanup_stuck_preprocessing(self) -> int:
        """
        Clean up questions stuck in 'preprocessing' status.

        Resets questions with status='preprocessing' back to 'raw' status.
        This should be called on backend startup and when preprocessing tasks are stopped.

        Returns:
            Number of questions reset
        """
        session = self.get_session()
        try:
            # Find all questions stuck in preprocessing status
            stuck_questions = session.query(ProcessingStatus).filter(
                ProcessingStatus.status == 'preprocessing'
            ).all()

            count = len(stuck_questions)
            if count > 0:
                # Reset them to raw status
                for ps in stuck_questions:
                    ps.status = 'raw'
                    ps.current_stage = None
                    ps.processing_started_at = None
                    # Clear any partial preprocessing data
                    if not ps.preprocessed_body:
                        # Only clear if there's no preprocessed data yet
                        ps.preprocessing_error = 'Preprocessing was interrupted'

                session.commit()
                logger = __import__('logging').getLogger(__name__)
                logger.info(f'Cleaned up {count} questions stuck in preprocessing status')

            return count
        except Exception as e:
            session.rollback()
            logger = __import__('logging').getLogger(__name__)
            logger.error(f'Error cleaning up stuck preprocessing: {e}')
            raise
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

    def get_questions_not_converted_by(self, converter_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get preprocessed questions that haven't been converted by a specific converter."""
        session = self.get_session()
        try:
            # Subquery to find questions already converted by this converter
            converted_ids = session.query(LeanConversionResult.question_id).filter(
                LeanConversionResult.converter_name == converter_name
            ).subquery()

            # Get preprocessed questions not in the converted_ids subquery
            results = session.query(Question, ProcessingStatus).join(
                ProcessingStatus,
                Question.id == ProcessingStatus.question_id
            ).filter(
                ProcessingStatus.status == 'preprocessed'
            ).filter(
                ~Question.id.in_(converted_ids)
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

    # ===== Lean Conversion Results =====

    def save_lean_conversion_result(self, question_id: int, converter_name: str,
                                   converter_type: str, question_lean_code: str = None,
                                   answer_lean_code: str = None, conversion_time: float = None,
                                   error_message: str = None) -> LeanConversionResult:
        """Save or update a Lean conversion result from a specific converter."""
        session = self.get_session()
        try:
            # Check if result already exists for this converter
            result = session.query(LeanConversionResult).filter(
                LeanConversionResult.question_id == question_id,
                LeanConversionResult.converter_name == converter_name
            ).first()

            if result:
                # Update existing result
                if question_lean_code is not None:
                    result.question_lean_code = question_lean_code
                if answer_lean_code is not None:
                    result.answer_lean_code = answer_lean_code
                if conversion_time is not None:
                    result.conversion_time = conversion_time
                if error_message is not None:
                    result.error_message = error_message
            else:
                # Create new result
                result = LeanConversionResult(
                    question_id=question_id,
                    converter_name=converter_name,
                    converter_type=converter_type,
                    question_lean_code=question_lean_code,
                    answer_lean_code=answer_lean_code,
                    conversion_time=conversion_time,
                    error_message=error_message
                )
                session.add(result)

            session.commit()
            session.refresh(result)
            return result
        finally:
            session.close()

    def get_lean_conversion_results(self, question_id: int) -> List[Dict[str, Any]]:
        """Get all Lean conversion results for a question."""
        session = self.get_session()
        try:
            results = session.query(LeanConversionResult).filter(
                LeanConversionResult.question_id == question_id
            ).order_by(LeanConversionResult.created_at.desc()).all()

            return [
                {
                    'id': r.id,
                    'converter_name': r.converter_name,
                    'converter_type': r.converter_type,
                    'question_lean_code': r.question_lean_code,
                    'answer_lean_code': r.answer_lean_code,
                    'verification_status': r.verification_status,
                    'verification_has_errors': r.verification_has_errors,
                    'verification_has_warnings': r.verification_has_warnings,
                    'verification_messages': json.loads(r.verification_messages) if r.verification_messages else [],
                    'verification_time': r.verification_time,
                    'conversion_time': r.conversion_time,
                    'error_message': r.error_message,
                    'created_at': r.created_at
                }
                for r in results
            ]
        finally:
            session.close()

    def update_lean_verification(self, result_id: int, verification_status: str,
                                has_errors: bool = False, has_warnings: bool = False,
                                messages: list = None, verification_time: float = None):
        """Update verification status for a Lean conversion result."""
        session = self.get_session()
        try:
            result = session.query(LeanConversionResult).filter(
                LeanConversionResult.id == result_id
            ).first()

            if result:
                result.verification_status = verification_status
                result.verification_has_errors = has_errors
                result.verification_has_warnings = has_warnings
                if messages is not None:
                    result.verification_messages = json.dumps(messages)
                if verification_time is not None:
                    result.verification_time = verification_time

                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_available_converters(self) -> List[Dict[str, Any]]:
        """Get list of all available converters with counts."""
        session = self.get_session()
        try:
            from sqlalchemy import distinct

            # Get unique converter names and types
            converters = session.query(
                LeanConversionResult.converter_name,
                LeanConversionResult.converter_type,
                func.count(LeanConversionResult.id).label('count')
            ).group_by(
                LeanConversionResult.converter_name,
                LeanConversionResult.converter_type
            ).all()

            result = [
                {
                    'converter_name': name,
                    'converter_type': conv_type,
                    'count': count
                }
                for name, conv_type, count in converters
            ]

            # Check for legacy lean data in processing_status
            legacy_count = session.query(ProcessingStatus).filter(
                (ProcessingStatus.lean_code.isnot(None)) |
                (ProcessingStatus.question_lean_code.isnot(None)) |
                (ProcessingStatus.answer_lean_code.isnot(None))
            ).count()

            if legacy_count > 0:
                result.append({
                    'converter_name': 'legacy',
                    'converter_type': 'legacy',
                    'count': legacy_count
                })

            return result
        finally:
            session.close()
