from span_tree import get_logger
from span_tree.log_trace import LogTrace, get_trace_state
from test_span_tree.conftest import trace_by_name

logger = get_logger(__name__)


def test_task():
    with LogTrace(trace_id="t1") as span:
        assert span.is_running
    assert span.is_done


def test_nested_task():
    with LogTrace(trace_id="t1") as span1:
        with logger(name="cool") as span2:
            logger.log_extra(cool=True)
        assert span2.is_done
        assert span1.is_running
    assert span1.is_done


def test_new_span():
    with logger("my_root") as span:
        assert span.is_running
    assert span.is_done


def test_new_span_forced_task(all_traces):
    with logger("parent"):
        with logger("forced_parent", force_new_trace=True):
            with logger("child_forced_parent"):
                logger.log_extra(parent="forced_parent")
                assert len(get_trace_state()) == 2
            assert len(get_trace_state()) == 2
        with logger("child_parent"):
            logger.log_extra(in_child=True, parent="parent")
            assert len(get_trace_state()) == 1
        assert len(get_trace_state()) == 1
    assert len(get_trace_state()) == 0
    assert len(all_traces) == 2


def test_deeply_nested_trace():
    with logger("root"):
        with logger("span1"):
            logger.log_extra(child1=True)
            with logger("span2"):
                logger.log_extra(grand_child1=True)
            with logger("span3"):
                logger.log_extra(grand_child2=True)
        with logger("span4"):
            logger.log_extra(child2=True)
            with logger("span5"):
                logger.log_extra(grand_child3=True)


def test_trace_ref(all_traces):
    with logger("root"):
        with logger("root2", force_new_trace=True):
            logger.log_extra(root2=True)
    root_trace = trace_by_name(all_traces, "root")
    root2_trace = trace_by_name(all_traces, "root2")
    assert list(root2_trace.root_span.iter_nodes()) == [
        ("extra_1", {"root2": True}),
    ]
    assert list(root_trace.root_span.iter_nodes()) == []


def test_ref_src(all_traces):
    with logger("root"):
        ref = logger.log_extra(ref_src=True)
    trace = trace_by_name(all_traces, "root")
    assert list(trace.root_span.refs_src) == [ref]


def test_ref_dest(all_traces):
    with logger("root"):
        logger.log_extra(ref_dest="some-ref")
    trace = trace_by_name(all_traces, "root")
    assert list(trace.root_span.refs_dest) == ["some-ref"]
