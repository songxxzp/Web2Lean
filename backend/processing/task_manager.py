"""
Task manager for tracking and controlling long-running processing tasks.
"""
import threading
from typing import Dict, Any, Optional
from datetime import datetime


class ProcessingTask:
    """Represents a processing task with progress tracking."""

    def __init__(self, task_id: str, task_type: str, total: int):
        self.task_id = task_id
        self.task_type = task_type  # 'preprocessing' or 'lean_conversion'
        self.total = total
        self.processed = 0
        self.failed = 0
        self.status = 'running'  # 'running', 'paused', 'completed', 'error'
        self.current_question_id: Optional[int] = None
        self.started_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()

    def pause(self):
        """Pause the task."""
        if self.status == 'running':
            self.status = 'paused'
            self._pause_event.clear()

    def resume(self):
        """Resume the task."""
        if self.status == 'paused':
            self.status = 'running'
            self._pause_event.set()

    def stop(self):
        """Stop the task."""
        self.status = 'stopped'
        self._stop_event.set()
        self._pause_event.set()  # Release pause if paused

    def is_paused(self) -> bool:
        """Check if task is paused."""
        return not self._pause_event.is_set() and self.status == 'paused'

    def is_stopped(self) -> bool:
        """Check if task is stopped."""
        return self._stop_event.is_set()

    def wait_if_paused(self):
        """Block execution if task is paused."""
        self._pause_event.wait()

    def increment_progress(self, success: bool = True):
        """Increment processed counter."""
        self.processed += 1
        if not success:
            self.failed += 1

    def get_progress(self) -> Dict[str, Any]:
        """Get task progress information."""
        progress = {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'total': self.total,
            'processed': self.processed,
            'failed': self.failed,
            'status': self.status,
            'progress_percent': int(self.processed / self.total * 100) if self.total > 0 else 0,
            'started_at': self.started_at.isoformat(),
        }
        if self.current_question_id:
            progress['current_question_id'] = self.current_question_id
        if self.completed_at:
            progress['completed_at'] = self.completed_at.isoformat()
        if self.error_message:
            progress['error_message'] = self.error_message
        return progress


class TaskManager:
    """Manages processing tasks."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, ProcessingTask] = {}
        return cls._instance

    def create_task(self, task_type: str, total: int) -> ProcessingTask:
        """Create a new task."""
        task_id = f"{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        task = ProcessingTask(task_id, task_type, total)
        task._pause_event.set()  # Start unpaused
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[ProcessingTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_active_task(self, task_type: str) -> Optional[ProcessingTask]:
        """Get the currently active task of a specific type."""
        for task in self._tasks.values():
            if task.task_type == task_type and task.status in ['running', 'paused']:
                return task
        return None

    def pause_task(self, task_id: str) -> bool:
        """Pause a task."""
        task = self.get_task(task_id)
        if task:
            task.pause()
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a task."""
        task = self.get_task(task_id)
        if task:
            task.resume()
            return True
        return False

    def stop_task(self, task_id: str) -> bool:
        """Stop a task."""
        task = self.get_task(task_id)
        if task:
            task.stop()
            return True
        return False
