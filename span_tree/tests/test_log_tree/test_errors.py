import pytest
from rich.pretty import Node
from rich.traceback import Trace

from log_tree import get_logger
from test_log_tree.conftest import tree_by_name, action_key_value

logger = get_logger(__name__)

class _Error(Exception):
    pass


def raise_me():
    raise _Error("some-error-message")


def test_uncaught_error(all_trees):
    with pytest.raises(_Error):
        with logger("error_in_exit"):
            raise_me()
    tree = tree_by_name(all_trees, "error_in_exit")
    key, trace = action_key_value(tree.root_action, Trace)
    assert trace.stacks[0].exc_type == "_Error"
    assert trace.stacks[0].exc_value == "some-error-message"


def test_caught_error(all_trees):
    with logger("catcher"):
        try:
            with logger("error_raiser"):
                raise_me()
        except _Error as e:
            logger.exception(e)
    tree = tree_by_name(all_trees, "catcher")
    key, trace = action_key_value(tree.root_action, Trace)
    assert key == "except_error_1"
    frame_names = [frame.name for frame in trace.stacks[0].frames]
    raiser_name = raise_me.__name__
    catcher = test_caught_error.__name__
    assert frame_names == [raiser_name, catcher]


def test_error_with_locals(all_trees):
    def error_raiser(name: str):
        raise _Error()

    with pytest.raises(_Error):
        with logger("with_locals"):
            error_raiser("some_local_name")
    tree = tree_by_name(all_trees, "with_locals")
    key, trace = action_key_value(tree.root_action, Trace)
    assert trace.stacks[0].frames[-1].locals == {
        "name": Node(
            key_repr="",
            value_repr="'some_local_name'",
            open_brace="",
            close_brace="",
            empty="",
            last=True,
            is_tuple=False,
            is_namedtuple=False,
            children=None,
            key_separator=": ",
            separator=", ",
        )
    }


def test_nested_error_all_the_way(all_trees):
    with pytest.raises(_Error):
        with logger("root"):
            with logger("child"):
                raise_me()
    tree = tree_by_name(all_trees, "root")
    key, trace = action_key_value(tree.root_action, Trace)
    assert key == "exit_error_1"
