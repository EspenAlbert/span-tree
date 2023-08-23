import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from typing import Callable, TextIO, TypeVar

from typing_extensions import ParamSpec
from zero_3rdparty.error import error_and_traceback
from zero_3rdparty.logging_utils import setup_logging
from zero_3rdparty.object_name import as_name

from span_tree.call_location import as_caller_name
from span_tree.constants import CALL_LOCATION, EXTRA_NAME, REF_DEST, REF_SRC
from span_tree.log_trace import (
    LogTrace,
    current_trace_or_none,
    next_trace_id,
    set_trace_publisher,
)


class MyHandler(logging.Handler):
    def __init__(
        self,
        level=logging.NOTSET,
        stream: TextIO = sys.stdout,
        render_traces: bool = False,
    ):
        super().__init__(level)
        self.stream = stream
        if render_traces:
            from span_tree.rich_rendering import print_trace_call

            set_trace_publisher(print_trace_call())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            has_msg = record.msg
            text = self.format(record)
            if has_msg:
                self.stream.write(f"{text}\n")
            extra = getattr(record, EXTRA_NAME, None)
            if trace := current_trace_or_none():
                if exc_info := record.exc_info:
                    trace.handle_error(
                        exc_info,  # type: ignore
                        caller_name=record.funcName,
                        caller_path=record.pathname,
                        caller_lineno=record.lineno,
                        call_trace=text,
                    )
                    return
                span = trace.current_span
                if has_msg:
                    span.add_log(record.levelname, text)
                if extra:
                    span.add_extra(extra)
                if ref := getattr(record, REF_SRC, None):
                    span.add_ref_src(ref)
                if ref := getattr(record, REF_DEST, None):
                    span.add_ref_dest(ref)
                return
            if extra:
                self._dump_extras(record, extra)
        except Exception as e:
            error_str = error_and_traceback(e)
            self.stream.write(f"{error_str}\n")

    def _dump_extras(self, record: logging.LogRecord, extra: dict):
        record2 = logging.LogRecord(
            **{
                **record.__dict__,
                "msg": f"log_extra_no_parent: {extra!r}",
                "level": record.levelno,
            }
        )
        self.stream.write(self.format(record2))
        self.stream.write("\n")


def create_handler(stream: TextIO, render_traces: bool) -> MyHandler:
    return MyHandler(stream=stream, render_traces=render_traces)


def configure(
    api_key: str = "",
    /,
    render_traces: bool = False,
    tags: dict[str, str] | None = None,
    disable_prev_logger: bool = False,
):
    tags = tags or {}
    handler_dict = {
        "()": "span_tree.handler.create_handler",
        "level": logging.INFO,
        "stream": "ext://sys.stdout",
        "render_traces": render_traces,
    }

    setup_logging(handler_dict, disable_stream_handler=disable_prev_logger)


ParamSpecT = ParamSpec("ParamSpecT")
ReturnT = TypeVar("ReturnT")
_skip_wrap = "__skip_wrap"


def skip_wrap(func: Callable) -> None:
    setattr(func, _skip_wrap, True)


def wrap_call(func: Callable[ParamSpecT, ReturnT]) -> Callable[ParamSpecT, ReturnT]:
    func_name = as_name(func)
    if (
        getattr(func, _skip_wrap, False)
        or func_name == "concurrent.futures.thread._worker"
    ):
        return func
    parent_trace = current_trace_or_none()
    span_name = as_name(func)
    caller_location = as_caller_name()
    trace_id = next_trace_id()
    if parent_trace:
        parent_trace.current_span.add_trace_child(trace_id)

    def wrapped_func(*args: ParamSpecT.args, **kwargs: ParamSpecT.kwargs) -> ReturnT:
        task = LogTrace(
            span_name,
            span_kwargs={CALL_LOCATION: caller_location},
            parent_trace=parent_trace,
            trace_id=trace_id,
        )
        with task:
            return func(*args, **kwargs)

    return wrapped_func


def monkeypatch_submit():
    old_submit = ThreadPoolExecutor.submit

    def new_submit(self, fn, /, *args, **kwargs):
        wrapped_func = wrap_call(fn)
        return old_submit(self, wrapped_func, *args, **kwargs)

    ThreadPoolExecutor.submit = new_submit


def monkeypatch_thread_init():
    old_init = Thread.__init__

    def new_init(
        self: Thread,
        group=None,
        target=None,
        name=None,
        args=(),
        kwargs=None,
        *,
        daemon=None,
    ):
        old_init(self, group, target, name, args, kwargs, daemon=daemon)
        if target:
            self._target = wrap_call(target)  # type: ignore

    Thread.__init__ = new_init


if not os.environ.get("LOG_TREE_SKIP_MONKEYPATCH"):
    monkeypatch_submit()
    monkeypatch_thread_init()
