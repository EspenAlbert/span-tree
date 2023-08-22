from log_tree.api import get_logger
from test_log_tree.conftest import tree_by_name

logger = get_logger(__name__)


def test_new_action(all_trees):
    with logger.new_action("api-root"):
        with logger.new_action("api-child"):
            logger.log_extra(in_child=True)
            logger.info("in-child-info-normal")
        logger.info("in-root")
        logger.log_extra(in_parent=True)
    tree = tree_by_name(all_trees, "api-root")
    assert len(tree.actions) == 2
    assert [key for key, _ in tree.root_action.iter_nodes()] == ['INFO_1', 'extra_2']
    last_action = list(tree.actions.values())[-1]
    assert [key for key, _ in last_action.iter_nodes()] == ['extra_1', 'INFO_2']


def test_decorator(all_trees):
    @logger.action
    def my_func(result: str):
        return result
    assert my_func("ok") == "ok"
    assert all_trees
