import concurrent.futures
import logging
from concurrent.futures import Future
from threading import Thread
from time import monotonic
from typing import Callable, Iterable

from rich import get_console
from rich.console import Console
from rich.tree import Tree
from zero_3rdparty.closable_queue import ClosableQueue

from span_tree.handler import skip_wrap
from span_tree.log_trace import LogTrace
from span_tree.rich_rendering import HasParentTraceError, create_rich_trace

logger = logging.getLogger(__name__)
_flush = object()


def trace_publisher(  # noqa: C901
    console: Console | None = None, flush_interval_seconds: float = 1
) -> tuple[Callable[[LogTrace], None], Callable[[], None]]:
    """
    Returns: publish, stop_publishing
    ## Print to console when
    1. All children are printed
    2. Timeout waiting for children
    """
    queue: ClosableQueue[LogTrace | object] = ClosableQueue()
    console = console or get_console()
    traces: dict[str, LogTrace] = {}
    traces_ts: dict[str, float] = {}

    def console_print_trace(trace_ids: Iterable[str], trace: Tree):
        """how do we know which children trace_ids where used?"""
        console.print(trace)
        for id in trace_ids:
            traces.pop(id, None)
            traces_ts.pop(id, None)

    def force_print(trace_id: str):
        logger.warning(f"force printing trace: {trace_id}")
        trace = traces[trace_id]
        rich_trace, trace_ids = create_rich_trace(trace, traces.get)
        console_print_trace(trace_ids, rich_trace)

    def flush_pending(threshold: float):
        for ts, trace_id in sorted(
            (ts, trace_id) for trace_id, ts in traces_ts.items()
        ):
            if ts > threshold:
                break
            force_print(trace_id)

    def attempt_print(trace: LogTrace):
        try:
            rich_trace, trace_ids = create_rich_trace(
                trace, traces.__getitem__, raise_on_has_parent=True
            )
            console_print_trace(trace_ids, rich_trace)
        except (KeyError, HasParentTraceError) as e:
            trace_id = trace.trace_id
            traces[trace_id] = trace
            traces_ts[trace_id] = monotonic()
            if isinstance(e, HasParentTraceError):
                if parent := traces.get(e.parent_trace_id):
                    attempt_print(parent)
            return None

    def consume_traces() -> None:
        logger.info("trace_consumer start")
        for trace in queue:  # type: ignore
            if trace is _flush:
                flush_pending(monotonic() - flush_interval_seconds)
                continue
            attempt_print(trace)
        flush_pending(monotonic())
        logger.warning("trace_consumer done")

    flush_done: Future[bool] = Future()
    flush_interval_seconds = flush_interval_seconds

    def flush_on_interval():
        logger.info("flusher start")
        while True:
            try:
                flush_done.result(timeout=flush_interval_seconds)
            except concurrent.futures.TimeoutError:
                queue.put_nowait(_flush)
            else:
                break
        queue.close()
        logger.info("flusher done")

    def stop_publishing() -> None:
        if not flush_done.done():
            flush_done.set_result(True)

    skip_wrap(flush_on_interval)
    skip_wrap(consume_traces)
    t_consumer = Thread(target=consume_traces)
    t_consumer.start()
    t_flusher = Thread(target=flush_on_interval)
    t_flusher.start()

    return queue.put_nowait, stop_publishing
