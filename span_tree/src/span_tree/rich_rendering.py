from contextlib import contextmanager
from typing import Any, Callable

from rich.console import Console
from rich.traceback import Trace, Traceback
from rich.tree import Tree
from typing_extensions import TypeAlias
from zero_3rdparty.datetime_utils import dump_date_as_rfc3339

from span_tree.log_action import (
    NODE_TYPE_EXIT_ERROR,
    as_tree_child_id,
    as_tree_parent_id,
)
from span_tree.log_tree import LogTree

MAX_FRAMES_ERROR = 5

ReadTree: TypeAlias = Callable[[str], LogTree | None]


class HasParentTreeError(Exception):
    def __init__(self, parent_tree_id: str):
        self.parent_tree_id = parent_tree_id


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


def create_rich_tree(
    log_tree: LogTree,
    reader: ReadTree,
    raise_on_has_parent: bool = False,
) -> tuple[Tree, set[str]]:
    root_tree_id = log_tree.tree_id
    ids = {root_tree_id}

    def add_subtree(node: Tree, key: str, value: Any) -> Tree:
        if raise_on_has_parent and (parent_id := as_tree_parent_id(key, value)):
            if parent_id != root_tree_id:
                raise HasParentTreeError(parent_id)
        if child_id := as_tree_child_id(key, value):
            if child_tree := reader(child_id):
                ids.add(child_id)
                child_root = convert_tree(child_tree, node_adder=add_subtree)
                return node.add(child_root)
        return _default_node_adder(node, key, value)

    tree = convert_tree(log_tree, node_adder=add_subtree)
    return tree, ids


def print_tree_call(render_call_locations: bool = True) -> Callable[[LogTree], Tree]:
    def print_tree(tree: LogTree):
        rich_tree = convert_tree(tree, render_call_locations=render_call_locations)
        _console.print(rich_tree)
        return rich_tree

    return print_tree


_ACTION_NODE = "__ACTION_NODE__"


def _tree_and_node_adder(tree: LogTree) -> tuple[Tree, Callable[[str, str], Tree]]:
    root = Tree(f"[b]{tree.tree_id}")

    def add_action_node(index: str, header: str) -> Tree:
        if index == "0":
            action_node = root.add(header)
            setattr(action_node, _ACTION_NODE, True)
            return action_node
        *indexes, _, __ = index.split("/")
        node = root.children[0]
        for level_index in indexes:
            action_children = [
                child for child in node.children if hasattr(child, _ACTION_NODE)
            ]
            node = action_children[int(level_index)]
        index = next(i for i, child in enumerate(node.children) if child is ...)
        action_node = Tree(header)
        setattr(action_node, _ACTION_NODE, True)
        node.children[index] = action_node
        return action_node

    return root, add_action_node


def _default_node_adder(node: Tree, key: str, value: Any) -> Tree:
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
    tree: LogTree,
    render_call_locations: bool = True,
    node_adder: Callable[[Tree, str, Any], Tree] | None = None,
) -> Tree:
    root, add_action_node = _tree_and_node_adder(tree)
    node_adder = node_adder or _default_node_adder

    for tree_index, a in tree.actions.items():
        color = "green" if a.is_ok else "red"
        ts = dump_date_as_rfc3339(a.timestamp, strip_microseconds=True).replace(
            "+00:00", "Z"
        )
        action_header = f"[b {color}]{a.name} => {a.status}[/] [cyan]{ts}[/] ⧖ [blue]{a.duration_ms*1000:.3f}ms[/]"

        node = add_action_node(tree_index, action_header)
        if render_call_locations:
            node.add(a.call_location)
        for key, value in a.iter_nodes_with_child_placeholders():
            if value is ...:
                node.children.append(...)
                # will be replaced by next action
                continue
            node_adder(node, key, value)
    return root
