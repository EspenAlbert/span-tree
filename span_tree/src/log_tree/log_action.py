from __future__ import annotations
import logging
from collections import UserDict
from time import time
from typing import Callable, Literal, Any, Iterable

from rich.traceback import Trace

from log_tree.call_location import as_caller_name
from log_tree.constants import (
    ACTION_STATUS_FIELD,
    STATUS_CREATED,
    ON_EXIT,
    STATUS_STARTED,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    ASYNC_TASK_NAME,
    ACTION_NAME_FIELD,
    TS_START_FIELD,
    TS_END_FIELD, ErrorTuple, CALL_LOCATION,
)

logger = logging.getLogger(__name__)
_NODE_COUNTER = "__node_counter__"
_CHILD_INDEX = "__child_counter__"
_CHILD_PLACEHOLDER = "__child_placeholder"
NODE_TYPE_EXIT_ERROR = "exit_error"
NODE_TYPE_EXCEPT_ERROR = "except_error"
NODE_TYPE_REF_SRC = "ref_src"
NODE_TYPE_REF_DEST = "ref_dest"
NODE_TYPE_TREE_CHILD = "tree_child"
NODE_TYPE_TREE_PARENT = "tree_parent"


def as_tree_child_id(key: str, value: Any) -> str | None:
    if key.startswith(NODE_TYPE_TREE_CHILD):
        assert isinstance(value, dict)
        return value["id"]
    return None


def as_tree_parent_id(key: str, value: Any) -> str | None:
    if key.startswith(NODE_TYPE_TREE_PARENT):
        assert isinstance(value, dict)
        return value["tree_id"]
    return None
class LogAction(UserDict):
    def __init__(
        self,
        name: str,
        on_exit: Callable[[LogAction, ErrorTuple | None], None] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self[ACTION_STATUS_FIELD] = STATUS_CREATED
        self[_NODE_COUNTER] = 0
        self[ACTION_NAME_FIELD] = name
        if on_exit:
            self[ON_EXIT] = on_exit

    def __enter__(self) -> LogAction:
        assert self.status == STATUS_CREATED
        self[ACTION_STATUS_FIELD] = STATUS_STARTED
        self[TS_START_FIELD] = time()
        if CALL_LOCATION not in self:
            self[CALL_LOCATION] = as_caller_name()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self[TS_END_FIELD] = time()
        self[ACTION_STATUS_FIELD] = STATUS_FAILED if exc_val else STATUS_SUCCEEDED
        if on_complete := self.get(ON_EXIT):
            error_tuple = (exc_type, exc_val, exc_tb) if exc_val else None
            on_complete(self, error_tuple)

    def __repr__(self):
        return repr({k: v for k, v in self.items() if k != ON_EXIT})

    @property
    def name(self) -> str:
        return self[ACTION_NAME_FIELD]

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
        return self[ACTION_STATUS_FIELD]

    @property
    def is_running(self) -> bool:
        return self[ACTION_STATUS_FIELD] == STATUS_STARTED

    @property
    def is_done(self) -> bool:
        return self[ACTION_STATUS_FIELD] in {STATUS_FAILED, STATUS_SUCCEEDED}

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
        for key, ref in self.iter_nodes():
            if key.startswith(NODE_TYPE_REF_SRC):
                yield ref

    @property
    def refs_dest(self) -> Iterable[str]:
        for key, ref in self.iter_nodes():
            if key.startswith(NODE_TYPE_REF_DEST):
                yield ref

    def next_child_index(self) -> int:
        current_child = self.setdefault(_CHILD_INDEX, -1)
        child_number = self[_CHILD_INDEX] = current_child + 1
        # ADDING a child placeholder used for rendering the tree
        self[f"{_CHILD_PLACEHOLDER}{child_number}"] = ...
        return child_number

    def _next_node_counter_key(self, group: str) -> str:
        counter = self[_NODE_COUNTER] + 1
        self[_NODE_COUNTER] = counter
        return f"{group}_{counter}"

    def add_extra(self, extra: dict[str, Any]) -> None:
        self[self._next_node_counter_key("extra")] = extra

    def add_log(self, level: str, message: str) -> None:
        self[self._next_node_counter_key(level)] = message

    def add_tree_parent(self, name: str, tree_id: str) -> None:
        self[self._next_node_counter_key(NODE_TYPE_TREE_PARENT)] = dict(
            name=name, tree_id=tree_id
        )

    def add_tree_child(self, child_id: str) -> None:
        self[self._next_node_counter_key(NODE_TYPE_TREE_CHILD)] = dict(id=child_id)

    def iter_nodes(self) -> Iterable[tuple[str, Any]]:
        key: str
        for key, value in self.items():
            if "_" in key and key.rsplit("_", maxsplit=1)[1].isdigit():
                yield key, value

    def iter_nodes_with_child_placeholders(self) -> Iterable[tuple[str, Any]]:
        key: str
        for key, value in self.items():
            if value is ...:
                yield key, value
                continue
            if "_" in key and key.rsplit("_", maxsplit=1)[1].isdigit():
                yield key, value

    def add_exit_trace(self, trace: Trace, call_trace: str) -> None:
        self[self._next_node_counter_key(NODE_TYPE_EXIT_ERROR)] = trace
        self[self._next_node_counter_key("call_trace")] = call_trace

    def add_except_trace(self, trace: Trace, call_trace: str) -> None:
        self[self._next_node_counter_key(NODE_TYPE_EXCEPT_ERROR)] = trace
        self[self._next_node_counter_key("call_trace")] = call_trace

    def add_ref_src(self, ref: str):
        self[self._next_node_counter_key(NODE_TYPE_REF_SRC)] = ref

    def add_ref_dest(self, ref: str):
        self[self._next_node_counter_key(NODE_TYPE_REF_DEST)] = ref
