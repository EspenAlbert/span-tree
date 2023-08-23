from __future__ import annotations

import itertools
import logging
from asyncio import current_task as current_async_task
from contextlib import contextmanager, suppress
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from functools import cached_property
from threading import current_thread
from typing import Any, Callable

from rich.traceback import Frame, Traceback
from typing_extensions import TypeAlias

from span_tree.constants import ErrorTuple
from span_tree.log_span import LogSpan

logger = logging.getLogger(__name__)


def next_trace_id() -> str:
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
class LogTrace:
    span_name: str = ""
    span_kwargs: dict[str, Any] = field(default_factory=dict, repr=False)
    trace_id: str = field(default_factory=next_trace_id)
    spans: dict[str, LogSpan] = field(default_factory=dict)
    parent_trace: LogTrace | None = None

    runtime_id: str = field(init=False, default_factory=runtime_id)
    _token: Token = field(init=False, repr=False)

    @cached_property
    def root_span(self):
        return self.spans["0"]

    def __post_init__(self):
        task_id = self.trace_id
        state[task_id] = self
        self.span_name = self.span_name or task_id
        self._token = _trace_id.set(task_id)
        kwargs = self.span_kwargs
        span = self.add_span(self.span_name, kwargs)
        if parent := self.parent_trace:
            span.add_trace_parent(parent.root_span.name, parent.trace_id)

    def __enter__(self) -> LogSpan:
        return self.root_span.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.root_span.__exit__(exc_type, exc_val, exc_tb)

    def add_span(self, name: str, kwargs: dict[str, Any]) -> LogSpan:
        # should be the only entry-point for creating an span
        # should ensure this task thread/task matches this span, and add the
        # reference if it is relevant
        now_runtime_id = runtime_id()
        if now_runtime_id != self.runtime_id:
            trace_id = next_trace_id()
            trace = LogTrace(name, kwargs, parent_trace=self, trace_id=trace_id)
            self.current_span.add_trace_child(trace_id)
            return trace.root_span
        if self.spans:
            span_index, span = self.current_span_tree_index
            child_index: str = f"{span_index}/{span.next_child_index()}"
        else:
            child_index = "0"
        next_span = LogSpan(name, on_exit=self.on_span_exit_trace, **kwargs)
        self.spans[child_index] = next_span
        return next_span

    def on_span_exit_trace(self, span: LogSpan, error: ErrorTuple | None) -> None:
        if span is self.root_span:
            if error:
                logger.exception(error[1])
            self._root_done()

    def handle_error(
        self,
        error_tuple: ErrorTuple,
        caller_name: str,
        caller_path: str,
        caller_lineno: int,
        call_trace: str,
    ) -> None:
        trace = Traceback.extract(*error_tuple, show_locals=True)
        if caller_path == __file__ and caller_name == "on_span_exit_trace":
            # called from logger.exception above
            self.root_span.add_exit_trace(trace, call_trace)
            return
        except_frame = Frame(
            filename=caller_path,
            lineno=caller_lineno,
            name=caller_name,
        )
        trace_stack = trace.stacks[0]
        # raise location, call location
        trace_stack.frames = [trace_stack.frames[-1], except_frame]
        self.current_span.add_except_trace(trace, call_trace)

    def _root_done(self):
        try:
            _trace_publisher(self)
        except BaseException as e:
            logger.exception(e)
        finally:
            state.pop(self.trace_id)
            _trace_id.reset(self._token)

    @property
    def current_span(self) -> LogSpan:
        return next(a for a in reversed(self.spans.values()) if a.is_running)

    @property
    def current_span_tree_index(self) -> tuple[str, LogSpan]:
        return next(
            (index, a) for index, a in reversed(self.spans.items()) if a.is_running
        )


state: dict[str, LogTrace] = {}
counter = itertools.count().__next__
_trace_id: ContextVar[str] = ContextVar(f"{__name__}.trace_id")
_main_thread_token = _trace_id.set(next_trace_id())


def current_trace_or_none() -> LogTrace | None:
    try:
        task_id = _trace_id.get()
    except LookupError:
        return None
    if task := state.get(task_id):
        return task
    return None


def current_span_or_none() -> LogSpan | None:
    if task := current_trace_or_none():
        return task.current_span
    return None


def get_trace_state() -> dict[str, LogTrace]:
    return state


def clear_trace_state():
    global counter, _main_thread_token
    state.clear()
    counter = itertools.count().__next__
    _trace_id.reset(_main_thread_token)
    _main_thread_token = _trace_id.set(f"t-{counter()}")


def default_trace_publisher(trace: LogTrace):
    print(f"log-trace done: {trace}")  # noqa: T201


TracePublisher: TypeAlias = Callable[[LogTrace], Any]
_trace_publisher: TracePublisher = default_trace_publisher


def set_trace_publisher(publisher: TracePublisher):
    global _trace_publisher
    _trace_publisher = publisher


@contextmanager
def temp_publisher(publisher: TracePublisher):
    global _trace_publisher
    old = _trace_publisher
    set_trace_publisher(publisher)
    try:
        yield old
    finally:
        set_trace_publisher(old)
