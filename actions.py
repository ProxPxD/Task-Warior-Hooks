from __future__ import annotations

import json
import re
import sys
from time import sleep
from typing import Tuple, Iterable
import pydash as _
from pydash import chain as c
from toolz import merge_with
from typing_extensions import deprecated

from consts import UUID, DESCR, TAGS, DEPENDS, MODIFY, TASK, ID
from task_types import Task, MsgCmds
from utils import is_diff_or_exist, gather_recurrent_dependencies, get_from_all, show


class Action:
    def should_create(self, task: Task, old_task: Task = None) -> bool:
        return True

    def create(self, task: Task, old_task: Task = None) -> Tuple[MsgCmds, Task, MsgCmds]:
        raise NotImplementedError

    @classmethod
    def perform_all(cls, task: Task, old_task = None, *, actions: Iterable[Action]) -> Tuple[MsgCmds, Task, MsgCmds]:
        pres, posts = [], []
        for action in actions:
            if action.should_create(task, old_task):
                pre, task, post = action.create(task, old_task)
                pres.extend(pre)
                posts.extend(post)
        return pres, task, posts


class ReverseDependency(Action):
    REVERSE_DEPENDS_ATTR = 'for'

    def should_create(self, task: Task, old_task: Task = None) -> bool:
        return self.REVERSE_DEPENDS_ATTR in task

    def create(self, task: Task, old_task: Task = None) -> Tuple[MsgCmds, Task, MsgCmds]:
        dest: str = task.pop(self.REVERSE_DEPENDS_ATTR)
        task_filter = dest if dest.isnumeric() else f'description~"{dest}"'
        uuid = task[UUID]
        msg = f'Added as dependency for "{task_filter}"'
        cmd = [TASK, task_filter, MODIFY, f'{DEPENDS}:{uuid}']
        return [], task, [(msg, cmd)]


class Autotag(Action):
    same_tagging = [
        'buy', 'learn', 'move', 'design', 'server',
        'scraplang', 'langcode', 'game', 'taskwarrior',
    ]
    pattern_to_tags = {
        '(vault|bit)warden': ['vaultwarden', 'password', 'self.hosting'],
        'backup': ['backup', 'security'],
        '(prog|code)\w*': ['prog'],
        'obsi(dian)?': ['obsi', 'note'],
    }
    tag_to_tags = {
        'private': ['priv'],
    }
    def create(self, task: Task, old_task: Task = None) -> Tuple[MsgCmds, Task, MsgCmds]:
        tag_tags = self._create_tags_by_tags(task[TAGS])
        descr_tags = self._create_tags_by_descr(task[DESCR])
        task[TAGS] = list({*tag_tags, *descr_tags})
        return [], task, []

    def _create_tags_by_descr(self, descr: str) -> list[str]:
        tags = []
        self.pattern_to_tags.update({word: [word] for word in self.same_tagging})
        for pattern, tags in self.pattern_to_tags.items():
            if re.search(pattern, descr, flags=re.IGNORECASE):
                tags.extend(tags)
        return tags

    def _create_tags_by_tags(self, tags: list[str]) -> list[str]:
        for check_tag, add_tags in self.tag_to_tags.items():
            if check_tag in tags:
                tags.extend(add_tags)
        return tags

# @deprecated('The usage failed, order with MarkForDependencies')
# class RecurDependencies(Action):
#     def should_create(self, task: Task, old_task: Task = None) -> bool:
#         return is_diff_or_exist(DEPENDS, task, old_task)
#
#     def create(self, task: Task, old_task: Task = None) -> Tuple[MsgCmds, Task, MsgCmds]:
#         recur_deps = gather_recurrent_dependencies()
#         to_updates = {uuid: list(set(recur)-set(orig)) for uuid, (orig, recur) in merge_with(tuple)(orig_deps, recur_deps).items()}
#         updates = [('', [TASK, uuid, MODIFY, f'{DEPENDS}:{",".join((dep for dep in deps))}']) for uuid, deps in to_updates.items() if deps]
#         if updates:
#             updates.append(('Updated Dependencies!', []))
#         return [], task, updates


class MarkForDependencies(Action):
    DEP_COUNT = 'depCount'

    def should_create(self, task: Task, old_task: Task = None) -> bool:
        return is_diff_or_exist(DEPENDS, task, old_task) or not task.get(self.DEP_COUNT)

    def create(self, task: Task, old_task: Task = None) -> Tuple[MsgCmds, Task, MsgCmds]:
        recur_deps = gather_recurrent_dependencies(update=task)
        curr_uuid = task.get(UUID)
        counts: dict[str, str] = get_from_all(self.DEP_COUNT, direct=True)
        width = len(str(max(map(lambda c: int(float(c or '0')), counts.values()))))
        merger = _.over([c().get(0, []), c().get(1, 0)])
        to_updates = {uuid: len(deps) for uuid, (deps, count) in merge_with(merger, recur_deps, counts).items() if len(deps) != int(count)}
        task[self.DEP_COUNT] = f'{to_updates.get(curr_uuid, 0):0{width}}'
        updates = [('', [TASK, uuid, MODIFY, f'{self.DEP_COUNT}:{int(count):0{width}}']) for uuid, count in to_updates.items() if uuid != curr_uuid]
        if updates:
            updates.append(('Updated Dependency Counts!', []))
        return [], task, updates
