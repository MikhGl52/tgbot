import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DownloadTask:
    user_id: int
    url: str
    format_id: str
    service: str  # 'youtube', 'instagram', 'music'
    title: str
    quality: Optional[str] = None


class UserQueue:
    def __init__(self):
        self.tasks: list[DownloadTask] = []
        self.is_processing: bool = False


class QueueManager:
    def __init__(self):
        self._queues: dict[int, UserQueue] = {}
        self._callbacks: dict[str, callable] = {}

    def get_queue(self, user_id: int) -> UserQueue:
        if user_id not in self._queues:
            self._queues[user_id] = UserQueue()
        return self._queues[user_id]

    def add_task(self, task: DownloadTask) -> int:
        """Добавляет задачу, возвращает позицию в очереди"""
        queue = self.get_queue(task.user_id)
        # Проверка дубликата
        for existing in queue.tasks:
            if existing.url == task.url and existing.format_id == task.format_id:
                return -1  # уже в очереди
        queue.tasks.append(task)
        return len(queue.tasks)

    def get_next_task(self, user_id: int) -> Optional[DownloadTask]:
        queue = self.get_queue(user_id)
        if queue.tasks:
            return queue.tasks[0]
        return None

    def complete_task(self, user_id: int):
        """Удаляет первую задачу после завершения"""
        queue = self.get_queue(user_id)
        if queue.tasks:
            queue.tasks.pop(0)
        if not queue.tasks:
            queue.is_processing = False

    def remove_task(self, user_id: int, index: int) -> bool:
        """Удаляет задачу по индексу (1-based)"""
        queue = self.get_queue(user_id)
        idx = index - 1
        if idx < 0 or idx >= len(queue.tasks):
            return False
        # Нельзя удалить задачу которая сейчас качается
        if idx == 0 and queue.is_processing:
            return False
        queue.tasks.pop(idx)
        return True

    def get_tasks(self, user_id: int) -> list[DownloadTask]:
        return self.get_queue(user_id).tasks

    def is_processing(self, user_id: int) -> bool:
        return self.get_queue(user_id).is_processing

    def set_processing(self, user_id: int, value: bool):
        self.get_queue(user_id).is_processing = value


queue_manager = QueueManager()