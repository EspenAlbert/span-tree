import asyncio
import time
from asyncio import create_task
from concurrent.futures import Future, ThreadPoolExecutor

import pytest

from span_tree.api import logger_log_extra, new_span
from test_span_tree.conftest import wait_for_printed_traces

logger, log_extra = logger_log_extra(__name__)
TIMEOUT = 1
FLUSH_INTERVAL_SECONDS = 0.1


def test_publishing_trace_without_children_should_be_published_immediately(
    printed_traces,
):
    with new_span("root"):
        pass
    wait_for_printed_traces(printed_traces)
    assert printed_traces


def test_publishing_nested_trace_child_finish_first(printed_traces):
    with new_span("root"):
        with new_span("child"):
            log_extra(in_child=True)
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 1


def test_publishing_nested_trace_child_finish_last(printed_traces):
    future = Future()

    def child_thread():
        logger.info("child start")
        future.result(timeout=TIMEOUT)
        logger.info("child end")

    with ThreadPoolExecutor() as pool:
        with new_span("root"):
            child_run = pool.submit(child_thread)
            logger.info("parent finishing")
        future.set_result(True)
        child_run.result(timeout=TIMEOUT)
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 1


def test_publish_deeply_nested_trace(printed_traces):
    with new_span("root"):
        logger.info("root-start")
        with new_span("root2"):
            logger.info("root2-start")
            with new_span("leaf"):
                logger.info("in leaf")
            logger.info("root2-end")
        logger.info("root-end")
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 1


def test_publish_trace_with_multiple_children(printed_traces):
    with new_span("root"):
        logger.info("root-start")
        with new_span("leaf1"):
            logger.info("in leaf1")
        logger.info("root-middle")
        with new_span("leaf2"):
            logger.info("in leaf2")
        logger.info("root-end")
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 1


def test_publish_deep_trace_with_multiple_grandchildren(printed_traces):
    with new_span("root"):
        logger.info("root-start")
        with new_span("middle"):
            with new_span("leaf1"):
                logger.info("in leaf1")
            logger.info("middle of middle")
            with new_span("leaf2"):
                logger.info("in leaf2")
        logger.info("root-end")
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 1


def test_publishing_for_two_different_traces(printed_traces):
    with new_span("root"):
        with new_span("child", force_new_trace=True):
            log_extra(in_different_task=True)
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 2


def test_slow_parent_should_flush_child_traces(printed_traces):
    def child_thread():
        logger.info("child running")

    with ThreadPoolExecutor() as pool:
        with new_span("root"):
            child_run = pool.submit(child_thread)
            child_run.result(timeout=TIMEOUT)
            time.sleep(FLUSH_INTERVAL_SECONDS * 2)
            wait_for_printed_traces(printed_traces)
            assert len(printed_traces) == 1
            logger.info("parent finishing")
    time.sleep(FLUSH_INTERVAL_SECONDS * 2.5)
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 2


@pytest.mark.asyncio()
async def test_async_spans_should_be_in_printed_in_same_trace(printed_traces):
    async def task_sleeper(name: str):
        with new_span(name):
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS * 0.5)

    with new_span("async-root"):
        tasks = [create_task(task_sleeper(f"async-task{i}")) for i in range(3)]
        for t in tasks:
            await t
        await asyncio.sleep(FLUSH_INTERVAL_SECONDS * 0.8)
    wait_for_printed_traces(printed_traces)
    assert len(printed_traces) == 1
