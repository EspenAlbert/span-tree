from __future__ import annotations

import logging
from collections import UserDict
from time import time
from typing import Any, Callable, Iterable, Literal, Type, TypeVar

from rich.traceback import Trace

from span_tree.call_location import as_caller_name
from span_tree.constants import (
    ASYNC_TASK_NAME,
    CALL_LOCATION,
    ON_EXIT,
    SPAN_NAME_FIELD,
    SPAN_STATUS_FIELD,
    STATUS_CREATED,
    STATUS_FAILED,
    STATUS_STARTED,
    STATUS_SUCCEEDED,
    TS_END_FIELD,
    TS_START_FIELD,
    ErrorTuple,
)

logger = logging.getLogger(__name__)
_NODE_COUNTER = "__node_counter__"
_CHILD_INDEX = "__child_counter__"
_CHILD_PLACEHOLDER = "__child_placeholder"
NODE_TYPE_EXIT_ERROR = "exit_error"
NODE_TYPE_EXCEPT_ERROR = "except_error"
NODE_TYPE_REF_SRC = "ref_src"
NODE_TYPE_REF_DEST = "ref_dest"
NODE_TYPE_TREE_CHILD = "trace_child"
NODE_TYPE_TREE_PARENT = "trace_parent"
_EVENTS = "__EVENTS__"
T = TypeVar("T")


def as_trace_child_id(key: str, value: Any) -> str | None:
    if key.startswith(NODE_TYPE_TREE_CHILD):
        assert isinstance(value, dict)
        return value["id"]
    return None


def as_trace_parent_id(key: str, value: Any) -> str | None:
    if key.startswith(NODE_TYPE_TREE_PARENT):
        assert isinstance(value, dict)
        return value["trace_id"]
    return None


class LogSpan(UserDict):
    def __init__(
        self,
        name: str,
        on_exit: Callable[[LogSpan, ErrorTuple | None], None] | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self[SPAN_STATUS_FIELD] = STATUS_CREATED
        self[_NODE_COUNTER] = 0
        self[SPAN_NAME_FIELD] = name
        self[_EVENTS] = []
        if on_exit:
            self[ON_EXIT] = on_exit

    def __enter__(self) -> LogSpan:
        assert self.status == STATUS_CREATED
        self[SPAN_STATUS_FIELD] = STATUS_STARTED
        self[TS_START_FIELD] = time()
        if CALL_LOCATION not in self:
            self[CALL_LOCATION] = as_caller_name()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self[TS_END_FIELD] = time()
        self[SPAN_STATUS_FIELD] = STATUS_FAILED if exc_val else STATUS_SUCCEEDED
        if on_complete := self.get(ON_EXIT):
            error_tuple = (exc_type, exc_val, exc_tb) if exc_val else None
            on_complete(self, error_tuple)

    def __repr__(self):
        return repr({k: v for k, v in self.items() if k != ON_EXIT})

    @property
    def name(self) -> str:
        return self[SPAN_NAME_FIELD]

    @property
    def call_location(self) -> str:
        return self[CALL_LOCATION]

    @property
    def duration_ms(self) -> float:
        assert self.is_done
        return self.timestamp_end - self.timestamp

    @property
    def is_ok(self) -> bool:
        assert self.is_done
        return self.status == STATUS_SUCCEEDED

    @property
    def status(self) -> Literal["running", "done"]:
        return self[SPAN_STATUS_FIELD]

    @property
    def is_running(self) -> bool:
        return self[SPAN_STATUS_FIELD] == STATUS_STARTED

    @property
    def is_done(self) -> bool:
        return self[SPAN_STATUS_FIELD] in {STATUS_FAILED, STATUS_SUCCEEDED}

    @property
    def timestamp(self) -> float:
        return self[TS_START_FIELD]

    @property
    def timestamp_end(self) -> float:
        return self[TS_END_FIELD]

    @property
    def async_task_name(self) -> str | None:
        return self.get(ASYNC_TASK_NAME)

    @property
    def refs_src(self) -> Iterable[str]:
        yield from self.events_filter(NODE_TYPE_REF_SRC, str)

    @property
    def refs_dest(self) -> Iterable[str]:
        yield from self.events_filter(NODE_TYPE_REF_DEST, str)

    def next_child_index(self) -> int:
        current_child = self.setdefault(_CHILD_INDEX, -1)
        child_number = self[_CHILD_INDEX] = current_child + 1
        # ADDING a child placeholder used for rendering the trace
        self.add_event(_CHILD_PLACEHOLDER, ...)
        return child_number

    def add_extra(self, extra: dict[str, Any]) -> None:
        self.add_event("extra", extra)

    def add_log(self, level: str, message: str) -> None:
        self.add_event(level, message)

    def add_trace_parent(self, name: str, trace_id: str) -> None:
        self.add_event(NODE_TYPE_TREE_PARENT, dict(name=name, trace_id=trace_id))

    def add_trace_child(self, child_id: str) -> None:
        self.add_event(NODE_TYPE_TREE_CHILD, dict(id=child_id))

    @property
    def events(self) -> list[tuple[str, Any]]:
        return [(k, v) for (k, v) in self[_EVENTS] if not k.startswith("__")]

    def events_filter(self, event_type: str, t: Type[T]) -> Iterable[T]:
        for i_type, event in self.events:
            if i_type == event_type:
                yield event

    def add_event(self, event_type: str, event: Any) -> None:
        self[_EVENTS].append((event_type, event))

    @property
    def events_with_child_placeholders(self) -> Iterable[tuple[str, Any]]:
        return self[_EVENTS]

    def add_exit_trace(self, trace: Trace, call_trace: str) -> None:
        self.add_event(NODE_TYPE_EXIT_ERROR, trace)
        self.add_event("call_trace", call_trace)

    def add_except_trace(self, trace: Trace, call_trace: str) -> None:
        self.add_event(NODE_TYPE_EXCEPT_ERROR, trace)
        self.add_event("call_trace", call_trace)

    def add_ref_src(self, ref: str):
        self.add_event(NODE_TYPE_REF_SRC, ref)

    def add_ref_dest(self, ref: str):
        self.add_event(NODE_TYPE_REF_DEST, ref)
