from typing import Any, Tuple, Iterable

Cmd = list[str]
MsgCmds = Iterable[Tuple[str, Cmd]]
Task = dict[str, Any]