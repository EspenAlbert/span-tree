import time
from typing import TypeVar, Type, Iterable, Any, Callable
from unittest.mock import MagicMock

import pytest
from rich.console import Console
from rich.tree import Tree

from log_tree import log_tree
from log_tree.handler import configure
from log_tree.log_action import LogAction
from log_tree.log_tree import clear_tree_state, LogTree, temp_publisher
from log_tree.log_tree_publisher import tree_publisher

FLUSH_INTERVAL_SECONDS = 0.1


@pytest.fixture(scope="session", autouse=True)
def configure_logger():
    configure(render_trees=True, disable_prev_logger=True)


@pytest.fixture(autouse=True)
def clear_state():
    clear_tree_state()


@pytest.fixture()
def printed_trees() -> list[Tree]:
    trees = []
    yield trees
    new_console = Console(
        width=240,
        log_path=False,
        no_color=False,
        force_terminal=True,
    )
    time.sleep(0.001) # adding a little sleep to make output be nicer
    for t in trees:
        new_console.print(t)
    new_console.file.flush()


@pytest.fixture(autouse=True)
def tree_rich_printer(printed_trees) -> Callable[[LogTree], None]:  # type: ignore
    console = MagicMock(print=printed_trees.append)
    publisher, stop_publisher = tree_publisher(
        console=console, flush_interval_seconds=FLUSH_INTERVAL_SECONDS
    )
    yield publisher
    stop_publisher()


@pytest.fixture(autouse=True)
def all_trees() -> list[LogTree]:
    return []


@pytest.fixture(autouse=True)
def publish_trees(tree_rich_printer, all_trees):
    def new_publisher(tree: log_tree.LogTree) -> Any:
        all_trees.append(tree)
        tree_rich_printer(tree)

    with temp_publisher(new_publisher):
        yield


def wait_for_printed_trees(trees: list[Tree]) -> None:
    for _ in range(10):
        if trees:
            return None
        time.sleep(FLUSH_INTERVAL_SECONDS / 20)
    raise ValueError("trees never set")


def tree_by_name(trees: list[LogTree], name: str) -> LogTree:
    for tree in trees:
        if tree.root_action.name == name:
            return tree
    raise ValueError(f"tree not found: {name}")


T = TypeVar("T")


def action_values(action: LogAction, value_type: Type[T]) -> Iterable[T]:
    for _, value in action.iter_nodes():
        if isinstance(value, value_type):
            yield value


def action_key_value(action: LogAction, value_type: Type[T]) -> tuple[str, T]:
    for key, value in action.iter_nodes():
        if isinstance(value, value_type):
            return key, value
    raise StopIteration
