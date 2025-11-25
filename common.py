import sys
from typing import Iterable

from actions import Action
from task_types import Task
from utils import apply


def perform(task: Task, old_task: Task = None, *, actions: Iterable[Action]) -> None:
    if not task:
        sys.exit(0)
    pres, final, posts = Action.perform_all(task, old_task, actions=actions)
    apply(pres, final, posts)