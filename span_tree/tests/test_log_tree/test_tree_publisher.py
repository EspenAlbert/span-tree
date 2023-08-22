import asyncio
import time
from asyncio import create_task
from concurrent.futures import Future, ThreadPoolExecutor

import pytest

from log_tree.api import new_action, logger_log_extra
from test_log_tree.conftest import wait_for_printed_trees

logger, log_extra = logger_log_extra(__name__)
TIMEOUT = 1
FLUSH_INTERVAL_SECONDS = 0.1


def test_publishing_tree_without_children_should_be_published_immediately(
    printed_trees,
):
    with new_action("root"):
        pass
    wait_for_printed_trees(printed_trees)
    assert printed_trees


def test_publishing_nested_tree_child_finish_first(printed_trees):
    with new_action("root"):
        with new_action("child"):
            log_extra(in_child=True)
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 1


def test_publishing_nested_tree_child_finish_last(printed_trees):
    future = Future()

    def child_thread():
        logger.info("child start")
        future.result(timeout=TIMEOUT)
        logger.info("child end")

    with ThreadPoolExecutor() as pool:
        with new_action("root"):
            child_run = pool.submit(child_thread)
            logger.info("parent finishing")
        future.set_result(True)
        child_run.result(timeout=TIMEOUT)
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 1


def test_publish_deeply_nested_tree(printed_trees):
    with new_action("root"):
        logger.info("root-start")
        with new_action("root2"):
            logger.info("root2-start")
            with new_action("leaf"):
                logger.info("in leaf")
            logger.info("root2-end")
        logger.info("root-end")
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 1


def test_publish_tree_with_multiple_children(printed_trees):
    with new_action("root"):
        logger.info("root-start")
        with new_action("leaf1"):
            logger.info("in leaf1")
        logger.info("root-middle")
        with new_action("leaf2"):
            logger.info("in leaf2")
        logger.info("root-end")
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 1


def test_publish_deep_tree_with_multiple_grandchildren(printed_trees):
    with new_action("root"):
        logger.info("root-start")
        with new_action("middle"):
            with new_action("leaf1"):
                logger.info("in leaf1")
            logger.info("middle of middle")
            with new_action("leaf2"):
                logger.info("in leaf2")
        logger.info("root-end")
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 1


def test_publishing_for_two_different_trees(printed_trees):
    with new_action("root"):
        with new_action("child", force_new_tree=True):
            log_extra(in_different_task=True)
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 2


def test_slow_parent_should_flush_child_trees(printed_trees):
    def child_thread():
        logger.info("child running")

    with ThreadPoolExecutor() as pool:
        with new_action("root"):
            child_run = pool.submit(child_thread)
            child_run.result(timeout=TIMEOUT)
            time.sleep(FLUSH_INTERVAL_SECONDS * 2)
            wait_for_printed_trees(printed_trees)
            assert len(printed_trees) == 1
            logger.info("parent finishing")
    time.sleep(FLUSH_INTERVAL_SECONDS * 2.5)
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 2


@pytest.mark.asyncio()
async def test_async_actions_should_be_in_printed_in_same_tree(printed_trees):
    async def task_sleeper(name: str):
        with new_action(name):
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS * 0.5)

    with new_action("async-root"):
        tasks = [create_task(task_sleeper(f"async-task{i}")) for i in range(3)]
        for t in tasks:
            await t
        await asyncio.sleep(FLUSH_INTERVAL_SECONDS * 0.8)
    wait_for_printed_trees(printed_trees)
    assert len(printed_trees) == 1
