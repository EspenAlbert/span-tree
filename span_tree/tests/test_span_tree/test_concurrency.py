import asyncio
import time
from asyncio import create_task
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Thread

import pytest

from span_tree.api import get_logger, new_span
from span_tree.handler import skip_wrap
from span_tree.log_trace import get_trace_state

logger = get_logger(__name__)


@pytest.mark.asyncio()
@pytest.mark.parametrize("with_parent", [False, True])
async def test_async_spans_should_be_in_different_traces(with_parent):
    cm = new_span("parent") if with_parent else nullcontext()

    async def task_sleeper(name: str):
        with new_span(name):
            await asyncio.sleep(0.3)

    with cm:
        tasks = [create_task(task_sleeper(f"async-task{i}")) for i in range(3)]
        await asyncio.sleep(0.1)
    assert len(get_trace_state()) == 3
    for t in tasks:
        await t
    assert len(get_trace_state()) == 0


def log_in_thread(i: int, message: str):
    logger.log_extra(f"thread-{i}-starting", **{message: message})
    time.sleep(0.1)
    logger.info(f"thread-{i} finishing")


@pytest.mark.parametrize("with_parent", [False, True])
def test_spawning_multiple_threads_should_create_one_trace_per_thread(with_parent):
    futures = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        context_manager = new_span("parent") if with_parent else nullcontext()

        with context_manager:
            for thread_nr in range(5):
                futures.append(
                    pool.submit(log_in_thread, thread_nr, f"message-{thread_nr}")
                )
        time.sleep(0.03)
        task_state = get_trace_state()
        logger.info(task_state)
        assert len(task_state) == 5
        time.sleep(0.11)
    assert len(get_trace_state()) == 0


@pytest.mark.parametrize("with_parent", [False, True])
def test_spawning_threads_from_threading_should_create_traces(all_traces, with_parent):
    cm = new_span("root") if with_parent else nullcontext()
    with cm:
        thread1 = Thread(target=log_in_thread, name="thread1", args=(1, "t1"))
        thread2 = Thread(target=log_in_thread, name="thread1", args=(2, "t2"))
        thread1.start()
        thread2.start()
    thread1.join()
    thread2.join()
    if with_parent:
        assert len(all_traces) == 3
    else:
        assert len(all_traces) == 2


def test_skip_wrap_should_not_create_trace(all_traces):
    with ThreadPoolExecutor() as pool:

        def no_trace():
            logger.info("normal logging without a trace")

        skip_wrap(no_trace)
        pool.submit(no_trace).result(timeout=1)
    assert len(all_traces) == 0


def test_logging_from_main_thread_without_parent():
    logger.log_extra(main_thread=True)
    task_state = get_trace_state()
    assert len(task_state) == 0
