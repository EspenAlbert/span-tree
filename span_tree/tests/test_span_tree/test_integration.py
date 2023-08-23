from span_tree import get_logger

logger = get_logger(__name__)


def test_a_slow_loop(all_traces):
    LOOP_COUNT = 10_000
    with logger.new_span("loop_root"):
        for i in range(LOOP_COUNT):
            if i % 1000 == 0:
                logger.info(f"loop @ {i}/{LOOP_COUNT}")
                logger.log_extra(name="espen")
