import time
from typing import Any, Callable, Iterable, Type, TypeVar
from unittest.mock import MagicMock

import pytest
from rich.console import Console
from rich.tree import Tree

from span_tree import log_trace
from span_tree.handler import configure
from span_tree.log_span import LogSpan
from span_tree.log_trace import LogTrace, clear_trace_state, temp_publisher
from span_tree.log_trace_publisher import trace_publisher

FLUSH_INTERVAL_SECONDS = 0.1


@pytest.fixture(scope="session", autouse=True)
def configure_logger():
    configure(render_traces=True, disable_prev_logger=True)


@pytest.fixture(autouse=True)
def clear_state():
    clear_trace_state()


@pytest.fixture()
def printed_traces() -> list[Tree]:
    traces = []
    yield traces
    new_console = Console(
        width=240,
        log_path=False,
        no_color=False,
        force_terminal=True,
    )
    time.sleep(0.001)  # adding a little sleep to make output be nicer
    for t in traces:
        new_console.print(t)
    new_console.file.flush()


@pytest.fixture(autouse=True)
def trace_rich_printer(printed_traces) -> Callable[[LogTrace], None]:  # type: ignore
    console = MagicMock(print=printed_traces.append)
    publisher, stop_publisher = trace_publisher(
        console=console, flush_interval_seconds=FLUSH_INTERVAL_SECONDS
    )
    yield publisher
    stop_publisher()


@pytest.fixture(autouse=True)
def all_traces() -> list[LogTrace]:
    return []


@pytest.fixture(autouse=True)
def publish_traces(trace_rich_printer, all_traces):
    def new_publisher(trace: log_trace.LogTrace) -> Any:
        all_traces.append(trace)
        trace_rich_printer(trace)

    with temp_publisher(new_publisher):
        yield


def wait_for_printed_traces(traces: list[Tree]) -> None:
    for _ in range(10):
        if traces:
            return None
        time.sleep(FLUSH_INTERVAL_SECONDS / 20)
    raise ValueError("traces never set")


def trace_by_name(traces: list[LogTrace], name: str) -> LogTrace:
    for trace in traces:
        if trace.root_span.name == name:
            return trace
    raise ValueError(f"trace not found: {name}")


T = TypeVar("T")


def span_values(span: LogSpan, value_type: Type[T]) -> Iterable[T]:
    for _, value in span.events:
        if isinstance(value, value_type):
            yield value


def span_key_value(span: LogSpan, value_type: Type[T]) -> tuple[str, T]:
    for key, value in span.events:
        if isinstance(value, value_type):
            return key, value
    raise StopIteration
