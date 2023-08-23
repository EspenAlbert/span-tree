import pytest

from span_tree import get_logger
from span_tree.log_action import LogAction

logger = get_logger(__name__)


def test_new_action():
    with logger("tree_printer"):
        logger.log_extra(beautiful=True)


@pytest.mark.freeze_time("2020-01-01")
def test_log_levels_logged(all_trees):
    with logger("log_levels"):
        logger.info("info-msg")
        logger.warning("warning-msg")
        logger.error("error-msg")
    assert len(all_trees) == 1
    tree = all_trees[0]
    action: LogAction = tree.actions["0"]
    assert list(action.iter_nodes()) == [
        (
            "INFO_1",
            "2020-01-01T00:00:00.000 INFO    MainThread test_span_tree.test_handler 17 "
            "info-msg",
        ),
        (
            "WARNING_2",
            "2020-01-01T00:00:00.000 WARNING MainThread test_span_tree.test_handler 18 "
            "warning-msg",
        ),
        (
            "ERROR_3",
            "2020-01-01T00:00:00.000 ERROR   MainThread test_span_tree.test_handler 19 "
            "error-msg",
        ),
    ]
