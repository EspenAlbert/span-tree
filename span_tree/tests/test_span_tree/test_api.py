from span_tree.api import get_logger
from test_span_tree.conftest import trace_by_name

logger = get_logger(__name__)


def test_new_span(all_traces):
    with logger.new_span("api-root"):
        with logger.new_span("api-child"):
            logger.log_extra(in_child=True)
            logger.info("in-child-info-normal")
        logger.info("in-root")
        logger.log_extra(in_parent=True)
    trace = trace_by_name(all_traces, "api-root")
    assert len(trace.spans) == 2
    assert [key for key, _ in trace.root_span.events] == ["INFO", "extra"]
    last_span = list(trace.spans.values())[-1]
    assert [key for key, _ in last_span.events] == ["extra", "INFO"]


def test_decorator(all_traces):
    @logger.span
    def my_func(result: str):
        return result

    assert my_func("ok") == "ok"
    assert all_traces
