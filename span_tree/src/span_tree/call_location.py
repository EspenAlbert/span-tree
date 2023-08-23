from __future__ import annotations

from inspect import currentframe
from types import FrameType

_MODULE_NAME = __name__.split(".")[0]


def as_caller_name() -> str:
    frame: FrameType | None = currentframe().f_back
    for frames_back in range(10):
        if frame is None:
            return ""
        frame = frame.f_back
        package = frame.f_globals["__package__"]
        if package != _MODULE_NAME:
            break
    if frame is None:
        return ""
    code = frame.f_code
    if self := frame.f_locals.get("self"):
        name = f"{self.__class__.__name__}.{code.co_name}"
    else:
        name = code.co_name
    file = code.co_filename
    return f'File "{file}", line {frame.f_lineno}, in {name}'
