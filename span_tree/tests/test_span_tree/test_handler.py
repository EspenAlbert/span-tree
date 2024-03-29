import pytest

from span_tree import get_logger
from span_tree.log_span import LogSpan

logger = get_logger(__name__)


def test_new_span():
    with logger("trace_printer"):
        logger.log_extra(beautiful=True)


@pytest.mark.freeze_time("2020-01-01")
def test_log_levels_logged(all_traces):
    with logger("log_levels"):
        logger.info("info-msg")
        logger.warning("warning-msg")
        logger.error("error-msg")
    assert len(all_traces) == 1
    trace = all_traces[0]
    span: LogSpan = trace.spans["0"]
    assert span.events == [
        (
            "INFO",
            "2020-01-01T00:00:00.000 INFO    MainThread test_span_tree.test_handler 17 "
            "info-msg",
        ),
        (
            "WARNING",
            "2020-01-01T00:00:00.000 WARNING MainThread test_span_tree.test_handler 18 "
            "warning-msg",
        ),
        (
            "ERROR",
            "2020-01-01T00:00:00.000 ERROR   MainThread test_span_tree.test_handler 19 "
            "error-msg",
        ),
    ]
