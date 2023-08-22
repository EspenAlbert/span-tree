from log_tree import get_logger
from log_tree.log_tree import LogTree, get_tree_state
from test_log_tree.conftest import tree_by_name

logger = get_logger(__name__)


def test_task():
    with LogTree(tree_id="t1") as action:
        assert action.is_running
    assert action.is_done


def test_nested_task():
    with LogTree(tree_id="t1") as action1:
        with logger(name="cool") as action2:
            logger.log_extra(cool=True)
        assert action2.is_done
        assert action1.is_running
    assert action1.is_done


def test_new_action():
    with logger("my_root") as action:
        assert action.is_running
    assert action.is_done


def test_new_action_forced_task(all_trees):
    with logger("parent"):
        with logger("forced_parent", force_new_tree=True):
            with logger("child_forced_parent"):
                logger.log_extra(parent="forced_parent")
                assert len(get_tree_state()) == 2
            assert len(get_tree_state()) == 2
        with logger("child_parent"):
            logger.log_extra(in_child=True, parent="parent")
            assert len(get_tree_state()) == 1
        assert len(get_tree_state()) == 1
    assert len(get_tree_state()) == 0
    assert len(all_trees) == 2


def test_deeply_nested_tree():
    with logger("root"):
        with logger("action1"):
            logger.log_extra(child1=True)
            with logger("action2"):
                logger.log_extra(grand_child1=True)
            with logger("action3"):
                logger.log_extra(grand_child2=True)
        with logger("action4"):
            logger.log_extra(child2=True)
            with logger("action5"):
                logger.log_extra(grand_child3=True)


def test_tree_ref(all_trees):
    with logger("root"):
        with logger("root2", force_new_tree=True):
            logger.log_extra(root2=True)
    root_tree = tree_by_name(all_trees, "root")
    root2_tree = tree_by_name(all_trees, "root2")
    assert list(root2_tree.root_action.iter_nodes()) == [
        ("extra_1", {"root2": True}),
    ]
    assert list(root_tree.root_action.iter_nodes()) == []


def test_ref_src(all_trees):
    with logger("root"):
        ref = logger.log_extra(ref_src=True)
    tree = tree_by_name(all_trees, "root")
    assert list(tree.root_action.refs_src) == [ref]


def test_ref_dest(all_trees):
    with logger("root"):
        logger.log_extra(ref_dest="some-ref")
    tree = tree_by_name(all_trees, "root")
    assert list(tree.root_action.refs_dest) == ["some-ref"]
