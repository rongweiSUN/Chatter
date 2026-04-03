"""并发任务管理器 — 管理后台任务执行，支持多任务并行与状态追踪。"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: int
    name: str
    status: TaskStatus = TaskStatus.RUNNING
    result: Any = None
    error: Optional[str] = None


class TaskManager:
    """轻量级后台任务管理器。

    submit() 提交任务到线程池，on_status_change 和 on_task_complete
    分别在任务数量变化和单个任务完成时被调用（从后台线程）。
    """

    def __init__(
        self,
        on_status_change: Callable[[str], None],
        on_task_complete: Callable[[Task], None],
        max_workers: int = 4,
    ):
        self._on_status_change = on_status_change
        self._on_task_complete = on_task_complete
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[int, Task] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def submit(self, name: str, fn: Callable, *args, **kwargs) -> int:
        with self._lock:
            task_id = self._next_id
            self._next_id += 1
            task = Task(id=task_id, name=name)
            self._tasks[task_id] = task

        self._notify_status_change()

        def _run():
            try:
                result = fn(*args, **kwargs)
                task.status = TaskStatus.COMPLETED
                task.result = result
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                print(f"[TaskManager] 任务{task_id}({name}) 异常: {e}", flush=True)
            finally:
                self._notify_status_change()
                try:
                    self._on_task_complete(task)
                except Exception as ce:
                    print(f"[TaskManager] 完成回调异常: {ce}", flush=True)
                with self._lock:
                    self._tasks.pop(task_id, None)
                    if not self._tasks:
                        self._next_id = 1

        self._executor.submit(_run)
        return task_id

    def get_running_tasks(self) -> list[Task]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def has_running_tasks(self) -> bool:
        with self._lock:
            return any(t.status == TaskStatus.RUNNING for t in self._tasks.values())

    def get_status_text(self) -> str:
        running = self.get_running_tasks()
        if not running:
            return "就绪"
        if len(running) == 1:
            return f"正在执行任务{running[0].id}: {running[0].name}"
        return f"正在执行 {len(running)} 个任务"

    def get_status_for_ui(self) -> dict:
        running = self.get_running_tasks()
        return {
            "status": "executing" if running else "idle",
            "tasks": [{"id": t.id, "name": t.name} for t in running],
        }

    def _notify_status_change(self):
        try:
            self._on_status_change(self.get_status_text())
        except Exception as e:
            print(f"[TaskManager] 状态回调异常: {e}", flush=True)

    def shutdown(self):
        self._executor.shutdown(wait=False)
