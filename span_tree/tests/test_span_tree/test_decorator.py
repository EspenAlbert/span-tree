from __future__ import annotations

from zero_3rdparty.object_name import as_name

from span_tree import get_logger
from test_span_tree.conftest import trace_by_name

logger = get_logger(__name__)


@logger.span
def my_func(pos: str, /, keyword: int):
    return f"{pos}-{keyword}"


def test_span_decorator_no_args(all_traces):
    result = my_func("hey", keyword=22)
    assert result == "hey-22"
    func_name = as_name(my_func)
    assert trace_by_name(all_traces, func_name)


@logger.span("my_decorator")
def my_func2(pos: str, /, keyword: int):
    return f"{pos}-{keyword}"


def test_span_decorator_with_args(all_traces):
    result = my_func2("hey", keyword=22)
    assert result == "hey-22"
    assert trace_by_name(all_traces, "my_decorator")


@logger.span
@logger.span
def my_func3(pos: str, /, keyword: int):
    return f"{pos}-{keyword}"


def test_span_decorator_multiple_times(all_traces):
    result = my_func3("hey", keyword=22)
    assert result == "hey-22"
    trace = all_traces[0]
    assert len(trace.spans) == 1
