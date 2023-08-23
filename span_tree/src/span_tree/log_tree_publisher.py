import concurrent.futures
import logging
from concurrent.futures import Future
from threading import Thread
from time import monotonic
from typing import Callable, Iterable

from rich import get_console
from rich.console import Console
from rich.tree import Tree

from span_tree.handler import skip_wrap
from span_tree.log_tree import LogTree
from span_tree.rich_rendering import HasParentTreeError, create_rich_tree
from zero_3rdparty.closable_queue import ClosableQueue

logger = logging.getLogger(__name__)
_flush = object()


def tree_publisher(
    console: Console | None = None, flush_interval_seconds: float = 1
) -> tuple[Callable[[LogTree], None], Callable[[], None]]:
    """
    Returns: publish, stop_publishing
    ## Print to console when
    1. All children are printed
    2. Timeout waiting for children
    """
    queue: ClosableQueue[LogTree | object] = ClosableQueue()
    console = console or get_console()
    trees: dict[str, LogTree] = {}
    trees_ts: dict[str, float] = {}

    def console_print_tree(tree_ids: Iterable[str], tree: Tree):
        """how do we know which children tree_ids where used?"""
        console.print(tree)
        for id in tree_ids:
            trees.pop(id, None)
            trees_ts.pop(id, None)

    def force_print(tree_id: str):
        logger.warning(f"force printing tree: {tree_id}")
        tree = trees[tree_id]
        rich_tree, tree_ids = create_rich_tree(tree, trees.get)
        console_print_tree(tree_ids, rich_tree)

    def flush_pending(threshold: float):
        for ts, tree_id in sorted((ts, tree_id) for tree_id, ts in trees_ts.items()):
            if ts > threshold:
                break
            force_print(tree_id)

    def attempt_print(tree: LogTree):
        try:
            rich_tree, tree_ids = create_rich_tree(
                tree, trees.__getitem__, raise_on_has_parent=True
            )
            console_print_tree(tree_ids, rich_tree)
        except (KeyError, HasParentTreeError) as e:
            tree_id = tree.tree_id
            trees[tree_id] = tree
            trees_ts[tree_id] = monotonic()
            if isinstance(e, HasParentTreeError):
                if parent := trees.get(e.parent_tree_id):
                    attempt_print(parent)
            return None

    def consume_trees() -> None:
        logger.info("tree_consumer start")
        for tree in queue:  # type: ignore
            if tree is _flush:
                flush_pending(monotonic() - flush_interval_seconds)
                continue
            attempt_print(tree)
        flush_pending(monotonic())
        logger.warning("tree_consumer done")

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
    skip_wrap(consume_trees)
    t_consumer = Thread(target=consume_trees)
    t_consumer.start()
    t_flusher = Thread(target=flush_on_interval)
    t_flusher.start()

    return queue.put_nowait, stop_publishing
