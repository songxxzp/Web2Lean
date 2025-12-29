"""
APScheduler-based task scheduler for Web2Lean.
"""
import logging
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


logger = logging.getLogger(__name__)


class TaskScheduler:
    """Manages scheduled tasks for crawling, preprocessing, Lean conversion, and verification."""

    def __init__(self, db_manager, settings):
        """
        Initialize the task scheduler.

        Args:
            db_manager: DatabaseManager instance
            settings: Settings instance
        """
        self.db = db_manager
        self.settings = settings
        self.scheduler = BackgroundScheduler()
        self.jobs = {}  # Map task_name -> job_id
        self.running_tasks: Set[str] = set()  # Track currently running task names
        self.lock = threading.Lock()  # Thread lock for running_tasks

    def start(self):
        """Start the scheduler and load all enabled tasks."""
        if not self.settings.scheduler_enabled:
            logger.info("Scheduler is disabled in settings")
            return

        try:
            self.scheduler.start()
            logger.info("Task scheduler started")

            # Load all enabled scheduled tasks from database
            self._load_scheduled_tasks()
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")

    def shutdown(self):
        """Shutdown the scheduler."""
        try:
            self.scheduler.shutdown(wait=False)
            logger.info("Task scheduler shut down")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

    def _load_scheduled_tasks(self):
        """Load all scheduled tasks from database and add them to the scheduler."""
        try:
            session = self.db.get_session()
            from backend.database.schema import ScheduledTask

            tasks = session.query(ScheduledTask).filter(
                ScheduledTask.enabled == True
            ).all()

            for task in tasks:
                self._add_scheduled_task(task)

            session.close()
            logger.info(f"Loaded {len(tasks)} scheduled tasks")
        except Exception as e:
            logger.error(f"Error loading scheduled tasks: {e}")

    def _add_scheduled_task(self, task):
        """
        Add a scheduled task to the scheduler.

        Args:
            task: ScheduledTask object
        """
        try:
            # Calculate total interval in minutes
            total_minutes = (
                task.interval_days * 24 * 60 +
                task.interval_hours * 60 +
                task.interval_minutes
            )

            if total_minutes == 0:
                logger.warning(f"Task {task.task_name} has zero interval, skipping")
                return

            # Create job function based on task type
            job_func = self._get_job_function(task)

            # Add job to scheduler
            # coalesce=True: 如果错过了多次执行，只执行一次（在启动时立即执行）
            # max_instances=1: 同一时间只允许一个实例运行
            trigger = IntervalTrigger(minutes=total_minutes)
            job = self.scheduler.add_job(
                job_func,
                trigger=trigger,
                id=task.task_name,
                name=task.task_name,
                replace_existing=True,
                coalesce=True,
                max_instances=1
            )

            self.jobs[task.task_name] = job.id
            logger.info(f"Added scheduled task: {task.task_name} (every {total_minutes} minutes)")

        except Exception as e:
            logger.error(f"Error adding scheduled task {task.task_name}: {e}")

    def _get_job_function(self, task):
        """
        Get the job function based on task type.

        Args:
            task: ScheduledTask object

        Returns:
            Callable function to execute
        """
        task_type = task.task_type
        task_name = task.task_name

        def run_crawl_job():
            """Execute crawl job with overlap protection."""
            if not self._try_start_task(task_name):
                logger.warning(f"Crawl task {task_name} is already running, skipping this scheduled execution")
                return
            try:
                self._execute_crawl_task(task)
            finally:
                self._on_task_finished(task)

        def run_preprocess_job():
            """Execute preprocess job with overlap protection."""
            if not self._try_start_task(task_name):
                logger.warning(f"Preprocess task {task_name} is already running, skipping this scheduled execution")
                return
            try:
                self._execute_preprocess_task(task)
            finally:
                self._on_task_finished(task)

        def run_convert_lean_job():
            """Execute convert_lean job with overlap protection."""
            if not self._try_start_task(task_name):
                logger.warning(f"Convert lean task {task_name} is already running, skipping this scheduled execution")
                return
            try:
                self._execute_convert_lean_task(task)
            finally:
                self._on_task_finished(task)

        def run_verify_job():
            """Execute verify job with overlap protection."""
            if not self._try_start_task(task_name):
                logger.warning(f"Verify task {task_name} is already running, skipping this scheduled execution")
                return
            try:
                self._execute_verify_task(task)
            finally:
                self._on_task_finished(task)

        job_functions = {
            'crawl': run_crawl_job,
            'preprocess': run_preprocess_job,
            'convert_lean': run_convert_lean_job,
            'verify': run_verify_job
        }

        return job_functions.get(task_type, lambda: logger.warning(f"Unknown task type: {task_type}"))

    def _try_start_task(self, task_name: str) -> bool:
        """
        Try to mark a task as running.

        Args:
            task_name: Name of the task

        Returns:
            True if task can start (not already running), False if skipped
        """
        with self.lock:
            if task_name in self.running_tasks:
                return False
            self.running_tasks.add(task_name)
            logger.debug(f"Task {task_name} marked as running")
            return True

    def _on_task_finished(self, task):
        """
        Called when a task finishes. Check if we missed a scheduled run.

        Args:
            task: ScheduledTask object
        """
        # Mark as not running
        with self.lock:
            if task.task_name in self.running_tasks:
                self.running_tasks.remove(task.task_name)
            logger.debug(f"Task {task.task_name} marked as finished")

        # Check if task is still enabled
        if not task.enabled:
            logger.debug(f"Task {task.task_name} is disabled, not checking for missed runs")
            return

        # Calculate the interval
        total_minutes = (
            (task.interval_days or 0) * 24 * 60 +
            (task.interval_hours or 0) * 60 +
            (task.interval_minutes or 0)
        )

        if total_minutes == 0:
            return

        # Check if next_run time is in the past (we missed a scheduled run)
        if task.next_run:
            try:
                from datetime import datetime
                next_run_time = datetime.fromisoformat(task.next_run)
                now = datetime.now()

                if next_run_time < now:
                    # We missed at least one scheduled run
                    logger.info(f"Task {task.task_name} finished but missed scheduled run (was scheduled for {next_run_time}, now {now})")
                    logger.info(f"Immediately restarting task {task.task_name}")

                    # Get the job function and execute it
                    job_func = self._get_job_function(task)
                    # Run in a separate thread to avoid blocking the scheduler
                    import threading
                    thread = threading.Thread(target=job_func, name=f"catchup-{task.task_name}")
                    thread.start()
            except Exception as e:
                logger.error(f"Error checking for missed run of task {task.task_name}: {e}")

    def _is_task_enabled(self, task_name: str) -> bool:
        """
        Check if a task is still enabled in the database.

        Args:
            task_name: Name of the task

        Returns:
            True if enabled, False otherwise
        """
        try:
            session = self.db.get_session()
            from backend.database.schema import ScheduledTask
            task = session.query(ScheduledTask).filter(
                ScheduledTask.task_name == task_name
            ).first()
            enabled = task.enabled if task else False
            session.close()
            return enabled
        except Exception as e:
            logger.error(f"Error checking task enabled status: {e}")
            return False

    def _execute_crawl_task(self, task):
        """Execute a crawl task."""
        logger.info(f"Executing crawl task: {task.task_name}")

        # Check if task is still enabled
        if not self._is_task_enabled(task.task_name):
            logger.warning(f"Task {task.task_name} was disabled, skipping execution")
            return

        try:
            from backend.crawlers import run_crawler

            site_id = task.site_id
            config = json.loads(task.config_json) if task.config_json else {}

            # Run crawler
            result = run_crawler(site_id=site_id, mode='incremental', **config)

            # Update last_run time
            self._update_task_run_time(task.task_name, success=True)

            logger.info(f"Crawl task {task.task_name} completed: {result}")
        except Exception as e:
            logger.error(f"Error executing crawl task {task.task_name}: {e}")
            self._update_task_run_time(task.task_name, success=False)

    def _execute_preprocess_task(self, task):
        """Execute a preprocess task."""
        logger.info(f"Executing preprocess task: {task.task_name}")

        # Check if task is still enabled
        if not self._is_task_enabled(task.task_name):
            logger.warning(f"Task {task.task_name} was disabled, skipping execution")
            return

        try:
            from backend.processing import LLMProcessor

            # Get raw questions
            limit = 10  # Default batch size
            if task.config_json:
                config = json.loads(task.config_json)
                limit = config.get('limit', 10)

            questions = self.db.get_questions_by_status('raw', limit=limit)

            if not questions:
                logger.info(f"No raw questions to preprocess for task {task.task_name}")
                self._update_task_run_time(task.task_name, success=True)
                return

            # Create processor
            processor = LLMProcessor(
                db_manager=self.db,
                api_key=self.settings.zhipu_api_key,
                text_model=self.settings.glm_text_model,
                vision_model=self.settings.glm_vision_model,
                max_length=self.settings.preprocessing_max_length
            )

            # Process questions
            question_ids = [q['id'] for q in questions]
            results = processor.process_questions_batch(
                question_ids,
                concurrency=self.settings.preprocessing_concurrency
            )

            success_count = sum(1 for r in results if r.get('success'))
            logger.info(f"Preprocessed {success_count}/{len(question_ids)} questions")

            self._update_task_run_time(task.task_name, success=True)
        except Exception as e:
            logger.error(f"Error executing preprocess task {task.task_name}: {e}")
            self._update_task_run_time(task.task_name, success=False)

    def _execute_convert_lean_task(self, task):
        """Execute a Lean conversion task."""
        logger.info(f"Executing convert_lean task: {task.task_name}")

        # Check if task is still enabled
        if not self._is_task_enabled(task.task_name):
            logger.warning(f"Task {task.task_name} was disabled, skipping execution")
            return

        try:
            from backend.processing import LeanConverter

            # Get config
            converter_name = 'kimina-7b'  # Default
            limit = 10
            if task.config_json:
                config = json.loads(task.config_json)
                converter_name = config.get('converter_name', converter_name)
                limit = config.get('limit', limit)

            # Get preprocessed questions not converted by this converter
            questions = self.db.get_questions_not_converted_by(converter_name, limit=limit)

            if not questions:
                logger.info(f"No questions to convert for task {task.task_name}")
                self._update_task_run_time(task.task_name, success=True)
                return

            # Create converter
            converter = LeanConverter(
                db_manager=self.db,
                converter_name=converter_name
            )

            # Convert questions
            for question in questions:
                try:
                    converter.convert_question(question['id'])
                except Exception as e:
                    logger.error(f"Error converting question {question['id']}: {e}")

            logger.info(f"Lean conversion task {task.task_name} completed")
            self._update_task_run_time(task.task_name, success=True)
        except Exception as e:
            logger.error(f"Error executing convert_lean task {task.task_name}: {e}")
            self._update_task_run_time(task.task_name, success=False)

    def _execute_verify_task(self, task):
        """Execute a verification task."""
        logger.info(f"Executing verify task: {task.task_name}")

        # Check if task is still enabled
        if not self._is_task_enabled(task.task_name):
            logger.warning(f"Task {task.task_name} was disabled, skipping execution")
            return

        try:
            from backend.processing import LeanVerifier

            # Get config
            converter_name = 'kimina-7b'
            if task.config_json:
                config = json.loads(task.config_json)
                converter_name = config.get('converter_name', converter_name)

            # Get unverified conversions
            results = self.db.get_unverified_conversions(converter_name=converter_name, limit=10)

            if not results:
                logger.info(f"No conversions to verify for task {task.task_name}")
                self._update_task_run_time(task.task_name, success=True)
                return

            # Create verifier
            verifier = LeanVerifier(db_manager=self.db)

            # Verify conversions
            for result in results:
                try:
                    verifier.verify_conversion(result['id'])
                except Exception as e:
                    logger.error(f"Error verifying conversion {result['id']}: {e}")

            logger.info(f"Verification task {task.task_name} completed")
            self._update_task_run_time(task.task_name, success=True)
        except Exception as e:
            logger.error(f"Error executing verify task {task.task_name}: {e}")
            self._update_task_run_time(task.task_name, success=False)

    def _update_task_run_time(self, task_name: str, success: bool = True):
        """
        Update the last_run time for a task.

        Args:
            task_name: Name of the task
            success: Whether the task succeeded
        """
        try:
            session = self.db.get_session()
            from backend.database.schema import ScheduledTask

            task = session.query(ScheduledTask).filter(
                ScheduledTask.task_name == task_name
            ).first()

            if task:
                task.last_run = datetime.now().isoformat()
                # Calculate next run time
                total_minutes = (
                    task.interval_days * 24 * 60 +
                    task.interval_hours * 60 +
                    task.interval_minutes
                )
                if total_minutes > 0:
                    next_run = datetime.now() + timedelta(minutes=total_minutes)
                    task.next_run = next_run.isoformat()
                session.commit()

            session.close()
        except Exception as e:
            logger.error(f"Error updating task run time: {e}")

    def add_task(self, task_name: str, task_type: str, site_id: Optional[int] = None,
                interval_days: int = 0, interval_hours: int = 24, interval_minutes: int = 0,
                enabled: bool = False, config_json: str = None) -> Dict[str, Any]:
        """
        Add a new scheduled task.

        Args:
            task_name: Unique name for the task
            task_type: Type of task ('crawl', 'preprocess', 'convert_lean', 'verify')
            site_id: Site ID (for crawl tasks)
            interval_days: Interval in days
            interval_hours: Interval in hours
            interval_minutes: Interval in minutes
            enabled: Whether the task is enabled
            config_json: Additional configuration as JSON string

        Returns:
            Created task info
        """
        try:
            session = self.db.get_session()
            from backend.database.schema import ScheduledTask

            # Check if task already exists
            existing = session.query(ScheduledTask).filter(
                ScheduledTask.task_name == task_name
            ).first()

            if existing:
                session.close()
                return {'error': 'Task with this name already exists'}

            # Create new task
            task = ScheduledTask(
                task_name=task_name,
                task_type=task_type,
                site_id=site_id,
                interval_days=interval_days,
                interval_hours=interval_hours,
                interval_minutes=interval_minutes,
                enabled=enabled,
                config_json=config_json
            )
            session.add(task)
            session.commit()
            session.refresh(task)

            # If enabled, add to scheduler
            if enabled:
                self._add_scheduled_task(task)

            session.close()

            return {
                'id': task.id,
                'task_name': task.task_name,
                'task_type': task.task_type,
                'site_id': task.site_id,
                'interval_days': task.interval_days,
                'interval_hours': task.interval_hours,
                'interval_minutes': task.interval_minutes,
                'enabled': task.enabled,
                'config_json': task.config_json
            }
        except Exception as e:
            logger.error(f"Error adding scheduled task: {e}")
            return {'error': str(e)}

    def update_task(self, task_name: str, **kwargs) -> Dict[str, Any]:
        """
        Update an existing scheduled task.

        Args:
            task_name: Name of the task to update
            **kwargs: Fields to update

        Returns:
            Updated task info or error
        """
        try:
            session = self.db.get_session()
            from backend.database.schema import ScheduledTask

            task = session.query(ScheduledTask).filter(
                ScheduledTask.task_name == task_name
            ).first()

            if not task:
                session.close()
                return {'error': 'Task not found'}

            # Check if task is being disabled
            was_enabled = task.enabled
            is_being_disabled = 'enabled' in kwargs and kwargs['enabled'] == False and was_enabled

            # Remove old job from scheduler if exists
            if task.task_name in self.jobs:
                try:
                    self.scheduler.remove_job(task.task_name)
                    del self.jobs[task.task_name]
                except:
                    pass

            # Update fields
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)

            session.commit()
            session.refresh(task)

            # Add updated job to scheduler if enabled
            if task.enabled:
                self._add_scheduled_task(task)

            session.close()

            # If task was disabled and is currently running, note that it will complete
            # but won't run again until re-enabled
            if is_being_disabled:
                with self.lock:
                    if task_name in self.running_tasks:
                        logger.warning(f"Task {task_name} is currently running and will complete. It will not run again until re-enabled.")

            return {
                'id': task.id,
                'task_name': task.task_name,
                'task_type': task.task_type,
                'site_id': task.site_id,
                'interval_days': task.interval_days,
                'interval_hours': task.interval_hours,
                'interval_minutes': task.interval_minutes,
                'enabled': task.enabled,
                'config_json': task.config_json,
                'last_run': task.last_run,
                'next_run': task.next_run
            }
        except Exception as e:
            logger.error(f"Error updating scheduled task: {e}")
            return {'error': str(e)}

    def delete_task(self, task_name: str) -> bool:
        """
        Delete a scheduled task.

        Args:
            task_name: Name of the task to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            # Remove from scheduler
            if task_name in self.jobs:
                try:
                    self.scheduler.remove_job(task_name)
                    del self.jobs[task_name]
                except:
                    pass

            # Remove from database
            session = self.db.get_session()
            from backend.database.schema import ScheduledTask

            task = session.query(ScheduledTask).filter(
                ScheduledTask.task_name == task_name
            ).first()

            if task:
                session.delete(task)
                session.commit()
                session.close()
                return True

            session.close()
            return False
        except Exception as e:
            logger.error(f"Error deleting scheduled task: {e}")
            return False

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all scheduled tasks.

        Returns:
            List of task info dictionaries
        """
        try:
            session = self.db.get_session()
            from backend.database.schema import ScheduledTask, Site

            tasks = session.query(ScheduledTask).all()

            result = []
            for task in tasks:
                # Get site name if applicable
                site_name = None
                if task.site_id:
                    site = session.query(Site).filter(Site.site_id == task.site_id).first()
                    if site:
                        site_name = site.site_name

                result.append({
                    'id': task.id,
                    'task_name': task.task_name,
                    'task_type': task.task_type,
                    'site_id': task.site_id,
                    'site_name': site_name,
                    'interval_days': task.interval_days,
                    'interval_hours': task.interval_hours,
                    'interval_minutes': task.interval_minutes,
                    'enabled': task.enabled,
                    'config_json': task.config_json,
                    'last_run': task.last_run,
                    'next_run': task.next_run,
                    'created_at': task.created_at
                })

            session.close()
            return result
        except Exception as e:
            logger.error(f"Error getting scheduled tasks: {e}")
            return []

    def get_task_status(self) -> Dict[str, Any]:
        """
        Get the status of the scheduler and all jobs.

        Returns:
            Scheduler status info including running tasks
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None
            })

        # Get list of currently running tasks
        with self.lock:
            running_tasks = list(self.running_tasks)

        return {
            'running': self.scheduler.running,
            'jobs': jobs,
            'running_tasks': running_tasks
        }
