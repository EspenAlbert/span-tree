from __future__ import annotations

import logging
from functools import partial, wraps
from typing import Any, Callable, ContextManager, Protocol, TypeVar, cast

from zero_3rdparty.id_creator import uuid4_hex
from zero_3rdparty.object_name import as_name

from span_tree.constants import EXTRA_NAME, REF_DEST, REF_SRC
from span_tree.log_action import LogAction
from span_tree.log_tree import LogTree, current_tree_or_none


class LogExtra(Protocol):
    def __call__(
        self,
        msg: str = "",
        level: int = logging.INFO,
        /,
        *,
        ref_src: bool = False,
        ref_dest: str = "",
        **kwargs,
    ) -> str:
        ...


def logger_log_extra(name: str) -> tuple[logging.Logger, LogExtra]:
    logger = logging.getLogger(name)
    return logger, as_log_extra(logger)


def log_extra(
    logger: logging.Logger,
    msg: str = "",
    level: int = logging.INFO,
    /,
    *,
    ref_src: bool = False,
    ref_dest: str = "",
    **kwargs,
) -> str | None:
    extra: dict[str, Any] = {EXTRA_NAME: kwargs}
    ref = ""
    if ref_src:
        ref = uuid4_hex()
        extra[REF_SRC] = ref
    if ref_dest:
        extra[REF_DEST] = ref_dest
    logger.log(level, msg, extra=extra, stacklevel=2)
    return ref


def as_log_extra(logger: logging.Logger) -> LogExtra:
    return cast(LogExtra, partial(log_extra, logger))


def new_action(
    name: str, force_new_tree: bool = False, **kwargs
) -> ContextManager[LogAction]:
    if force_new_tree:
        return LogTree(name, action_kwargs=kwargs)
    if parent := current_tree_or_none():
        return parent.add_action(name, kwargs)
    return LogTree(name, action_kwargs=kwargs)


T = TypeVar("T")
__DECORATED_CHECK = f"{__name__}_decorator"


def action(
    name: str | T = "", force_new_tree: bool = False, **log_kwargs
) -> Callable[[T], T] | T:
    def decorator(f: T):
        nonlocal name
        if hasattr(f, __DECORATED_CHECK):
            return f
        assert callable(f)
        setattr(f, __DECORATED_CHECK, True)
        if name == "" or name is f:
            name = as_name(f)

        @wraps(f)
        def inner(*args, **kwargs):
            with new_action(name, force_new_tree=force_new_tree, **log_kwargs):
                return f(*args, **kwargs)

        return inner

    if callable(name):
        return decorator(name)
    return decorator


class ActionLogger(logging.LoggerAdapter):
    # cannot be named "extra" as that is the name of the extra on the instance
    def log_extra(
        self,
        msg: str = "",
        level: int = logging.INFO,
        /,
        *,
        ref_src: bool = False,
        ref_dest: str = "",
        **kwargs,
    ) -> str:
        return log_extra(
            self.logger, msg, level, ref_src=ref_src, ref_dest=ref_dest, **kwargs
        )

    @staticmethod
    def new_action(
        name: str, force_new_tree: bool = False, **kwargs
    ) -> ContextManager[LogAction]:
        return new_action(name, force_new_tree, **kwargs)

    def __call__(
        self, name: str, force_new_tree: bool = False, **kwargs
    ) -> ContextManager[LogAction]:
        return new_action(name, force_new_tree, **kwargs)

    @staticmethod
    def action(
        name: str | T = "", force_new_tree: bool = False, **log_kwargs
    ) -> Callable[[T], T] | T:
        return action(name, force_new_tree, **log_kwargs)


def get_logger(name: str) -> ActionLogger:
    logger = logging.getLogger(name)
    return ActionLogger(logger)


getLogger = get_logger
