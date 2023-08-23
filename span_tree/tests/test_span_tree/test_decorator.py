from __future__ import annotations

from zero_3rdparty.object_name import as_name

from span_tree import get_logger
from test_span_tree.conftest import tree_by_name

logger = get_logger(__name__)


@logger.action
def my_func(pos: str, /, keyword: int):
    return f"{pos}-{keyword}"


def test_action_decorator_no_args(all_trees):
    result = my_func("hey", keyword=22)
    assert result == "hey-22"
    func_name = as_name(my_func)
    assert tree_by_name(all_trees, func_name)


@logger.action("my_decorator")
def my_func2(pos: str, /, keyword: int):
    return f"{pos}-{keyword}"


def test_action_decorator_with_args(all_trees):
    result = my_func2("hey", keyword=22)
    assert result == "hey-22"
    assert tree_by_name(all_trees, "my_decorator")


@logger.action
@logger.action
def my_func3(pos: str, /, keyword: int):
    return f"{pos}-{keyword}"


def test_action_decorator_multiple_times(all_trees):
    result = my_func3("hey", keyword=22)
    assert result == "hey-22"
    tree = all_trees[0]
    assert len(tree.actions) == 1
