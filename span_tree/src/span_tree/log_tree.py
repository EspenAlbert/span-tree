from __future__ import annotations

import itertools
import logging
from asyncio import current_task as current_async_task
from contextlib import suppress, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from functools import cached_property
from threading import current_thread
from typing import Any, Callable

from rich.traceback import Traceback, Frame
from typing_extensions import TypeAlias

from span_tree.constants import ErrorTuple
from span_tree.log_action import LogAction

logger = logging.getLogger(__name__)


def next_tree_id() -> str:
    return f"t-{counter()}"


def async_task_name() -> str:
    with suppress(RuntimeError):
        if task := current_async_task():
            return task.get_name()
    return ""


def runtime_id() -> str:
    thread_name = current_thread().name
    if task_name := async_task_name():
        return f"{thread_name}.{task_name}"
    return thread_name


@dataclass
class LogTree:
    action_name: str = ""
    action_kwargs: dict[str, Any] = field(default_factory=dict, repr=False)
    tree_id: str = field(default_factory=next_tree_id)
    actions: dict[str, LogAction] = field(default_factory=dict)
    parent_tree: LogTree | None = None

    runtime_id: str = field(init=False, default_factory=runtime_id)
    _token: Token = field(init=False, repr=False)

    @cached_property
    def root_action(self):
        return self.actions["0"]

    def __post_init__(self):
        task_id = self.tree_id
        state[task_id] = self
        self.action_name = self.action_name or task_id
        self._token = _tree_id.set(task_id)
        kwargs = self.action_kwargs
        action = self.add_action(self.action_name, kwargs)
        if parent := self.parent_tree:
            action.add_tree_parent(parent.root_action.name, parent.tree_id)

    def __enter__(self) -> LogAction:
        return self.root_action.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.root_action.__exit__(exc_type, exc_val, exc_tb)

    def add_action(self, name: str, kwargs: dict[str, Any]) -> LogAction:
        # should be the only entry-point for creating an action
        # should ensure this task thread/task matches this action, and add the
        # reference if it is relevant
        now_runtime_id = runtime_id()
        if now_runtime_id != self.runtime_id:
            tree_id = next_tree_id()
            tree = LogTree(name, kwargs, parent_tree=self, tree_id=tree_id)
            self.current_action.add_tree_child(tree_id)
            return tree.root_action
        if self.actions:
            action_index, action = self.current_action_tree_index
            child_index: str = f"{action_index}/{action.next_child_index()}"
        else:
            child_index = "0"
        next_action = LogAction(name, on_exit=self.on_action_exit_tree, **kwargs)
        self.actions[child_index] = next_action
        return next_action

    def on_action_exit_tree(self, action: LogAction, error: ErrorTuple | None) -> None:
        if action is self.root_action:
            if error:
                logger.exception(error[1])
            self._root_done()

    def handle_error(
        self,
        error_tuple: ErrorTuple,
        caller_name: str,
        caller_path: str,
        caller_lineno: int,
        call_trace: str
    ) -> None:
        trace = Traceback.extract(*error_tuple, show_locals=True)
        if caller_path == __file__ and caller_name == "on_action_exit_tree":
            # called from logger.exception above
            self.root_action.add_exit_trace(trace, call_trace)
            return
        except_frame = Frame(
            filename=caller_path,
            lineno=caller_lineno,
            name=caller_name,
        )
        trace_stack = trace.stacks[0]
        # raise location, call location
        trace_stack.frames = [trace_stack.frames[-1], except_frame]
        self.current_action.add_except_trace(trace, call_trace)

    def _root_done(self):
        try:
            _tree_publisher(self)
        except BaseException as e:
            logger.exception(e)
        finally:
            state.pop(self.tree_id)
            _tree_id.reset(self._token)

    @property
    def current_action(self) -> LogAction:
        return next(a for a in reversed(self.actions.values()) if a.is_running)

    @property
    def current_action_tree_index(self) -> tuple[str, LogAction]:
        return next(
            (index, a) for index, a in reversed(self.actions.items()) if a.is_running
        )


state: dict[str, LogTree] = {}
counter = itertools.count().__next__
_tree_id: ContextVar[str] = ContextVar(f"{__name__}.tree_id")
_main_thread_token = _tree_id.set(next_tree_id())


def current_tree_or_none() -> LogTree | None:
    try:
        task_id = _tree_id.get()
    except LookupError:
        return None
    if task := state.get(task_id):
        return task
    return None


def current_action_or_none() -> LogAction | None:
    if task := current_tree_or_none():
        return task.current_action
    return None


def get_tree_state() -> dict[str, LogTree]:
    return state


def clear_tree_state():
    global counter, _main_thread_token
    state.clear()
    counter = itertools.count().__next__
    _tree_id.reset(_main_thread_token)
    _main_thread_token = _tree_id.set(f"t-{counter()}")


def default_tree_publisher(tree: LogTree):
    print(f"log-tree done: {tree}")


TreePublisher: TypeAlias = Callable[[LogTree], Any]
_tree_publisher: TreePublisher = default_tree_publisher


def set_tree_publisher(publisher: TreePublisher):
    global _tree_publisher
    _tree_publisher = publisher

@contextmanager
def temp_publisher(publisher: TreePublisher):
    global _tree_publisher
    old = _tree_publisher
    set_tree_publisher(publisher)
    try:
        yield old
    finally:
        set_tree_publisher(old)
