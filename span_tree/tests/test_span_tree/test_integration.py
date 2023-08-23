from os import getenv

import pytest
import requests

from span_tree import get_logger

logger = get_logger(__name__)


def test_a_slow_loop(all_traces):
    LOOP_COUNT = 10_000
    with logger.new_span("loop_root"):
        for i in range(LOOP_COUNT):
            if i % 1000 == 0:
                logger.info(f"loop @ {i}/{LOOP_COUNT}")
                logger.log_extra(name="espen")
    assert all_traces
    assert all_traces[0].root_span.duration_ms < 10


def test_simple_math(all_traces):
    with logger.new_span("simple_math"):
        assert 2 + 2 == 4
    assert all_traces[0].root_span.duration_ms < 1


@pytest.mark.skipif(getenv("RUN_SLOW", "") == "", reason="RUN_SLOW must exist in env")
def test_url_get(all_traces):
    with logger.new_span("request get"):
        response = requests.get("https://github.com/EspenAlbert")
        response.raise_for_status()
    assert all_traces[0].root_span.duration_ms > 10
