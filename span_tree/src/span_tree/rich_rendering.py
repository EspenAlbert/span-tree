from contextlib import contextmanager
from typing import Any, Callable

from rich.console import Console
from rich.traceback import Trace, Traceback
from rich.tree import Tree
from typing_extensions import TypeAlias
from zero_3rdparty.datetime_utils import dump_date_as_rfc3339

from span_tree.log_span import (
    NODE_TYPE_EXIT_ERROR,
    as_trace_child_id,
    as_trace_parent_id,
)
from span_tree.log_trace import LogTrace

MAX_FRAMES_ERROR = 5

ReadTrace: TypeAlias = Callable[[str], LogTrace | None]


class HasParentTraceError(Exception):
    def __init__(self, parent_trace_id: str):
        self.parent_trace_id = parent_trace_id


_console: Console = Console(
    log_time=True,
    width=240,
    log_path=False,
    no_color=False,
    force_terminal=True,
)


def set_console(console: Console) -> Console:
    global _console
    old = _console
    _console = console
    return old


@contextmanager
def temp_console(console: Console) -> Console:
    old = set_console(console)
    try:
        yield old
    finally:
        set_console(old)


def create_rich_trace(
    log_trace: LogTrace,
    reader: ReadTrace,
    raise_on_has_parent: bool = False,
) -> tuple[Tree, set[str]]:
    root_trace_id = log_trace.trace_id
    ids = {root_trace_id}

    def add_subtrace(node: Tree, key: str, value: Any) -> Trace:
        if raise_on_has_parent and (parent_id := as_trace_parent_id(key, value)):
            if parent_id != root_trace_id:
                raise HasParentTraceError(parent_id)
        if child_id := as_trace_child_id(key, value):
            if child_trace := reader(child_id):
                ids.add(child_id)
                child_root = convert_tree(child_trace, node_adder=add_subtrace)
                return node.add(child_root)
        return _default_node_adder(node, key, value)

    trace = convert_tree(log_trace, node_adder=add_subtrace)
    return trace, ids


def print_trace_call(render_call_locations: bool = True) -> Callable[[LogTrace], Trace]:
    def print_trace(trace: LogTrace):
        rich_trace = convert_tree(trace, render_call_locations=render_call_locations)
        _console.print(rich_trace)
        return rich_trace

    return print_trace


_SPAN_NODE = "__SPAN_NODE__"


def _tree_and_node_adder(trace: LogTrace) -> tuple[Tree, Callable[[str, str], Tree]]:
    root = Tree(f"[b]{trace.trace_id}")

    def add_span_node(index: str, header: str) -> Tree:
        if index == "0":
            span_node = root.add(header)
            setattr(span_node, _SPAN_NODE, True)
            return span_node
        *indexes, _, __ = index.split("/")
        node = root.children[0]
        for level_index in indexes:
            span_children = [
                child for child in node.children if hasattr(child, _SPAN_NODE)
            ]
            node = span_children[int(level_index)]
        index = next(i for i, child in enumerate(node.children) if child is ...)
        span_node = Tree(header)
        setattr(span_node, _SPAN_NODE, True)
        node.children[index] = span_node
        return span_node

    return root, add_span_node


def _default_node_adder(node: Trace, key: str, value: Any) -> Trace:
    if isinstance(value, Trace):
        is_error = key.startswith(NODE_TYPE_EXIT_ERROR)
        node_tb = node.add(key, style="red" if is_error else "yellow")
        traceback = Traceback(value, max_frames=MAX_FRAMES_ERROR, show_locals=True)
        node_tb.add(traceback)
        return node_tb
    else:
        value_str = value if isinstance(value, str) else repr(value)
        return node.add(f"[blue]{key}[/]={value_str}")


def convert_tree(
    trace: LogTrace,
    render_call_locations: bool = True,
    node_adder: Callable[[Tree, str, Any], Tree] | None = None,
) -> Tree:
    root, add_span_node = _tree_and_node_adder(trace)
    node_adder = node_adder or _default_node_adder

    for trace_index, span in trace.spans.items():
        color = "green" if span.is_ok else "red"
        ts = dump_date_as_rfc3339(span.timestamp, strip_microseconds=True).replace(
            "+00:00", "Z"
        )
        span_header = f"[b {color}]{span.name} => {span.status}[/] [cyan]{ts}[/] ⧖ [blue]{span.duration_ms*1000:.3f}ms[/]"

        node = add_span_node(trace_index, span_header)
        if render_call_locations:
            node.add(span.call_location)
        for key, value in span.events_with_child_placeholders:
            if value is ...:
                node.children.append(...)
                # will be replaced by next span
                continue
            node_adder(node, key, value)
    return root
