
from __future__ import annotations

import json
import subprocess
import sys
from typing import Tuple, Any

from pydash import chain as c
from toolz import valmap

from consts import UUID, DEPENDS
from task_types import MsgCmds, Task, Cmd


def show(*args, **kwargs) -> None:
    mapped_args = []
    for arg in args:
        if isinstance(arg, dict):
            try:
                mapped_args.append(json.dumps(arg, indent=4))
                continue
            except TypeError:
                pass
        mapped_args.append(arg)
    print(*mapped_args, **kwargs, file=sys.stderr)

def apply(pres: MsgCmds, task: Task, posts: MsgCmds) -> None:
    execute(pres)
    print(dumped := json.dumps(task))
    execute(posts)

def execute(cmd_dict: MsgCmds) -> None:
    for name, cmd in cmd_dict:
        if guard(cmd):
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
        if name:
            print(name, file=sys.stderr)

def guard(cmd: Cmd) -> bool:
    attrs = [part for part in cmd if ':' in part and ' ' not in part]
    if unalloweds := c(attrs).filter(lambda a: any(s in a for s in '_-.')).value():
        raise ValueError(f'Unallowed symbol in attribute: {unalloweds}')
    return True

def is_diff_or_exist(key: str, task: Task, old_task: Task) -> bool:
        if old_task:
            return task.get(key) != old_task.get(key)
        return bool(task.get(key))

def get_from_all(*paths, direct: bool = False) -> dict[str, dict[str, Any]] | dict[str, Any]:
    getter = c({UUID, *paths}).map(c().split('.').map(c().surround('"')).join('.')).map(lambda p: f'{p}: .{p}').join(', ').value()
    result = subprocess.run(
        f"task export | jq -r '[.[]  | {{{getter}}}]' ",
        capture_output=True,
        shell=True
    )
    map_to_dict = {data.pop(UUID): data for data in json.loads(result.stdout)}
    if direct:
        map_to_dict = valmap(lambda d: d[paths[0]], map_to_dict)
    return map_to_dict

def gather_recurrent_dependencies(update: Task = None) -> dict[str, list[str]]:
    orig_uuid_deps: dict[str, list[str]] = get_from_all(DEPENDS, direct=True)
    if update:
        orig_uuid_deps[update.get(UUID)] = update.get(DEPENDS, [])
    uuids = list(orig_uuid_deps.keys())
    new_uuid_deps: dict[str, list[str]] = {}
    while uuids:
        uuid = uuids.pop()
        deps = list(orig_uuid_deps.get(uuid) or [])
        new_uuid_deps[uuid] = []
        while deps:
            dep = deps.pop()
            new_uuid_deps[uuid].append(dep)
            deps.extend(orig_uuid_deps.get(dep) or [])
    return new_uuid_deps
